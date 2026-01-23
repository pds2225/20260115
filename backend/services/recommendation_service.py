"""Recommendation Service

Provides country recommendations based on:
1. KOTRA 수출유망추천정보 API (ML-based prediction)
2. KOTRA 국가정보 API (economic indicators)
3. KOTRA 상품DB API (product trends)
4. KOTRA 기업성공사례 API (success cases)

FitScore formula:
- Base: 50 points
- Export Recommendation Score (0-5) → normalized to 0-25 points
- GDP Growth Rate bonus: >3% → +5 points
- Risk Grade penalty: D/E → -5 points
- News sentiment: ±10 points max
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
    ExportGoal
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating country recommendations."""
    
    # Score weights
    WEIGHTS = {
        "export_score": 0.40,      # 40% - ML prediction
        "economic_score": 0.25,    # 25% - GDP/growth
        "risk_score": 0.20,        # 20% - Risk grade
        "trend_score": 0.15,       # 15% - Product trends
    }
    
    # Country name mapping (KOTRA API returns Korean names)
    COUNTRY_NAME_MAP = {
        "미국": ("US", "미국"),
        "중국": ("CN", "중국"),
        "일본": ("JP", "일본"),
        "베트남": ("VN", "베트남"),
        "독일": ("DE", "독일"),
        "영국": ("GB", "영국"),
        "프랑스": ("FR", "프랑스"),
        "이탈리아": ("IT", "이탈리아"),
        "태국": ("TH", "태국"),
        "인도네시아": ("ID", "인도네시아"),
        "인도": ("IN", "인도"),
        "브라질": ("BR", "브라질"),
        "멕시코": ("MX", "멕시코"),
        "호주": ("AU", "호주"),
        "캐나다": ("CA", "캐나다"),
        "싱가포르": ("SG", "싱가포르"),
        "말레이시아": ("MY", "말레이시아"),
        "필리핀": ("PH", "필리핀"),
        "아랍에미리트": ("AE", "아랍에미리트"),
        "사우디아라비아": ("SA", "사우디아라비아"),
        "네덜란드": ("NL", "네덜란드"),
        "폴란드": ("PL", "폴란드"),
        "터키": ("TR", "터키"),
        "러시아": ("RU", "러시아"),
        "대만": ("TW", "대만"),
        "홍콩": ("HK", "홍콩"),
        "카타르": ("QA", "카타르"),
        "칠레": ("CL", "칠레"),
        "이라크": ("IQ", "이라크"),
    }
    
    def __init__(self, kotra_client: Optional[KotraAPIClient] = None):
        """Initialize recommendation service.
        
        Args:
            kotra_client: KOTRA API client instance
        """
        self.kotra_client = kotra_client or get_kotra_client()
    
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
        """Generate country recommendations.
        
        Args:
            request: RecommendationRequest with HS code and preferences
            
        Returns:
            RecommendationResponse with ranked country recommendations
        """
        logger.info(f"Generating recommendations for HS code: {request.hs_code}")
        
        # 1. Get ML-based export recommendations
        export_recs = await self.kotra_client.get_export_recommendations(
            hs_code=request.hs_code,
            export_scale=request.export_scale,
            num_rows=50
        )
        
        if not export_recs:
            logger.warning("No export recommendations returned from KOTRA API")
            return self._generate_fallback_response(request)
        
        # 2. Filter out current export countries if goal is new market
        if request.goal == ExportGoal.NEW_MARKET:
            current_codes = set(request.current_export_countries)
            export_recs = [
                r for r in export_recs
                if self._get_country_code(r.get("NAT_NAME", "")) not in current_codes
            ]
        
        # 3. Get detailed info for top candidates
        candidates = export_recs[:min(20, len(export_recs))]
        
        # Parallel fetch of country info and product trends
        recommendations = await self._enrich_recommendations(
            candidates, 
            request.hs_code
        )
        
        # 4. Rank and select top N
        recommendations.sort(key=lambda x: x.success_probability, reverse=True)
        top_recommendations = recommendations[:request.top_n]
        
        # Assign ranks
        for i, rec in enumerate(top_recommendations, 1):
            rec.rank = i
        
        return RecommendationResponse(
            hs_code=request.hs_code,
            goal=request.goal,
            total_countries_analyzed=len(export_recs),
            recommendations=top_recommendations,
            data_sources=[
                "KOTRA 수출유망추천정보",
                "KOTRA 국가정보",
                "KOTRA 상품DB",
                "KOTRA 기업성공사례"
            ],
            generated_at=datetime.utcnow()
        )
    
    async def _enrich_recommendations(
        self,
        candidates: List[Dict[str, Any]],
        hs_code: str
    ) -> List[CountryRecommendation]:
        """Enrich candidates with additional data.
        
        Args:
            candidates: List of export recommendation records
            hs_code: HS code for trend search
            
        Returns:
            List of enriched CountryRecommendation objects
        """
        recommendations = []
        
        for rec in candidates:
            country_name = rec.get("NAT_NAME", "")
            country_code = self._get_country_code(country_name)
            export_score = float(rec.get("EXP_BHRC_SCR", 0))
            
            # Fetch additional data (with error handling)
            try:
                # Parallel fetch
                country_info_task = self.kotra_client.get_country_economic_indicators(country_code)
                product_task = self.kotra_client.get_product_info(
                    country_code=country_code,
                    num_rows=3
                )
                success_task = self.kotra_client.get_relevant_success_cases(
                    country_code=country_code,
                    hs_code=hs_code
                )
                
                country_info, products, success_cases = await asyncio.gather(
                    country_info_task,
                    product_task,
                    success_task,
                    return_exceptions=True
                )
                
                # Handle exceptions
                if isinstance(country_info, Exception):
                    logger.warning(f"Country info error for {country_code}: {country_info}")
                    country_info = {}
                if isinstance(products, Exception):
                    logger.warning(f"Product info error for {country_code}: {products}")
                    products = []
                if isinstance(success_cases, Exception):
                    logger.warning(f"Success cases error for {country_code}: {success_cases}")
                    success_cases = []
                
            except Exception as e:
                logger.error(f"Error enriching data for {country_code}: {e}")
                country_info = {}
                products = []
                success_cases = []
            
            # Calculate composite score
            score_breakdown = self._calculate_score_breakdown(
                export_score=export_score,
                country_info=country_info,
                products=products
            )
            
            total_score = sum(score_breakdown.values())
            # Normalize to 0-1 probability
            success_probability = min(1.0, max(0.0, total_score / 100))
            
            # Extract trends from products
            recent_trends = [
                {
                    "title": p.get("newsTitl", p.get("title", "")),
                    "date": p.get("othbcDt", ""),
                    "product": p.get("cmdltNmKorn", "")
                }
                for p in (products if isinstance(products, list) else [])[:3]
            ]
            
            recommendation = CountryRecommendation(
                rank=0,  # Set later
                country_code=country_code,
                country_name=self._get_country_korean_name(country_name),
                success_score=export_score,
                success_probability=round(success_probability, 3),
                gdp=country_info.get("gdp") if isinstance(country_info, dict) else None,
                growth_rate=country_info.get("growth_rate") if isinstance(country_info, dict) else None,
                risk_grade=country_info.get("risk_grade") if isinstance(country_info, dict) else None,
                market_characteristics=country_info.get("market_characteristics", "") if isinstance(country_info, dict) else None,
                promising_products=[
                    g.get("bhrcGoods", "") 
                    for g in country_info.get("promising_goods", [])[:5]
                ] if isinstance(country_info, dict) else [],
                recent_trends=recent_trends,
                success_cases=success_cases[:3] if isinstance(success_cases, list) else [],
                score_breakdown=score_breakdown
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def _calculate_score_breakdown(
        self,
        export_score: float,
        country_info: Dict[str, Any],
        products: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate score breakdown.
        
        Args:
            export_score: KOTRA ML score (0-5)
            country_info: Country economic indicators
            products: Product trend data
            
        Returns:
            Dict with score component breakdown
        """
        breakdown = {}
        
        # 1. Export score (0-5 → 0-40 points)
        normalized_export = (export_score / 5.0) * 40
        breakdown["export_prediction"] = round(normalized_export, 2)
        
        # 2. Economic score (0-25 points)
        economic_score = 15  # Base
        if country_info:
            growth_rate = country_info.get("growth_rate")
            if growth_rate and growth_rate > 3:
                economic_score += 5
            elif growth_rate and growth_rate > 1:
                economic_score += 2
            
            gdp = country_info.get("gdp")
            if gdp and gdp > 1000:  # GDP > 1 trillion
                economic_score += 5
            elif gdp and gdp > 100:
                economic_score += 2
        breakdown["economic_indicators"] = round(min(25, economic_score), 2)
        
        # 3. Risk score (0-20 points, penalty for bad grades)
        risk_score = 15  # Base
        if country_info:
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
        
        # 4. Trend score (0-15 points based on recent activity)
        trend_score = 8  # Base
        if products:
            trend_score = min(15, 8 + len(products) * 2)
        breakdown["market_trends"] = round(trend_score, 2)
        
        return breakdown
    
    def _generate_fallback_response(
        self,
        request: RecommendationRequest
    ) -> RecommendationResponse:
        """Generate fallback response when API fails.
        
        Args:
            request: Original request
            
        Returns:
            RecommendationResponse with default recommendations
        """
        # Default promising markets
        DEFAULT_MARKETS = [
            ("US", "미국", 3.5),
            ("CN", "중국", 3.2),
            ("VN", "베트남", 3.0),
            ("JP", "일본", 2.8),
            ("DE", "독일", 2.5),
        ]
        
        recommendations = []
        for i, (code, name, score) in enumerate(DEFAULT_MARKETS[:request.top_n], 1):
            if code not in request.current_export_countries:
                recommendations.append(CountryRecommendation(
                    rank=i,
                    country_code=code,
                    country_name=name,
                    success_score=score,
                    success_probability=score / 5.0,
                    score_breakdown={
                        "export_prediction": score * 8,
                        "economic_indicators": 15,
                        "risk_assessment": 15,
                        "market_trends": 10
                    }
                ))
        
        return RecommendationResponse(
            hs_code=request.hs_code,
            goal=request.goal,
            total_countries_analyzed=len(DEFAULT_MARKETS),
            recommendations=recommendations,
            data_sources=["기본 데이터 (API 응답 없음)"],
            generated_at=datetime.utcnow()
        )


# Singleton service instance
_service_instance: Optional[RecommendationService] = None


def get_recommendation_service() -> RecommendationService:
    """Get or create RecommendationService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RecommendationService()
    return _service_instance
