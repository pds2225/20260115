"""Simulation Service

Provides export performance simulation based on:
1. KOTRA 국가정보 API (economic indicators)
2. KOTRA 해외시장뉴스 API (news sentiment/risk)
3. KOTRA 수출유망추천정보 API (ML prediction)

Success Probability Formula:
- Base: 30%
- Export Recommendation (predProb): +40% weight
- Economic Indicators (GDP growth, risk grade): +25% weight
- News Sentiment (positive/negative keywords): +20% weight
- Product Trends: +15% weight

Revenue Estimation:
- Market share assumption: 0.01% - 0.1%
- Based on import amount (impAmt) from country info
"""

import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from .kotra_client import KotraAPIClient, get_kotra_client
from ..models.schemas import (
    SimulationRequest,
    SimulationResult,
)
from ..database import (
    get_market_size,
    get_industry_by_hs_code,
    COUNTRY_MARKET_DATA,
)

logger = logging.getLogger(__name__)


class SimulationService:
    """Service for simulating export performance."""
    
    # Base probability
    BASE_PROBABILITY = 0.30
    
    # Weight factors
    WEIGHTS = {
        "export_ml": 0.40,      # ML prediction weight
        "economic": 0.25,       # Economic indicators
        "news_sentiment": 0.20, # News analysis
        "trends": 0.15,         # Product trends
    }
    
    # Market share assumptions
    MIN_MARKET_SHARE = 0.0001  # 0.01%
    MAX_MARKET_SHARE = 0.001   # 0.1%
    
    def __init__(self, kotra_client: Optional[KotraAPIClient] = None):
        """Initialize simulation service.
        
        Args:
            kotra_client: KOTRA API client instance
        """
        self.kotra_client = kotra_client or get_kotra_client()
    
    async def simulate(
        self,
        request: SimulationRequest
    ) -> SimulationResult:
        """Run export performance simulation.
        
        Args:
            request: SimulationRequest with target country and company params
            
        Returns:
            SimulationResult with revenue projections and success probability
        """
        logger.info(f"Running simulation for {request.target_country}, HS: {request.hs_code}")
        
        # Parallel data fetching
        tasks = {
            "export_rec": self.kotra_client.get_export_recommendations(
                hs_code=request.hs_code,
                num_rows=100
            ),
            "country_info": self.kotra_client.get_country_economic_indicators(
                country_code=request.target_country
            ),
            "product_info": self.kotra_client.get_product_info(
                country_code=request.target_country,
                num_rows=10
            ),
        }
        
        # Add news analysis if requested
        if request.include_news_risk:
            tasks["news_risk"] = self.kotra_client.analyze_news_risk(
                country_code=request.target_country,
                num_articles=50
            )
        
        results = {}
        for key, task in tasks.items():
            try:
                results[key] = await task
            except Exception as e:
                logger.warning(f"Error fetching {key}: {e}")
                results[key] = {} if key != "export_rec" else []
        
        # Extract relevant export recommendation
        export_score = self._get_export_score(
            results.get("export_rec", []),
            request.hs_code,
            request.target_country
        )
        
        # Calculate success probability
        probability, breakdown = self._calculate_probability(
            export_score=export_score,
            country_info=results.get("country_info", {}),
            news_risk=results.get("news_risk", {}),
            product_count=len(results.get("product_info", []))
        )
        
        # Estimate market size (GDP × 산업비중 기반 개선된 로직)
        market_result = self._estimate_market_size(
            country_code=request.target_country,
            hs_code=request.hs_code,
            country_info=results.get("country_info", {}),
            user_estimate=request.market_size_estimate
        )
        market_size = market_result["market_size"]
        
        # Calculate revenue projections
        revenue_min, revenue_max = self._calculate_revenue(
            market_size=market_size,
            probability=probability,
            price_per_unit=request.price_per_unit,
            annual_capacity=request.annual_capacity
        )
        
        # Market share calculation
        market_share_min = (revenue_min / market_size * 100) if market_size > 0 else 0
        market_share_max = (revenue_max / market_size * 100) if market_size > 0 else 0
        
        country_info = results.get("country_info", {})
        
        # breakdown에 시장규모 계산 상세 추가
        breakdown["market_estimation"] = {
            "market_size_usd": market_size,
            "source": market_result["source"],
            "confidence": market_result["confidence"],
            "details": market_result["breakdown"]
        }
        
        return SimulationResult(
            target_country=request.target_country,
            country_name=country_info.get("country_name", request.target_country),
            hs_code=request.hs_code,
            estimated_revenue_min=round(revenue_min, 2),
            estimated_revenue_max=round(revenue_max, 2),
            success_probability=round(probability, 3),
            market_size=market_size,
            market_share_min=round(market_share_min, 4),
            market_share_max=round(market_share_max, 4),
            news_risk_adjustment=results.get("news_risk") if request.include_news_risk else None,
            economic_indicators={
                "gdp": country_info.get("gdp"),
                "growth_rate": country_info.get("growth_rate"),
                "inflation_rate": country_info.get("inflation_rate"),
                "risk_grade": country_info.get("risk_grade"),
                "exchange_rate": country_info.get("exchange_rate"),
            },
            calculation_breakdown=breakdown,
            data_sources=[
                "KOTRA 수출유망추천정보",
                "KOTRA 국가정보",
                "KOTRA 해외시장뉴스",
                "시장규모 산정: " + market_result["source"]
            ],
            generated_at=datetime.utcnow()
        )
    
    def _get_export_score(
        self,
        export_recs: list,
        hs_code: str,
        target_country: str
    ) -> float:
        """Extract export score for target country.
        
        Args:
            export_recs: List of export recommendations
            hs_code: Target HS code
            target_country: Target country code/name
            
        Returns:
            Export success score (0-5)
        """
        if not export_recs:
            return 2.5  # Default middle score
        
        hs_prefix = hs_code[:4]
        
        for rec in export_recs:
            rec_hs = rec.get("HSCD", "")
            rec_country = rec.get("NAT_NAME", "")
            
            # Match by HS code prefix and country
            if rec_hs.startswith(hs_prefix):
                if target_country.upper() in rec_country.upper():
                    return float(rec.get("EXP_BHRC_SCR", 2.5))
        
        # If no exact match, return average of matching HS codes
        matching = [
            float(r.get("EXP_BHRC_SCR", 0))
            for r in export_recs
            if r.get("HSCD", "").startswith(hs_prefix)
        ]
        
        return sum(matching) / len(matching) if matching else 2.5
    
    def _calculate_probability(
        self,
        export_score: float,
        country_info: Dict[str, Any],
        news_risk: Dict[str, Any],
        product_count: int
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate success probability.
        
        Args:
            export_score: ML export score (0-5)
            country_info: Country economic indicators
            news_risk: News sentiment analysis
            product_count: Number of product trends found
            
        Returns:
            Tuple of (probability, breakdown dict)
        """
        breakdown = {
            "base_probability": self.BASE_PROBABILITY,
            "weights": self.WEIGHTS.copy(),
            "components": {}
        }
        
        # 1. Export ML Score (0-5 → 0-1)
        export_factor = export_score / 5.0
        breakdown["components"]["export_ml"] = {
            "raw_score": export_score,
            "normalized": export_factor,
            "contribution": export_factor * self.WEIGHTS["export_ml"]
        }
        
        # 2. Economic Indicators
        economic_factor = 0.5  # Base
        
        if country_info:
            growth_rate = country_info.get("growth_rate")
            risk_grade = country_info.get("risk_grade", "")
            
            # Growth rate bonus
            if growth_rate:
                if growth_rate > 5:
                    economic_factor += 0.3
                elif growth_rate > 3:
                    economic_factor += 0.2
                elif growth_rate > 1:
                    economic_factor += 0.1
                elif growth_rate < 0:
                    economic_factor -= 0.2
            
            # Risk grade adjustment
            if risk_grade in ["A", "AA", "AAA"]:
                economic_factor += 0.2
            elif risk_grade in ["B", "BB", "BBB"]:
                economic_factor += 0.1
            elif risk_grade in ["D", "DD", "DDD", "E"]:
                economic_factor -= 0.2
        
        economic_factor = max(0, min(1, economic_factor))
        breakdown["components"]["economic"] = {
            "growth_rate": country_info.get("growth_rate"),
            "risk_grade": country_info.get("risk_grade"),
            "factor": economic_factor,
            "contribution": economic_factor * self.WEIGHTS["economic"]
        }
        
        # 3. News Sentiment
        news_factor = 0.5  # Neutral base
        
        if news_risk:
            risk_adjustment = news_risk.get("risk_adjustment", 0)
            # Convert -15 to +15 range to 0-1
            news_factor = 0.5 + (risk_adjustment / 30)
            news_factor = max(0, min(1, news_factor))
        
        breakdown["components"]["news_sentiment"] = {
            "risk_adjustment": news_risk.get("risk_adjustment", 0),
            "positive_count": news_risk.get("positive_count", 0),
            "negative_count": news_risk.get("negative_count", 0),
            "factor": news_factor,
            "contribution": news_factor * self.WEIGHTS["news_sentiment"]
        }
        
        # 4. Product Trends
        trend_factor = min(1.0, 0.3 + (product_count * 0.1))
        breakdown["components"]["trends"] = {
            "product_count": product_count,
            "factor": trend_factor,
            "contribution": trend_factor * self.WEIGHTS["trends"]
        }
        
        # Calculate final probability
        weighted_sum = (
            export_factor * self.WEIGHTS["export_ml"] +
            economic_factor * self.WEIGHTS["economic"] +
            news_factor * self.WEIGHTS["news_sentiment"] +
            trend_factor * self.WEIGHTS["trends"]
        )
        
        # Scale and clamp
        probability = self.BASE_PROBABILITY + (weighted_sum * 0.65)
        probability = max(0.05, min(0.95, probability))
        
        breakdown["final_probability"] = probability
        
        return probability, breakdown
    
    def _estimate_market_size(
        self,
        country_code: str,
        hs_code: str,
        country_info: Dict[str, Any],
        user_estimate: Optional[float]
    ) -> Dict[str, Any]:
        """Estimate market size using GDP-based industry calculation.
        
        Updated 2024-01-24: GDP × 산업비중 기반 동적 계산
        
        Args:
            country_code: Target country code (US, CN, JP, etc.)
            hs_code: HS code for industry mapping
            country_info: Country economic data from API
            user_estimate: User-provided estimate in USD millions
            
        Returns:
            Dict with market_size, source, confidence, breakdown
        """
        result = {
            "market_size": 100_000_000,  # Default $100M
            "source": "default",
            "confidence": "low",
            "breakdown": {}
        }
        
        # Priority 1: User-provided estimate
        if user_estimate:
            result["market_size"] = user_estimate * 1_000_000
            result["source"] = "user_estimate"
            result["confidence"] = "high"
            result["breakdown"]["user_estimate_millions"] = user_estimate
            return result
        
        # Priority 2: GDP × 산업비중 기반 계산 (database.py 활용)
        industry_info = get_industry_by_hs_code(hs_code)
        industry_kr = industry_info.get("industry_kr", "기타")
        
        market_data = get_market_size(country_code, industry_kr)
        
        if market_data.get("source") != "default":
            result["market_size"] = market_data["market_size_usd"]
            result["source"] = market_data["source"]
            result["confidence"] = market_data["confidence"]
            result["breakdown"] = {
                "country": country_code,
                "industry": industry_kr,
                "industry_en": industry_info.get("industry_en"),
                "gdp_usd": market_data.get("gdp_usd"),
                "industry_ratio": market_data.get("industry_ratio"),
                "growth_rate": market_data.get("growth_rate"),
                "calculation_method": "GDP × industry_ratio"
            }
            return result
        
        # Priority 3: API에서 받은 GDP 정보로 계산
        gdp = country_info.get("gdp")
        if gdp:
            # 산업별 기본 비중 (화장품: 0.5%, 의약품: 3%, 식품: 1%)
            industry_ratios = {
                "화장품": 0.005,
                "의약품": 0.03,
                "식품": 0.01,
                "전자기기": 0.02,
                "섬유": 0.008,
                "기타": 0.005
            }
            ratio = industry_ratios.get(industry_kr, 0.005)
            market_size = gdp * 1_000_000_000 * ratio
            
            result["market_size"] = market_size
            result["source"] = "api_gdp_estimate"
            result["confidence"] = "medium"
            result["breakdown"] = {
                "country": country_code,
                "industry": industry_kr,
                "gdp_billions": gdp,
                "industry_ratio": ratio,
                "calculation_method": "API_GDP × default_industry_ratio"
            }
            return result
        
        # Fallback: 기본값
        result["breakdown"] = {
            "country": country_code,
            "industry": industry_kr,
            "reason": "No GDP data available"
        }
        return result
    
    def _calculate_revenue(
        self,
        market_size: float,
        probability: float,
        price_per_unit: float,
        annual_capacity: int
    ) -> Tuple[float, float]:
        """Calculate revenue projections.
        
        Args:
            market_size: Total market size in USD
            probability: Success probability
            price_per_unit: Price per unit in USD
            annual_capacity: Annual production capacity
            
        Returns:
            Tuple of (min_revenue, max_revenue) in USD
        """
        # Capacity-based max revenue
        capacity_revenue = price_per_unit * annual_capacity
        
        # Market share based revenue
        market_revenue_min = market_size * self.MIN_MARKET_SHARE
        market_revenue_max = market_size * self.MAX_MARKET_SHARE
        
        # Adjust by probability
        adjusted_min = market_revenue_min * probability
        adjusted_max = market_revenue_max * probability
        
        # Cap by capacity
        final_min = min(adjusted_min, capacity_revenue * 0.3)
        final_max = min(adjusted_max, capacity_revenue * 0.8)
        
        return final_min, final_max


# Singleton service instance
_service_instance: Optional[SimulationService] = None


def get_simulation_service() -> SimulationService:
    """Get or create SimulationService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SimulationService()
    return _service_instance
