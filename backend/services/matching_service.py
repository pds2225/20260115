"""Matching Service

Provides buyer-seller matching based on:
1. Profile compatibility (HS code, price, MOQ, certifications)
2. KOTRA 무역사기사례 API (fraud risk penalty)
3. KOTRA 기업성공사례 API (success case references)

FitScore Formula (0-100):
- Base: 50 points
- HS Code Match (4-digit): +20 points
- Price Compatibility: +15 points
- MOQ Compatibility: +10 points
- Certification Match: +5 points per match (max +15)
- Fraud Risk Penalty: -15 to 0 points
- Success Case Bonus: +5 points if similar cases exist
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
from ..database import load_seller_profiles, load_buyer_profiles

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for buyer-seller matching."""
    
    # Score configuration
    BASE_SCORE = 50
    HS_MATCH_BONUS = 20
    PRICE_MATCH_BONUS = 15
    MOQ_MATCH_BONUS = 10
    CERT_MATCH_BONUS = 5  # Per certification, max 15
    SUCCESS_CASE_BONUS = 5
    
    # Fraud risk penalties
    FRAUD_PENALTIES = {
        "HIGH": -15,
        "MEDIUM": -7,
        "LOW": -3,
        "SAFE": 0
    }
    
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
        if self._check_hs_match(
            profile.get("hs_code", ""),
            candidate.get("hs_code", "")
        ):
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
        # For sellers: buyer MOQ should be >= seller MOQ
        # For buyers: seller MOQ should be <= buyer acceptable MOQ
        profile_moq = profile.get("moq", 0)
        candidate_moq = candidate.get("moq", 0)
        
        if profile_moq > 0 and candidate_moq > 0:
            if abs(profile_moq - candidate_moq) / max(profile_moq, candidate_moq) < 0.5:
                breakdown["moq_compatible"] = self.MOQ_MATCH_BONUS
                total += self.MOQ_MATCH_BONUS
            else:
                breakdown["moq_compatible"] = 0
        else:
            breakdown["moq_compatible"] = self.MOQ_MATCH_BONUS // 2  # Partial credit
            total += self.MOQ_MATCH_BONUS // 2
        
        # 4. Certification Match (+5 per, max 15)
        cert_matches = self._get_certification_matches(
            profile.get("certifications", []),
            candidate.get("certifications", [])
        )
        cert_bonus = min(len(cert_matches) * self.CERT_MATCH_BONUS, 15)
        breakdown["certification_match"] = cert_bonus
        total += cert_bonus
        
        # 5. Fraud Risk Penalty (-15 to 0)
        risk_level = fraud_risk.get("risk_level", "SAFE")
        fraud_penalty = self.FRAUD_PENALTIES.get(risk_level, 0)
        breakdown["fraud_risk_penalty"] = fraud_penalty
        total += fraud_penalty
        
        # 6. Success Case Bonus (+5)
        if success_cases:
            breakdown["success_case_bonus"] = self.SUCCESS_CASE_BONUS
            total += self.SUCCESS_CASE_BONUS
        else:
            breakdown["success_case_bonus"] = 0
        
        # Clamp to 0-100
        total = max(0, min(100, total))
        
        return total, breakdown
    
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
        """Get Korean country name."""
        NAMES = {
            "US": "미국",
            "CN": "중국",
            "JP": "일본",
            "VN": "베트남",
            "DE": "독일",
            "GB": "영국",
            "FR": "프랑스",
            "KR": "한국",
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
