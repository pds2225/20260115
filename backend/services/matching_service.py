"""Matching Service

개선사항 (2026-01-26):
1. MOQ 고도화: Hard Gate + Soft Score + MOV(최소주문금액) 반영
2. 인증 매칭 정교화: required vs preferred 분리
3. 성공사례 보너스 개선: 증거 강도 기반 점수화
4. 수출불가국 처리: hard_block 제외, restricted 감점
5. 결측치 처리 + confidence 계산
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from .kotra_client import KotraAPIClient, get_kotra_client
from ..models.schemas import (
    MatchRequest,
    MatchResponse,
    MatchResult,
    ProfileType,
    Explanation,
    DataCoverage,
    ComplianceInfo,
)
from ..database import (
    load_seller_profiles,
    load_buyer_profiles,
    get_industry_by_hs_code,
    get_fraud_penalty,
    get_country_fraud_summary,
    FRAUD_TYPE_WEIGHTS,
    COUNTRY_MARKET_DATA,
)
from ..utils.compliance import get_compliance_checker, ComplianceStatus
from ..utils.missing_data import MissingDataHandler
from ..utils.confidence import ConfidenceCalculator

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for buyer-seller matching."""

    # Score configuration
    BASE_SCORE = 50
    HS_MATCH_BONUS = 20
    PRICE_MATCH_BONUS = 15
    MOQ_MAX_BONUS = 10
    CERT_REQUIRED_MAX = 20  # required 인증 최대
    CERT_PREFERRED_BONUS = 3  # preferred 인증 개당
    SUCCESS_CASE_MAX_BONUS = 10
    FRAUD_PENALTY_CAP = -25

    def __init__(self, kotra_client: Optional[KotraAPIClient] = None):
        self.kotra_client = kotra_client or get_kotra_client()
        self.compliance_checker = get_compliance_checker()
        self.missing_handler = MissingDataHandler()
        self.confidence_calc = ConfidenceCalculator()

        self._sellers = load_seller_profiles()
        self._buyers = load_buyer_profiles()

    async def find_matches(
        self,
        request: MatchRequest
    ) -> MatchResponse:
        """Find matching partners with improved MOQ, cert, and success case logic."""
        logger.info(f"Finding matches for {request.profile_type} profile")

        self.missing_handler.reset()
        profile = request.profile
        blocked_countries = []
        kotra_status = "ok"

        # 후보 풀 결정
        if request.profile_type == ProfileType.SELLER:
            candidates = self._buyers.copy()
        else:
            candidates = self._sellers.copy()

        # 수출불가국 필터링
        filtered_candidates = []
        for candidate in candidates:
            country = candidate.get("country", "")
            status, info = self.compliance_checker.check(country)

            if status == ComplianceStatus.BLOCKED:
                if country not in blocked_countries:
                    blocked_countries.append(country)
                continue

            candidate["compliance_info"] = info
            filtered_candidates.append(candidate)

        candidates = filtered_candidates

        # 국가별 리스크 데이터 조회
        countries = list(set(c.get("country", "") for c in candidates))
        fraud_results = {}
        success_results = {}

        if request.include_risk_analysis:
            for country in countries:
                if country:
                    try:
                        fraud_results[country] = await self.kotra_client.get_country_fraud_risk(country)
                    except Exception as e:
                        logger.warning(f"Fraud risk error for {country}: {e}")
                        fraud_results[country] = {"risk_level": "SAFE", "score_penalty": 0}

                    try:
                        success_results[country] = await self.kotra_client.get_relevant_success_cases(
                            country_code=country,
                            hs_code=profile.get("hs_code", "")
                        )
                    except Exception as e:
                        logger.warning(f"Success cases error for {country}: {e}")
                        success_results[country] = []

        # 매칭 점수 계산
        matches = []
        high_risk_countries = []

        for candidate in candidates:
            country = candidate.get("country", "")

            # MOQ Hard Gate 체크
            moq_gate, moq_score, order_value, moq_reason = self._evaluate_moq(
                profile, candidate, request.profile_type
            )

            # MOQ Hard Gate 실패 시 탈락 (fit_score=0)
            if not moq_gate:
                matches.append(self._create_failed_match(
                    candidate, request.profile_type, moq_reason
                ))
                continue

            # 인증 매칭 (required vs preferred)
            cert_result = self._evaluate_certifications(profile, candidate)

            # required 인증 미충족 시 탈락
            if not cert_result["required_passed"]:
                matches.append(self._create_failed_match(
                    candidate, request.profile_type,
                    f"필수 인증 미충족: {', '.join(cert_result['missing_required'])}"
                ))
                continue

            # FitScore 계산
            fit_score, score_breakdown = self._calculate_fit_score(
                profile=profile,
                candidate=candidate,
                moq_score=moq_score,
                cert_result=cert_result,
                fraud_risk=fraud_results.get(country, {}),
                success_cases=success_results.get(country, [])
            )

            # High risk 국가 추적
            if fraud_results.get(country, {}).get("risk_level") == "HIGH":
                if country not in high_risk_countries:
                    high_risk_countries.append(country)

            # Compliance 정보
            comp_info = candidate.get("compliance_info", {})
            compliance = None
            if comp_info.get("compliance_status") != "ok":
                compliance = ComplianceInfo(
                    compliance_status=comp_info.get("compliance_status", "ok"),
                    reason=comp_info.get("reason"),
                    score_penalty=comp_info.get("score_penalty", 0),
                    warning=comp_info.get("warning")
                )

            partner_type = (
                ProfileType.BUYER
                if request.profile_type == ProfileType.SELLER
                else ProfileType.SELLER
            )

            match_result = MatchResult(
                partner_id=candidate.get("id", "unknown"),
                partner_type=partner_type,
                company_name=candidate.get("company_name"),
                country=country,
                country_name=self._get_country_name(country),
                fit_score=round(fit_score, 2),
                score_breakdown=score_breakdown,
                hs_code_match=self._check_hs_match(
                    profile.get("hs_code", ""),
                    candidate.get("hs_code", "")
                ),
                price_compatible=self._check_price_compatibility(
                    profile.get("price_range", [0, 0]),
                    candidate.get("price_range", [0, 0])
                ),
                moq_compatible=moq_gate,
                moq_gate_passed=moq_gate,
                moq_score=round(moq_score, 3),
                order_value_usd=round(order_value, 2) if order_value else None,
                missing_required_certs=cert_result["missing_required"],
                matched_preferred_certs=cert_result["matched_preferred"],
                certification_match=cert_result["matched_all"],
                fraud_risk=fraud_results.get(country) if request.include_risk_analysis else None,
                compliance=compliance,
                success_cases=success_results.get(country, [])[:2]
            )

            matches.append(match_result)

        # 점수순 정렬
        matches.sort(key=lambda x: x.fit_score, reverse=True)

        # Confidence 계산
        missing_fields = self.missing_handler.get_missing_fields()
        data_sources = ["KOTRA 무역사기사례", "KOTRA 기업성공사례"]
        confidence, conf_breakdown = self.confidence_calc.calculate(
            context="matching",
            missing_fields=missing_fields,
            data_sources_used=data_sources,
            fallback_used=False,
            kotra_status=kotra_status
        )

        explanation = Explanation(
            kotra_status=kotra_status,
            fallback_used=False,
            confidence=confidence,
            data_coverage=DataCoverage(
                missing_rate=len(missing_fields) / 10 if missing_fields else 0,
                missing_fields=missing_fields,
                imputation_methods={}
            ),
            warning=self.confidence_calc.get_confidence_warning(confidence),
            interpretation=conf_breakdown.get("interpretation")
        )

        return MatchResponse(
            profile_type=request.profile_type,
            total_candidates=len(candidates),
            matches=matches[:request.top_n],
            countries_analyzed=countries,
            high_risk_countries=high_risk_countries,
            blocked_countries=blocked_countries,
            explanation=explanation,
            data_sources=data_sources,
            generated_at=datetime.utcnow()
        )

    def _evaluate_moq(
        self,
        profile: Dict[str, Any],
        candidate: Dict[str, Any],
        profile_type: ProfileType
    ) -> Tuple[bool, float, float, str]:
        """MOQ 평가: Hard Gate + Soft Score + MOV.

        Returns:
            (gate_passed, soft_score 0-1, order_value_usd, failure_reason)
        """
        profile_moq = profile.get("moq", 0)
        candidate_moq = candidate.get("moq", 0)
        annual_capacity = profile.get("annual_capacity") or candidate.get("annual_capacity")
        min_order_usd = profile.get("min_order_usd") or candidate.get("min_order_usd")
        price_range = candidate.get("price_range", [0, 0])
        unit_price = (price_range[0] + price_range[1]) / 2 if len(price_range) >= 2 else 5.0

        # 주문 금액 계산
        order_value = candidate_moq * unit_price if candidate_moq else 0

        # 1. Hard Gate: buyer_moq > seller_capacity
        if profile_type == ProfileType.SELLER:
            # seller 입장: buyer의 MOQ가 seller capacity를 초과하면 탈락
            if annual_capacity and candidate_moq > annual_capacity:
                return False, 0.0, order_value, f"바이어 MOQ({candidate_moq})가 연간 생산능력({annual_capacity})을 초과"

        else:
            # buyer 입장: seller의 MOQ가 buyer가 원하는 것보다 너무 크면 탈락
            if profile_moq and candidate_moq > profile_moq * 3:
                return False, 0.0, order_value, f"셀러 MOQ({candidate_moq})가 원하는 MOQ({profile_moq})의 3배 초과"

        # 2. MOV(최소주문금액) 체크
        if min_order_usd and order_value < min_order_usd:
            return False, 0.0, order_value, f"주문금액(${order_value:.0f})이 최소주문금액(${min_order_usd:.0f}) 미달"

        # 3. Soft Score: MOQ 범위 대비 벗어나는 정도
        if profile_moq > 0 and candidate_moq > 0:
            ratio = abs(profile_moq - candidate_moq) / max(profile_moq, candidate_moq)
            if ratio <= 0.2:
                soft_score = 1.0
            elif ratio <= 0.5:
                soft_score = 0.7
            elif ratio <= 1.0:
                soft_score = 0.4
            else:
                soft_score = 0.2
        else:
            soft_score = 0.5  # 정보 부족

        return True, soft_score, order_value, ""

    def _evaluate_certifications(
        self,
        profile: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """인증 매칭 평가: required vs preferred.

        Returns:
            {
                required_passed: bool,
                missing_required: List[str],
                matched_preferred: List[str],
                matched_all: List[str],
                required_score: float (0-1),
                preferred_score: float (0-1)
            }
        """
        # 하위호환: certifications → required_certs로 마이그레이션
        profile_required = profile.get("required_certs", [])
        profile_preferred = profile.get("preferred_certs", [])

        # 기존 certifications 필드가 있고 required가 비어있으면 마이그레이션
        if not profile_required and profile.get("certifications"):
            profile_required = profile.get("certifications", [])

        candidate_certs = set(c.upper() for c in candidate.get("certifications", []))

        # Required 평가
        required_set = set(c.upper() for c in profile_required)
        matched_required = required_set & candidate_certs
        missing_required = list(required_set - candidate_certs)

        # Required 충족률
        if required_set:
            required_score = len(matched_required) / len(required_set)
            required_passed = len(missing_required) == 0
        else:
            required_score = 1.0
            required_passed = True

        # Preferred 평가
        preferred_set = set(c.upper() for c in profile_preferred)
        matched_preferred = list(preferred_set & candidate_certs)
        preferred_score = len(matched_preferred) / len(preferred_set) if preferred_set else 0.0

        # 전체 매칭
        matched_all = list(matched_required | set(matched_preferred))

        return {
            "required_passed": required_passed,
            "missing_required": missing_required,
            "matched_required": list(matched_required),
            "matched_preferred": matched_preferred,
            "matched_all": matched_all,
            "required_score": required_score,
            "preferred_score": preferred_score
        }

    def _calculate_fit_score(
        self,
        profile: Dict[str, Any],
        candidate: Dict[str, Any],
        moq_score: float,
        cert_result: Dict[str, Any],
        fraud_risk: Dict[str, Any],
        success_cases: List[Dict[str, Any]]
    ) -> Tuple[float, Dict[str, Any]]:
        """FitScore 계산 (개선된 로직)."""
        breakdown = {"base": self.BASE_SCORE}
        total = self.BASE_SCORE

        # 1. HS Code Match (+20)
        hs_match = self._check_hs_match(
            profile.get("hs_code", ""),
            candidate.get("hs_code", "")
        )
        if hs_match:
            breakdown["hs_code_match"] = self.HS_MATCH_BONUS
            total += self.HS_MATCH_BONUS
        else:
            breakdown["hs_code_match"] = 0

        # 2. Price Compatibility (+15)
        price_match = self._check_price_compatibility(
            profile.get("price_range", [0, 0]),
            candidate.get("price_range", [0, 0])
        )
        if price_match:
            breakdown["price_compatible"] = self.PRICE_MATCH_BONUS
            total += self.PRICE_MATCH_BONUS
        else:
            breakdown["price_compatible"] = 0

        # 3. MOQ Score (Soft Score × 10)
        moq_bonus = round(moq_score * self.MOQ_MAX_BONUS, 2)
        breakdown["moq_compatible"] = moq_bonus
        total += moq_bonus

        # 4. Certification Score (required 충족률 + preferred 가점)
        cert_bonus = 0
        # required 충족률 × 15
        cert_bonus += cert_result["required_score"] * 15
        # preferred 개당 +3, 최대 +6
        cert_bonus += min(len(cert_result["matched_preferred"]) * self.CERT_PREFERRED_BONUS, 6)
        cert_bonus = min(cert_bonus, self.CERT_REQUIRED_MAX)
        breakdown["certification_match"] = round(cert_bonus, 2)
        breakdown["missing_required_certs"] = cert_result["missing_required"]
        breakdown["matched_preferred_certs"] = cert_result["matched_preferred"]
        total += cert_bonus

        # 5. Fraud Risk Penalty
        fraud_penalty = self._calculate_fraud_penalty(fraud_risk)
        breakdown["fraud_risk_penalty"] = fraud_penalty
        breakdown["fraud_types_detail"] = fraud_risk.get("fraud_types", {})
        total += fraud_penalty

        # 6. Success Case Bonus (증거 강도 기반)
        success_bonus = self._calculate_success_bonus(
            profile.get("hs_code", ""),
            candidate.get("country", ""),
            success_cases
        )
        breakdown["success_case_bonus"] = round(success_bonus, 2)
        total += success_bonus

        # 7. Compliance Penalty
        comp_info = candidate.get("compliance_info", {})
        comp_penalty = comp_info.get("score_penalty", 0)
        if comp_penalty:
            breakdown["compliance_penalty"] = comp_penalty
            total += comp_penalty

        # 0-100 범위로 클램프
        total = max(0, min(100, total))

        return total, breakdown

    def _calculate_fraud_penalty(self, fraud_risk: Dict[str, Any]) -> int:
        """사기 리스크 패널티 계산."""
        if not fraud_risk:
            return 0

        fraud_types = fraud_risk.get("fraud_type_distribution",
                                     fraud_risk.get("fraud_types", {}))

        if not fraud_types:
            case_count = fraud_risk.get("case_count", 0)
            if case_count >= 20:
                return -20
            elif case_count >= 10:
                return -12
            elif case_count >= 5:
                return -6
            return 0

        total_penalty = 0
        for fraud_type, count in fraud_types.items():
            type_info = FRAUD_TYPE_WEIGHTS.get(fraud_type, FRAUD_TYPE_WEIGHTS['기타'])
            penalty_per_case = type_info['base_penalty'] / 5
            total_penalty += penalty_per_case * count

        return max(self.FRAUD_PENALTY_CAP, int(total_penalty))

    def _calculate_success_bonus(
        self,
        hs_code: str,
        country_code: str,
        success_cases: List[Dict[str, Any]]
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
            # 1. country_match
            case_country = case.get("country", case.get("regn", ""))
            country_match = 1.0 if country_code.upper() in case_country.upper() else 0.0

            if country_match == 0:
                continue

            # 2. hs_similarity
            hs_similarity = 0.6
            case_hs = str(case.get("hs_code", ""))
            if hs_prefix and hs_prefix in case_hs:
                hs_similarity = 1.0
            elif len(hs_prefix) >= 2 and hs_prefix[:2] in case_hs:
                hs_similarity = 0.8

            # 3. recency
            case_date = case.get("date", case.get("othbcDt", ""))
            recency = 0.6
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

            bonus = 10 * country_match * hs_similarity * recency
            max_bonus = max(max_bonus, bonus)

        return min(self.SUCCESS_CASE_MAX_BONUS, max_bonus)

    def _create_failed_match(
        self,
        candidate: Dict[str, Any],
        profile_type: ProfileType,
        reason: str
    ) -> MatchResult:
        """탈락 후보의 MatchResult 생성."""
        partner_type = (
            ProfileType.BUYER
            if profile_type == ProfileType.SELLER
            else ProfileType.SELLER
        )

        return MatchResult(
            partner_id=candidate.get("id", "unknown"),
            partner_type=partner_type,
            company_name=candidate.get("company_name"),
            country=candidate.get("country", ""),
            country_name=self._get_country_name(candidate.get("country", "")),
            fit_score=0.0,
            score_breakdown={"failed": True, "reason": reason},
            hs_code_match=False,
            price_compatible=False,
            moq_compatible=False,
            moq_gate_passed=False,
            moq_score=0.0,
            order_value_usd=None,
            missing_required_certs=[],
            matched_preferred_certs=[],
            certification_match=[],
            fraud_risk=None,
            compliance=None,
            success_cases=[]
        )

    def _check_hs_match(self, hs1: str, hs2: str) -> bool:
        """HS 코드 매칭 (4자리)."""
        if not hs1 or not hs2:
            return False
        return hs1[:4] == hs2[:4]

    def _check_price_compatibility(
        self,
        range1: List[float],
        range2: List[float]
    ) -> bool:
        """가격 범위 호환성."""
        if len(range1) < 2 or len(range2) < 2:
            return False
        return range1[1] >= range2[0] and range2[1] >= range1[0]

    def _get_country_name(self, country_code: str) -> str:
        """국가 코드 → 한글명."""
        country_data = COUNTRY_MARKET_DATA.get(country_code.upper(), {})
        if country_data:
            return country_data.get('name_kr', country_code)

        NAMES = {
            "US": "미국", "CN": "중국", "JP": "일본", "VN": "베트남",
            "DE": "독일", "GB": "영국", "FR": "프랑스", "KR": "한국",
            "SG": "싱가포르", "TH": "태국", "ID": "인도네시아", "IN": "인도",
            "AU": "호주", "AE": "아랍에미리트",
        }
        return NAMES.get(country_code.upper(), country_code)

    def add_seller(self, profile: Dict[str, Any]) -> str:
        """셀러 프로필 추가."""
        if "id" not in profile:
            profile["id"] = f"seller_{len(self._sellers) + 1:03d}"
        self._sellers.append(profile)
        return profile["id"]

    def add_buyer(self, profile: Dict[str, Any]) -> str:
        """바이어 프로필 추가."""
        if "id" not in profile:
            profile["id"] = f"buyer_{len(self._buyers) + 1:03d}"
        self._buyers.append(profile)
        return profile["id"]


# Singleton
_service_instance: Optional[MatchingService] = None


def get_matching_service() -> MatchingService:
    """Get or create MatchingService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MatchingService()
    return _service_instance
