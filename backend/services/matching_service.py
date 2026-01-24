"""Matching Service

Provides buyer-seller matching based on:
1. Profile compatibility (HS code, price, MOQ, certifications)
2. KOTRA 무역사기사례 API (fraud risk penalty)
3. KOTRA 기업성공사례 API (success case references)

FitScore Formula (0-100) - Updated 2024-01-24:
- Base: 50 points
- HS Code Match (4-digit): +20 points
- Price Compatibility: +15 points
- MOQ Compatibility: +10 points
- Certification Match: +5 points per match (max +15)
- Fraud Risk Penalty: -20 to 0 points (유형별 차등 적용)
- Success Case Bonus: +5~15 points (산업 매칭 시 추가 보너스)
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .kotra_client import KotraAPIClient, get_kotra_client
from ..models.schemas import (
    MatchRequest,
    MatchResponse,
    MatchResult,
    ProfileType,
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

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for buyer-seller matching."""
    
    # Score configuration
    BASE_SCORE = 50
    HS_MATCH_BONUS = 20
    PRICE_MATCH_BONUS = 15
    MOQ_MATCH_BONUS = 10
    CERT_MATCH_BONUS = 5  # Per certification, max 15
    SUCCESS_CASE_BONUS_BASE = 5
    SUCCESS_CASE_BONUS_INDUSTRY = 10  # 동일 산업 성공사례 시 추가
    
    # Fraud risk penalties (유형별 차등 적용 - database.py에서 가져옴)
    # 이메일해킹: -20, 금품사취: -18, 선적서류위조: -15, 품질사기: -12, 기업사칭: -15
    FRAUD_PENALTY_CAP = -25  # 최대 페널티 측
    
    def __init__(self, kotra_client: Optional[KotraAPIClient] = None):
        """Initialize matching service.
        
        Args:
            kotra_client: KOTRA API client instance
        """
        self.kotra_client = kotra_client or get_kotra_client()
        
        # Load in-memory profiles (would be DB in production)
        self._sellers = load_seller_profiles()
        self._buyers = load_buyer_profiles()
    
    async def find_matches(
        self,
        request: MatchRequest
    ) -> MatchResponse:
        """Find matching partners for a profile.
        
        Args:
            request: MatchRequest with profile data
            
        Returns:
            MatchResponse with ranked matches
        """
        logger.info(f"Finding matches for {request.profile_type} profile")
        
        profile = request.profile
        
        # Determine candidate pool
        if request.profile_type == ProfileType.SELLER:
            candidates = self._buyers
        else:
            candidates = self._sellers
        
        # Get unique countries from candidates
        countries = list(set(c.get("country", "") for c in candidates))
        
        # Fetch risk data for all countries in parallel
        fraud_risk_tasks = {}
        success_case_tasks = {}
        
        if request.include_risk_analysis:
            for country in countries:
                if country:
                    fraud_risk_tasks[country] = self.kotra_client.get_country_fraud_risk(country)
                    success_case_tasks[country] = self.kotra_client.get_relevant_success_cases(
                        country_code=country,
                        hs_code=profile.get("hs_code", "")
                    )
        
        # Execute all tasks
        fraud_results = {}
        success_results = {}
        
        for country, task in fraud_risk_tasks.items():
            try:
                fraud_results[country] = await task
            except Exception as e:
                logger.warning(f"Fraud risk error for {country}: {e}")
                fraud_results[country] = {"risk_level": "SAFE", "score_penalty": 0}
        
        for country, task in success_case_tasks.items():
            try:
                success_results[country] = await task
            except Exception as e:
                logger.warning(f"Success cases error for {country}: {e}")
                success_results[country] = []
        
        # Score and rank candidates
        matches = []
        high_risk_countries = []
        
        for candidate in candidates:
            country = candidate.get("country", "")
            
            # Calculate FitScore
            fit_score, score_breakdown = self._calculate_fit_score(
                profile=profile,
                candidate=candidate,
                fraud_risk=fraud_results.get(country, {}),
                success_cases=success_results.get(country, [])
            )
            
            # Track high risk countries
            if fraud_results.get(country, {}).get("risk_level") == "HIGH":
                if country not in high_risk_countries:
                    high_risk_countries.append(country)
            
            # Check compatibilities
            hs_match = self._check_hs_match(
                profile.get("hs_code", ""),
                candidate.get("hs_code", "")
            )
            price_compatible = self._check_price_compatibility(
                profile.get("price_range", [0, 0]),
                candidate.get("price_range", [0, 0])
            )
            moq_compatible = self._check_moq_compatibility(
                profile.get("moq", 0),
                candidate.get("moq", 0),
                request.profile_type
            )
            cert_match = self._get_certification_matches(
                profile.get("certifications", []),
                candidate.get("certifications", [])
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
                hs_code_match=hs_match,
                price_compatible=price_compatible,
                moq_compatible=moq_compatible,
                certification_match=cert_match,
                fraud_risk=fraud_results.get(country) if request.include_risk_analysis else None,
                success_cases=success_results.get(country, [])[:2]
            )
            
            matches.append(match_result)
        
        # Sort by FitScore descending
        matches.sort(key=lambda x: x.fit_score, reverse=True)
        
        return MatchResponse(
            profile_type=request.profile_type,
            total_candidates=len(candidates),
            matches=matches[:request.top_n],
            countries_analyzed=countries,
            high_risk_countries=high_risk_countries,
            data_sources=[
                "KOTRA 무역사기사례",
                "KOTRA 기업성공사례"
            ],
            generated_at=datetime.utcnow()
        )
    
    def _calculate_fit_score(
        self,
        profile: Dict[str, Any],
        candidate: Dict[str, Any],
        fraud_risk: Dict[str, Any],
        success_cases: List[Dict[str, Any]]
    ) -> tuple[float, Dict[str, float]]:
        """Calculate FitScore for a candidate.
        
        Updated 2024-01-24: 무역사기 유형별 차등 페널티 + 산업 매칭 보너스 추가
        
        Args:
            profile: User's profile
            candidate: Candidate profile
            fraud_risk: Fraud risk data for candidate's country
            success_cases: Success cases for candidate's country
            
        Returns:
            Tuple of (total_score, breakdown_dict)
        """
        breakdown = {"base": self.BASE_SCORE}
        total = self.BASE_SCORE
        
        # 1. HS Code Match (+20)
        profile_hs = profile.get("hs_code", "")
        candidate_hs = candidate.get("hs_code", "")
        
        if self._check_hs_match(profile_hs, candidate_hs):
            breakdown["hs_code_match"] = self.HS_MATCH_BONUS
            total += self.HS_MATCH_BONUS
        else:
            breakdown["hs_code_match"] = 0
        
        # 2. Price Compatibility (+15)
        if self._check_price_compatibility(
            profile.get("price_range", [0, 0]),
            candidate.get("price_range", [0, 0])
        ):
            breakdown["price_compatible"] = self.PRICE_MATCH_BONUS
            total += self.PRICE_MATCH_BONUS
        else:
            breakdown["price_compatible"] = 0
        
        # 3. MOQ Compatibility (+10)
        profile_moq = profile.get("moq", 0)
        candidate_moq = candidate.get("moq", 0)
        
        if profile_moq > 0 and candidate_moq > 0:
            if abs(profile_moq - candidate_moq) / max(profile_moq, candidate_moq) < 0.5:
                breakdown["moq_compatible"] = self.MOQ_MATCH_BONUS
                total += self.MOQ_MATCH_BONUS
            else:
                breakdown["moq_compatible"] = 0
        else:
            breakdown["moq_compatible"] = self.MOQ_MATCH_BONUS // 2
            total += self.MOQ_MATCH_BONUS // 2
        
        # 4. Certification Match (+5 per, max 15)
        cert_matches = self._get_certification_matches(
            profile.get("certifications", []),
            candidate.get("certifications", [])
        )
        cert_bonus = min(len(cert_matches) * self.CERT_MATCH_BONUS, 15)
        breakdown["certification_match"] = cert_bonus
        total += cert_bonus
        
        # 5. Fraud Risk Penalty (유형별 차등 적용, -25 ~ 0)
        fraud_penalty = self._calculate_fraud_penalty(fraud_risk)
        breakdown["fraud_risk_penalty"] = fraud_penalty
        breakdown["fraud_types_detail"] = fraud_risk.get("fraud_types", {})
        total += fraud_penalty
        
        # 6. Success Case Bonus (+5 ~ +15, 산업 매칭 시 추가)
        success_bonus = self._calculate_success_bonus(profile_hs, success_cases)
        breakdown["success_case_bonus"] = success_bonus
        total += success_bonus
        
        # Clamp to 0-100
        total = max(0, min(100, total))
        
        return total, breakdown
    
    def _calculate_fraud_penalty(
        self, 
        fraud_risk: Dict[str, Any]
    ) -> int:
        """Calculate fraud penalty based on fraud type distribution.
        
        유형별 차등 페널티:
        - 이메일해킹: -20
        - 금품사취: -18
        - 선적서류위조: -15
        - 기업사칭: -15
        - 운송사기: -12
        - 품질사기: -12
        - 인증서위조: -10
        - 기타: -8
        """
        if not fraud_risk:
            return 0
        
        # 사기 유형별 분포 가져오기
        fraud_types = fraud_risk.get("fraud_type_distribution", 
                                      fraud_risk.get("fraud_types", {}))
        
        if not fraud_types:
            # 건수 기반 기본 페널티
            case_count = fraud_risk.get("case_count", 0)
            if case_count >= 20:
                return -20
            elif case_count >= 10:
                return -12
            elif case_count >= 5:
                return -6
            return 0
        
        # 유형별 가중 페널티 계산
        total_penalty = 0
        for fraud_type, count in fraud_types.items():
            type_info = FRAUD_TYPE_WEIGHTS.get(fraud_type, FRAUD_TYPE_WEIGHTS['기타'])
            # 건당 페널티의 1/5 적용 (누적 효과)
            penalty_per_case = type_info['base_penalty'] / 5
            total_penalty += penalty_per_case * count
        
        # 최대 페널티 측
        return max(self.FRAUD_PENALTY_CAP, int(total_penalty))
    
    def _calculate_success_bonus(
        self,
        hs_code: str,
        success_cases: List[Dict[str, Any]]
    ) -> int:
        """Calculate success case bonus with industry matching.
        
        기본 보너스: +5 (성공사례 존재 시)
        산업 매칭 보너스: +10 (동일 산업 성공사례 존재 시)
        """
        if not success_cases:
            return 0
        
        bonus = self.SUCCESS_CASE_BONUS_BASE
        
        # HS코드로 산업 확인
        industry_info = get_industry_by_hs_code(hs_code)
        profile_industry = industry_info.get('industry_kr', '')
        
        # 성공사례 중 동일 산업 확인
        for case in success_cases:
            case_industry = case.get('industry', '')
            if profile_industry and profile_industry in case_industry:
                bonus += self.SUCCESS_CASE_BONUS_INDUSTRY
                break  # 한 건만 매칭되면 보너스 부여
        
        return min(bonus, 15)  # 최대 +15
    
    def _check_hs_match(self, hs1: str, hs2: str) -> bool:
        """Check if HS codes match (first 4 digits)."""
        if not hs1 or not hs2:
            return False
        return hs1[:4] == hs2[:4]
    
    def _check_price_compatibility(
        self,
        range1: List[float],
        range2: List[float]
    ) -> bool:
        """Check if price ranges overlap."""
        if len(range1) < 2 or len(range2) < 2:
            return False
        
        min1, max1 = range1[0], range1[1]
        min2, max2 = range2[0], range2[1]
        
        # Check overlap
        return max1 >= min2 and max2 >= min1
    
    def _check_moq_compatibility(
        self,
        profile_moq: int,
        candidate_moq: int,
        profile_type: ProfileType
    ) -> bool:
        """Check MOQ compatibility."""
        if profile_moq <= 0 or candidate_moq <= 0:
            return True  # No MOQ constraint
        
        if profile_type == ProfileType.SELLER:
            # Buyer's MOQ should be >= seller's MOQ
            return candidate_moq >= profile_moq
        else:
            # Seller's MOQ should be <= buyer's acceptable MOQ
            return candidate_moq <= profile_moq
    
    def _get_certification_matches(
        self,
        certs1: List[str],
        certs2: List[str]
    ) -> List[str]:
        """Get matching certifications."""
        set1 = set(c.upper() for c in certs1)
        set2 = set(c.upper() for c in certs2)
        return list(set1 & set2)
    
    def _get_country_name(self, country_code: str) -> str:
        """Get Korean country name from COUNTRY_MARKET_DATA."""
        country_data = COUNTRY_MARKET_DATA.get(country_code.upper(), {})
        if country_data:
            return country_data.get('name_kr', country_code)
        
        # Fallback
        NAMES = {
            "US": "미국", "CN": "중국", "JP": "일본", "VN": "베트남",
            "DE": "독일", "GB": "영국", "FR": "프랑스", "KR": "한국",
            "SG": "싱가포르", "TH": "태국", "ID": "인도네시아", "IN": "인도",
            "AU": "호주", "AE": "아랍에미리트",
        }
        return NAMES.get(country_code.upper(), country_code)
    
    def add_seller(self, profile: Dict[str, Any]) -> str:
        """Add a seller profile (for testing)."""
        if "id" not in profile:
            profile["id"] = f"seller_{len(self._sellers) + 1:03d}"
        self._sellers.append(profile)
        return profile["id"]
    
    def add_buyer(self, profile: Dict[str, Any]) -> str:
        """Add a buyer profile (for testing)."""
        if "id" not in profile:
            profile["id"] = f"buyer_{len(self._buyers) + 1:03d}"
        self._buyers.append(profile)
        return profile["id"]


# Singleton service instance
_service_instance: Optional[MatchingService] = None


def get_matching_service() -> MatchingService:
    """Get or create MatchingService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MatchingService()
    return _service_instance
