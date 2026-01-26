"""Simulation Service

개선사항 (2026-01-26):
1. 수출불가국 처리: hard_block 시뮬레이션 거부, restricted 경고
2. 결측치 처리: LOCF/지역평균 대체, 0으로 채우기 금지
3. Confidence 계산: 필수 피처 결측률 기반
4. Explanation 상세화 (kotra_status, fallback_used, confidence, data_coverage)
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import logging

from .kotra_client import KotraAPIClient, get_kotra_client
from ..models.schemas import (
    SimulationRequest,
    SimulationResult,
    Explanation,
    DataCoverage,
    ComplianceInfo,
)
from ..database import (
    get_market_size,
    get_industry_by_hs_code,
    COUNTRY_MARKET_DATA,
)
from ..utils.compliance import get_compliance_checker, ComplianceStatus
from ..utils.missing_data import MissingDataHandler
from ..utils.confidence import ConfidenceCalculator

logger = logging.getLogger(__name__)


class SimulationService:
    """Service for simulating export performance."""

    BASE_PROBABILITY = 0.30
    WEIGHTS = {
        "export_ml": 0.40,
        "economic": 0.25,
        "news_sentiment": 0.20,
        "trends": 0.15,
    }
    MIN_MARKET_SHARE = 0.0001
    MAX_MARKET_SHARE = 0.001
    EXPORT_SCORE_MAX = 30.0

    COUNTRY_NAME_MAP = {
        "US": ["미국"], "CN": ["중국"], "JP": ["일본"], "VN": ["베트남"],
        "DE": ["독일"], "SG": ["싱가포르"], "TH": ["태국"], "ID": ["인도네시아"],
        "IN": ["인도"], "AU": ["호주"], "GB": ["영국"], "FR": ["프랑스"],
        "AE": ["아랍에미리트"], "CA": ["캐나다"], "MX": ["멕시코"],
    }

    def __init__(self, kotra_client: Optional[KotraAPIClient] = None):
        self.kotra_client = kotra_client or get_kotra_client()
        self.compliance_checker = get_compliance_checker()
        self.missing_handler = MissingDataHandler()
        self.confidence_calc = ConfidenceCalculator()

    async def simulate(self, request: SimulationRequest) -> SimulationResult:
        """Run export simulation with compliance check and confidence."""
        logger.info(f"Running simulation for {request.target_country}, HS: {request.hs_code}")

        self.missing_handler.reset()
        kotra_status = "ok"
        fallback_used = False
        data_sources = []

        # 1. Compliance 체크 (수출불가국 처리)
        status, comp_info = self.compliance_checker.check(request.target_country)

        if status == ComplianceStatus.BLOCKED:
            return self._create_blocked_result(request, comp_info)

        compliance = None
        if status == ComplianceStatus.RESTRICTED:
            compliance = ComplianceInfo(
                compliance_status="restricted",
                reason=comp_info.get("reason"),
                score_penalty=comp_info.get("score_penalty", 0),
                warning=comp_info.get("warning")
            )

        # 2. KOTRA API 호출
        export_rec = []
        country_info = {}
        product_info = []
        news_risk = {}

        try:
            export_rec = await self.kotra_client.get_export_recommendations(
                hs_code=request.hs_code,
                num_rows=100
            )
            data_sources.append("KOTRA 수출유망추천정보")
        except Exception as e:
            logger.warning(f"Export rec API error: {e}")
            kotra_status = "unavailable"
            fallback_used = True

        try:
            country_info = await self.kotra_client.get_country_economic_indicators(
                request.target_country
            )
            data_sources.append("KOTRA 국가정보")
        except Exception as e:
            logger.warning(f"Country info API error: {e}")
            kotra_status = "unavailable"
            fallback_used = True

        try:
            product_info = await self.kotra_client.get_product_info(
                country_code=request.target_country,
                num_rows=10
            )
            data_sources.append("KOTRA 상품DB")
        except Exception as e:
            logger.warning(f"Product info API error: {e}")

        if request.include_news_risk:
            try:
                news_risk = await self.kotra_client.analyze_news_risk(
                    country_code=request.target_country,
                    num_articles=50
                )
                data_sources.append("KOTRA 해외시장뉴스")
            except Exception as e:
                logger.warning(f"News risk API error: {e}")

        # 3. 결측치 처리 (0으로 채우기 금지)
        processed_info, imputation_methods = self.missing_handler.process_country_info(
            country_info if isinstance(country_info, dict) else {},
            request.target_country
        )

        # 4. Export score 추출
        export_score = self._get_export_score(
            export_rec if isinstance(export_rec, list) else [],
            request.hs_code,
            request.target_country
        )

        # 5. 확률 계산
        probability, breakdown = self._calculate_probability(
            export_score=export_score,
            country_info=processed_info,
            news_risk=news_risk if isinstance(news_risk, dict) else {},
            product_count=len(product_info) if isinstance(product_info, list) else 0,
            compliance_penalty=comp_info.get("score_penalty", 0)
        )

        # 6. 시장 규모 추정
        market_result = self._estimate_market_size(
            country_code=request.target_country,
            hs_code=request.hs_code,
            country_info=processed_info,
            user_estimate=request.market_size_estimate
        )
        market_size = market_result["market_size"]

        # 7. 매출 계산
        revenue_min, revenue_max = self._calculate_revenue(
            market_size=market_size,
            probability=probability,
            price_per_unit=request.price_per_unit,
            annual_capacity=request.annual_capacity
        )

        market_share_min = (revenue_min / market_size * 100) if market_size > 0 else 0
        market_share_max = (revenue_max / market_size * 100) if market_size > 0 else 0

        # 시장규모 breakdown 추가
        breakdown["market_estimation"] = {
            "market_size_usd": market_size,
            "source": market_result["source"],
            "confidence": market_result["confidence"],
            "details": market_result["breakdown"]
        }

        # 8. Confidence 계산
        missing_fields = self.missing_handler.get_missing_fields()
        confidence, conf_breakdown = self.confidence_calc.calculate(
            context="simulation",
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

        country_name = processed_info.get("country_name") or self._get_country_name(request.target_country)

        return SimulationResult(
            target_country=request.target_country,
            country_name=country_name,
            hs_code=request.hs_code,
            estimated_revenue_min=round(revenue_min, 2),
            estimated_revenue_max=round(revenue_max, 2),
            success_probability=round(probability, 3),
            market_size=market_size,
            market_share_min=round(market_share_min, 4),
            market_share_max=round(market_share_max, 4),
            news_risk_adjustment=news_risk if request.include_news_risk and news_risk else None,
            economic_indicators={
                "gdp": processed_info.get("gdp"),
                "growth_rate": processed_info.get("growth_rate"),
                "inflation_rate": processed_info.get("inflation_rate"),
                "risk_grade": processed_info.get("risk_grade")
            },
            calculation_breakdown=breakdown,
            explanation=explanation,
            compliance=compliance,
            data_sources=data_sources,
            generated_at=datetime.utcnow()
        )

    def _create_blocked_result(
        self,
        request: SimulationRequest,
        comp_info: Dict[str, Any]
    ) -> SimulationResult:
        """차단국에 대한 시뮬레이션 결과 (거부)."""
        explanation = Explanation(
            kotra_status="blocked",
            fallback_used=False,
            confidence=0.0,
            data_coverage=DataCoverage(missing_rate=1.0, missing_fields=[], imputation_methods={}),
            warning=f"수출 금지 대상국: {comp_info.get('reason')}",
            interpretation="시뮬레이션 불가 - 수출 금지 국가"
        )

        compliance = ComplianceInfo(
            compliance_status="blocked",
            reason=comp_info.get("reason"),
            score_penalty=-100,
            warning=comp_info.get("action")
        )

        return SimulationResult(
            target_country=request.target_country,
            country_name=request.target_country,
            hs_code=request.hs_code,
            estimated_revenue_min=0.0,
            estimated_revenue_max=0.0,
            success_probability=0.0,
            market_size=0.0,
            market_share_min=0.0,
            market_share_max=0.0,
            news_risk_adjustment=None,
            economic_indicators={},
            calculation_breakdown={
                "status": "blocked",
                "reason": comp_info.get("reason")
            },
            explanation=explanation,
            compliance=compliance,
            data_sources=[],
            generated_at=datetime.utcnow()
        )

    def _get_export_score(
        self,
        export_recs: List[Dict[str, Any]],
        hs_code: str,
        target_country: str
    ) -> float:
        """KOTRA API에서 수출 점수 추출."""
        if not export_recs:
            region = self.missing_handler.get_region(target_country)
            defaults = {
                "asia": 7.0, "europe": 6.0, "americas": 8.0,
                "middle_east": 5.0, "africa": 4.0, "default": 6.2
            }
            return defaults.get(region, 6.2)

        hs_prefix = hs_code[:4]
        country_names = self.COUNTRY_NAME_MAP.get(target_country.upper(), [target_country])

        for rec in export_recs:
            if rec.get("HSCD", "").startswith(hs_prefix):
                for name in country_names:
                    if name in rec.get("NAT_NAME", ""):
                        return float(rec.get("EXP_BHRC_SCR", 6.2))

        matching = [
            float(r.get("EXP_BHRC_SCR", 0))
            for r in export_recs
            if r.get("HSCD", "").startswith(hs_prefix)
        ]

        if matching:
            return sum(matching) / len(matching)

        return 6.2

    def _calculate_probability(
        self,
        export_score: float,
        country_info: Dict[str, Any],
        news_risk: Dict[str, Any],
        product_count: int,
        compliance_penalty: int = 0
    ) -> Tuple[float, Dict[str, Any]]:
        """성공 확률 계산."""
        breakdown = {
            "base_probability": self.BASE_PROBABILITY,
            "weights": self.WEIGHTS.copy(),
            "components": {}
        }

        # 1. Export ML score
        export_factor = min(export_score / self.EXPORT_SCORE_MAX, 1.0)
        breakdown["components"]["export_ml"] = {
            "raw_score": export_score,
            "normalized": round(export_factor, 3),
            "contribution": round(export_factor * self.WEIGHTS["export_ml"], 3)
        }

        # 2. Economic score
        economic_factor = 0.5
        growth_rate = country_info.get("growth_rate")
        if growth_rate:
            if growth_rate > 5:
                economic_factor += 0.3
            elif growth_rate > 3:
                economic_factor += 0.2
            elif growth_rate > 1:
                economic_factor += 0.1

        risk_grade = country_info.get("risk_grade", "")
        if risk_grade in ["A", "AA", "AAA"]:
            economic_factor += 0.2
        elif risk_grade in ["B", "BB", "BBB"]:
            economic_factor += 0.1
        elif risk_grade in ["D", "DD", "E"]:
            economic_factor -= 0.1

        economic_factor = max(0, min(1, economic_factor))
        breakdown["components"]["economic"] = {
            "factor": round(economic_factor, 3),
            "growth_rate": growth_rate,
            "risk_grade": risk_grade,
            "contribution": round(economic_factor * self.WEIGHTS["economic"], 3)
        }

        # 3. News sentiment
        news_factor = 0.5
        if news_risk:
            risk_adjustment = news_risk.get("risk_adjustment", 0)
            news_factor = 0.5 + (risk_adjustment / 30)
            news_factor = max(0, min(1, news_factor))

        breakdown["components"]["news_sentiment"] = {
            "factor": round(news_factor, 3),
            "adjustment": news_risk.get("risk_adjustment", 0) if news_risk else 0,
            "contribution": round(news_factor * self.WEIGHTS["news_sentiment"], 3)
        }

        # 4. Trends
        trend_factor = min(1.0, 0.3 + (product_count * 0.1))
        breakdown["components"]["trends"] = {
            "factor": round(trend_factor, 3),
            "product_count": product_count,
            "contribution": round(trend_factor * self.WEIGHTS["trends"], 3)
        }

        # 가중 합계
        weighted_sum = (
            export_factor * self.WEIGHTS["export_ml"] +
            economic_factor * self.WEIGHTS["economic"] +
            news_factor * self.WEIGHTS["news_sentiment"] +
            trend_factor * self.WEIGHTS["trends"]
        )

        probability = self.BASE_PROBABILITY + (weighted_sum * 0.65)

        # Compliance 패널티 적용
        if compliance_penalty:
            penalty_factor = 1.0 + (compliance_penalty / 100)
            probability *= max(0.3, penalty_factor)
            breakdown["compliance_penalty"] = compliance_penalty

        probability = max(0.05, min(0.95, probability))
        breakdown["final_probability"] = round(probability, 3)

        return probability, breakdown

    def _estimate_market_size(
        self,
        country_code: str,
        hs_code: str,
        country_info: Dict[str, Any],
        user_estimate: Optional[float]
    ) -> Dict[str, Any]:
        """시장 규모 추정."""
        if user_estimate:
            return {
                "market_size": user_estimate * 1_000_000,
                "source": "user_estimate",
                "confidence": "high",
                "breakdown": {"user_provided": True}
            }

        industry_info = get_industry_by_hs_code(hs_code)
        industry_kr = industry_info.get("industry_kr", "기타")

        market_data = get_market_size(country_code, industry_kr)

        if market_data.get("source") != "default":
            return {
                "market_size": market_data["market_size_usd"],
                "source": market_data["source"],
                "confidence": market_data["confidence"],
                "breakdown": {
                    "country": country_code,
                    "industry": industry_kr,
                    "gdp_usd": market_data.get("gdp_usd"),
                    "industry_ratio": market_data.get("industry_ratio")
                }
            }

        return {
            "market_size": 100_000_000,
            "source": "default",
            "confidence": "low",
            "breakdown": {}
        }

    def _calculate_revenue(
        self,
        market_size: float,
        probability: float,
        price_per_unit: float,
        annual_capacity: int
    ) -> Tuple[float, float]:
        """예상 매출 계산."""
        capacity_revenue = price_per_unit * annual_capacity

        market_revenue_min = market_size * self.MIN_MARKET_SHARE
        market_revenue_max = market_size * self.MAX_MARKET_SHARE

        adjusted_min = market_revenue_min * probability
        adjusted_max = market_revenue_max * probability

        final_min = min(adjusted_min, capacity_revenue * 0.3)
        final_max = min(adjusted_max, capacity_revenue * 0.8)

        return final_min, final_max

    def _get_country_name(self, country_code: str) -> str:
        """국가 코드 → 한글명."""
        names = self.COUNTRY_NAME_MAP.get(country_code.upper(), [])
        if names:
            return names[0]

        country_data = COUNTRY_MARKET_DATA.get(country_code.upper(), {})
        return country_data.get("name_kr", country_code)


# Singleton
_service_instance: Optional[SimulationService] = None


def get_simulation_service() -> SimulationService:
    """Get or create SimulationService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SimulationService()
    return _service_instance
