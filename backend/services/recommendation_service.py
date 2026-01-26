"""Recommendation Service

개선사항 (2026-01-26):
1. Fallback 개선: 고정 5개국 금지, 캐시 + 대체 스코어링 기반
2. 수출불가국 처리: hard_block 제외, restricted 감점
3. 결측치 처리 + confidence 계산
4. 성공사례 보너스 개선: 증거 강도 기반 점수화
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .kotra_client import KotraAPIClient, get_kotra_client
from ..models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    CountryRecommendation,
    ExportGoal,
    Explanation,
    DataCoverage,
    ComplianceInfo,
)
from ..utils.cache import get_recommendation_cache
from ..utils.compliance import get_compliance_checker, ComplianceStatus
from ..utils.missing_data import MissingDataHandler
from ..utils.confidence import ConfidenceCalculator
from ..database import COUNTRY_MARKET_DATA, get_industry_by_hs_code

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating country recommendations."""

    # Score weights
    WEIGHTS = {
        "export_score": 0.40,
        "economic_score": 0.25,
        "risk_score": 0.20,
        "trend_score": 0.15,
    }

    # 대체 스코어링용 후보국 풀 (고정 5개국 금지 대신 다양한 후보)
    CANDIDATE_POOL = [
        ("US", "미국"), ("CN", "중국"), ("JP", "일본"), ("VN", "베트남"),
        ("DE", "독일"), ("GB", "영국"), ("FR", "프랑스"), ("IT", "이탈리아"),
        ("TH", "태국"), ("ID", "인도네시아"), ("IN", "인도"), ("BR", "브라질"),
        ("MX", "멕시코"), ("AU", "호주"), ("CA", "캐나다"), ("SG", "싱가포르"),
        ("MY", "말레이시아"), ("PH", "필리핀"), ("AE", "아랍에미리트"),
        ("SA", "사우디아라비아"), ("NL", "네덜란드"), ("PL", "폴란드"),
        ("TR", "터키"), ("TW", "대만"), ("HK", "홍콩"),
    ]

    # Country name mapping
    COUNTRY_NAME_MAP = {
        "미국": ("US", "미국"), "중국": ("CN", "중국"), "일본": ("JP", "일본"),
        "베트남": ("VN", "베트남"), "독일": ("DE", "독일"), "영국": ("GB", "영국"),
        "프랑스": ("FR", "프랑스"), "이탈리아": ("IT", "이탈리아"),
        "태국": ("TH", "태국"), "인도네시아": ("ID", "인도네시아"),
        "인도": ("IN", "인도"), "브라질": ("BR", "브라질"),
        "멕시코": ("MX", "멕시코"), "호주": ("AU", "호주"),
        "캐나다": ("CA", "캐나다"), "싱가포르": ("SG", "싱가포르"),
        "말레이시아": ("MY", "말레이시아"), "필리핀": ("PH", "필리핀"),
        "아랍에미리트": ("AE", "아랍에미리트"), "사우디아라비아": ("SA", "사우디아라비아"),
        "네덜란드": ("NL", "네덜란드"), "폴란드": ("PL", "폴란드"),
        "터키": ("TR", "터키"), "러시아": ("RU", "러시아"),
        "대만": ("TW", "대만"), "홍콩": ("HK", "홍콩"),
    }

    def __init__(self, kotra_client: Optional[KotraAPIClient] = None):
        self.kotra_client = kotra_client or get_kotra_client()
        self.cache = get_recommendation_cache()
        self.compliance_checker = get_compliance_checker()
        self.missing_handler = MissingDataHandler()
        self.confidence_calc = ConfidenceCalculator()

    def _get_country_code(self, country_name: str) -> str:
        """Convert country name to ISO code."""
        for name, (code, _) in self.COUNTRY_NAME_MAP.items():
            if name in country_name:
                return code
        return country_name[:2].upper()

    def _get_country_korean_name(self, country_name: str) -> str:
        """Get Korean name for country."""
        for name, (_, korean) in self.COUNTRY_NAME_MAP.items():
            if name in country_name:
                return korean
        return country_name

    async def get_recommendations(
        self,
        request: RecommendationRequest
    ) -> RecommendationResponse:
        """Generate country recommendations with improved fallback."""
        logger.info(f"Generating recommendations for HS code: {request.hs_code}")

        self.missing_handler.reset()
        kotra_status = "ok"
        fallback_used = False
        data_sources = []
        excluded_countries = []

        # 1. KOTRA API 호출 시도
        export_recs = await self.kotra_client.get_export_recommendations(
            hs_code=request.hs_code,
            export_scale=request.export_scale,
            num_rows=50
        )

        # 2. API 실패 시 Fallback 전략
        if not export_recs:
            kotra_status = "unavailable"
            logger.warning("KOTRA API failed, using fallback strategy")

            # 2a. 캐시 확인 (TTL 14일)
            cached = self.cache.get(request.hs_code, "KR")
            if cached:
                fallback_used = True
                logger.info("Using cached recommendations")
                export_recs = cached.get("recommendations", [])
                data_sources = ["캐시된 데이터 (14일 이내)"]
            else:
                # 2b. 대체 스코어링 기반 추천
                fallback_used = True
                export_recs = await self._generate_alternative_recommendations(
                    request.hs_code,
                    request.current_export_countries
                )
                data_sources = ["대체 스코어링 (KOTRA API 장애)"]
        else:
            data_sources = ["KOTRA 수출유망추천정보"]

        # 3. 수출불가국 필터링
        filtered_recs = []
        for rec in export_recs:
            country_code = rec.get("country_code") or self._get_country_code(rec.get("NAT_NAME", ""))
            status, info = self.compliance_checker.check(country_code)

            if status == ComplianceStatus.BLOCKED:
                excluded_countries.append({
                    "country_code": country_code,
                    "reason": info["reason"],
                    "action": "excluded"
                })
                continue

            # restricted 국가는 포함하되 패널티 적용
            if status == ComplianceStatus.RESTRICTED:
                rec["compliance_penalty"] = info["score_penalty"]
                rec["compliance_warning"] = info.get("warning")

            filtered_recs.append(rec)

        # 4. 현재 수출국 제외 (신시장 목표인 경우)
        if request.goal == ExportGoal.NEW_MARKET:
            current_codes = set(request.current_export_countries)
            filtered_recs = [
                r for r in filtered_recs
                if (r.get("country_code") or self._get_country_code(r.get("NAT_NAME", ""))) not in current_codes
            ]

        # 5. 상세 정보 보강
        candidates = filtered_recs[:min(20, len(filtered_recs))]
        recommendations = await self._enrich_recommendations(
            candidates,
            request.hs_code,
            fallback_used
        )

        # 6. 정렬 및 Top N 선택
        recommendations.sort(key=lambda x: x.success_probability, reverse=True)
        top_recommendations = recommendations[:request.top_n]

        for i, rec in enumerate(top_recommendations, 1):
            rec.rank = i

        # 7. 캐시 저장 (API 정상 응답 시)
        if kotra_status == "ok" and recommendations:
            self.cache.set(
                request.hs_code,
                "KR",
                [r.model_dump() for r in recommendations[:20]],
                {"source": "kotra_api", "count": len(recommendations)}
            )

        # 8. Confidence 계산
        missing_fields = self.missing_handler.get_missing_fields()
        confidence, conf_breakdown = self.confidence_calc.calculate(
            context="recommendation",
            missing_fields=missing_fields,
            data_sources_used=data_sources,
            fallback_used=fallback_used,
            kotra_status=kotra_status
        )

        data_coverage = self.missing_handler.get_data_coverage()

        explanation = Explanation(
            kotra_status=kotra_status,
            fallback_used=fallback_used,
            confidence=confidence,
            data_coverage=DataCoverage(
                missing_rate=data_coverage.get("missing_rate", 0),
                missing_fields=data_coverage.get("missing_fields", []),
                imputation_methods=data_coverage.get("imputation_methods", {})
            ),
            warning=self.confidence_calc.get_confidence_warning(confidence),
            interpretation=conf_breakdown.get("interpretation")
        )

        return RecommendationResponse(
            hs_code=request.hs_code,
            goal=request.goal,
            total_countries_analyzed=len(filtered_recs),
            recommendations=top_recommendations,
            data_sources=data_sources + ["KOTRA 국가정보", "KOTRA 상품DB", "KOTRA 기업성공사례"],
            explanation=explanation,
            excluded_countries=excluded_countries,
            generated_at=datetime.utcnow()
        )

    async def _generate_alternative_recommendations(
        self,
        hs_code: str,
        exclude_countries: List[str]
    ) -> List[Dict[str, Any]]:
        """대체 스코어링 기반 추천 생성 (고정 5개국 금지)."""
        exclude_set = set(c.upper() for c in exclude_countries)

        # 후보국 중 blocked 제외
        blocked = set(self.compliance_checker.get_blocked_countries())
        candidates = [
            (code, name) for code, name in self.CANDIDATE_POOL
            if code not in exclude_set and code not in blocked
        ]

        recommendations = []
        industry_info = get_industry_by_hs_code(hs_code)
        industry = industry_info.get("industry_kr", "기타")

        for code, name in candidates:
            # 시장 데이터 기반 스코어 계산
            market_data = COUNTRY_MARKET_DATA.get(code, {})
            gdp = market_data.get("gdp_usd", 500_000_000_000) / 1e12  # 조 USD
            growth_rate = market_data.get("import_growth_rate", 0.03) * 100
            risk_grade = market_data.get("risk_grade", "C")

            # 대체 스코어 계산 (GDP + 성장률 기반)
            base_score = min(5.0, (gdp / 5) + (growth_rate / 2))

            # 리스크 등급 보정
            risk_adj = {"A": 1.2, "B": 1.0, "C": 0.8}.get(risk_grade, 0.7)
            adjusted_score = base_score * risk_adj

            # 산업 관련성 보정
            industry_ratio = market_data.get("industry_ratios", {}).get(industry, 0.005)
            if industry_ratio > 0.01:
                adjusted_score *= 1.1

            recommendations.append({
                "HSCD": hs_code,
                "NAT_CD": code,
                "NAT_NAME": name,
                "country_code": code,
                "EXP_BHRC_SCR": round(adjusted_score, 2),
                "data_source": "alternative_scoring",
                "scoring_basis": {
                    "gdp_trillion": round(gdp, 2),
                    "growth_rate": growth_rate,
                    "risk_grade": risk_grade,
                    "industry_ratio": industry_ratio
                }
            })

        # 점수순 정렬
        recommendations.sort(key=lambda x: x["EXP_BHRC_SCR"], reverse=True)
        return recommendations[:20]

    async def _enrich_recommendations(
        self,
        candidates: List[Dict[str, Any]],
        hs_code: str,
        is_fallback: bool
    ) -> List[CountryRecommendation]:
        """Enrich candidates with additional data."""
        recommendations = []

        for rec in candidates:
            country_name = rec.get("NAT_NAME", "")
            country_code = rec.get("country_code") or self._get_country_code(country_name)
            export_score = float(rec.get("EXP_BHRC_SCR", 0))
            compliance_penalty = rec.get("compliance_penalty", 0)

            # 추가 데이터 가져오기
            try:
                country_info, products, success_cases = await asyncio.gather(
                    self.kotra_client.get_country_economic_indicators(country_code),
                    self.kotra_client.get_product_info(country_code=country_code, num_rows=3),
                    self.kotra_client.get_relevant_success_cases(
                        country_code=country_code,
                        hs_code=hs_code
                    ),
                    return_exceptions=True
                )

                if isinstance(country_info, Exception):
                    country_info = {}
                if isinstance(products, Exception):
                    products = []
                if isinstance(success_cases, Exception):
                    success_cases = []
            except Exception as e:
                logger.error(f"Error enriching data for {country_code}: {e}")
                country_info, products, success_cases = {}, [], []

            # 결측치 처리
            processed_info, _ = self.missing_handler.process_country_info(
                country_info if isinstance(country_info, dict) else {},
                country_code
            )

            # 점수 계산
            score_breakdown = self._calculate_score_breakdown(
                export_score=export_score,
                country_info=processed_info,
                products=products if isinstance(products, list) else [],
                success_cases=success_cases if isinstance(success_cases, list) else [],
                hs_code=hs_code,
                country_code=country_code
            )

            # compliance 패널티 적용
            if compliance_penalty:
                score_breakdown["compliance_penalty"] = compliance_penalty

            total_score = sum(v for k, v in score_breakdown.items() if isinstance(v, (int, float)))
            success_probability = min(1.0, max(0.0, total_score / 100))

            # Compliance 정보
            status, comp_info = self.compliance_checker.check(country_code)
            compliance = ComplianceInfo(
                compliance_status=comp_info["compliance_status"],
                reason=comp_info.get("reason"),
                score_penalty=comp_info.get("score_penalty", 0),
                warning=comp_info.get("warning")
            ) if status != ComplianceStatus.OK else None

            recommendations.append(CountryRecommendation(
                rank=0,
                country_code=country_code,
                country_name=self._get_country_korean_name(country_name) or country_name,
                success_score=export_score,
                success_probability=round(success_probability, 3),
                gdp=processed_info.get("gdp"),
                growth_rate=processed_info.get("growth_rate"),
                risk_grade=processed_info.get("risk_grade"),
                market_characteristics=processed_info.get("market_characteristics"),
                promising_products=[
                    g.get("bhrcGoods", "")
                    for g in processed_info.get("promising_goods", [])[:5]
                ] if isinstance(processed_info.get("promising_goods"), list) else [],
                recent_trends=[
                    {"title": p.get("newsTitl", ""), "date": p.get("othbcDt", "")}
                    for p in (products if isinstance(products, list) else [])[:3]
                ],
                success_cases=success_cases[:3] if isinstance(success_cases, list) else [],
                score_breakdown=score_breakdown,
                compliance=compliance
            ))

        return recommendations

    def _calculate_score_breakdown(
        self,
        export_score: float,
        country_info: Dict[str, Any],
        products: List[Dict[str, Any]],
        success_cases: List[Dict[str, Any]],
        hs_code: str,
        country_code: str
    ) -> Dict[str, float]:
        """Calculate score breakdown with improved success case bonus."""
        breakdown = {}

        # 1. Export score (0-5 → 0-40 points)
        normalized_export = (export_score / 5.0) * 40
        breakdown["export_prediction"] = round(min(40, normalized_export), 2)

        # 2. Economic score (0-25 points)
        economic_score = 15
        growth_rate = country_info.get("growth_rate")
        if growth_rate and growth_rate > 3:
            economic_score += 5
        elif growth_rate and growth_rate > 1:
            economic_score += 2

        gdp = country_info.get("gdp")
        if gdp and gdp > 1000:
            economic_score += 5
        elif gdp and gdp > 100:
            economic_score += 2
        breakdown["economic_indicators"] = round(min(25, economic_score), 2)

        # 3. Risk score (0-20 points)
        risk_score = 15
        risk_grade = country_info.get("risk_grade", "")
        if risk_grade in ["A", "AA", "AAA"]:
            risk_score = 20
        elif risk_grade in ["B", "BB", "BBB"]:
            risk_score = 15
        elif risk_grade in ["C", "CC", "CCC"]:
            risk_score = 10
        elif risk_grade in ["D", "DD", "DDD", "E"]:
            risk_score = 5
        breakdown["risk_assessment"] = round(risk_score, 2)

        # 4. Trend score (0-15 points)
        trend_score = 8
        if products:
            trend_score = min(15, 8 + len(products) * 2)
        breakdown["market_trends"] = round(trend_score, 2)

        # 5. Success case bonus (개선: 증거 강도 기반)
        success_bonus = self._calculate_success_bonus(
            success_cases, hs_code, country_code
        )
        breakdown["success_case_bonus"] = round(success_bonus, 2)

        return breakdown

    def _calculate_success_bonus(
        self,
        success_cases: List[Dict[str, Any]],
        hs_code: str,
        country_code: str
    ) -> float:
        """성공사례 보너스 (증거 강도 기반).

        공식: 10 * country_match * hs_similarity * recency
        """
        if not success_cases:
            return 0.0

        max_bonus = 0.0
        current_year = datetime.now().year
        hs_prefix = hs_code[:4] if hs_code else ""

        for case in success_cases[:5]:
            # 1. country_match (0 or 1)
            case_country = case.get("country", case.get("regn", ""))
            country_match = 1.0 if country_code.upper() in case_country.upper() else 0.0

            # country_match=0이면 거의 무의미
            if country_match == 0:
                continue

            # 2. hs_similarity (0.6 / 0.8 / 1.0)
            case_industry = case.get("industry", "")
            hs_similarity = 0.6  # 기본값
            if hs_prefix and hs_prefix in str(case.get("hs_code", "")):
                hs_similarity = 1.0
            elif hs_prefix[:2] in str(case.get("hs_code", "")):
                hs_similarity = 0.8

            # 3. recency (0.3 / 0.6 / 1.0)
            case_date = case.get("date", case.get("othbcDt", ""))
            recency = 0.6  # 기본값
            try:
                if case_date:
                    case_year = int(case_date[:4])
                    age = current_year - case_year
                    if age <= 5:
                        recency = 1.0
                    elif age <= 10:
                        recency = 0.6
                    else:
                        recency = 0.3
            except (ValueError, TypeError):
                pass

            # 보너스 계산
            bonus = 10 * country_match * hs_similarity * recency
            max_bonus = max(max_bonus, bonus)

        return min(10, max_bonus)  # 최대 10점


# Singleton service instance
_service_instance: Optional[RecommendationService] = None


def get_recommendation_service() -> RecommendationService:
    """Get or create RecommendationService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RecommendationService()
    return _service_instance
