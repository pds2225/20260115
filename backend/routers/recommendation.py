"""Recommendation Router

Endpoints for country recommendation based on KOTRA APIs:
- POST /recommend - Get country recommendations for export
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from ..models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    ExportGoal
)
from ..services.recommendation_service import (
    RecommendationService,
    get_recommendation_service
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=RecommendationResponse,
    summary="국가 추천",
    description="""
    HS코드와 수출 목표를 기반으로 유망 수출 국가를 추천합니다.
    
    **KOTRA API 연동:**
    - 수출유망추천정보 (ML 기반 예측)
    - 국가정보 (경제지표)
    - 상품DB (트렌드)
    - 기업성공사례 (참고 사례)
    
    **점수 계산:**
    - 수출유망예측 (40%)
    - 경제지표 (25%)
    - 리스크등급 (20%)
    - 시장트렌드 (15%)
    """
)
async def get_recommendations(
    request: RecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service)
) -> RecommendationResponse:
    """Get country recommendations for export."""
    try:
        result = await service.get_recommendations(request)
        logger.info(
            f"Generated {len(result.recommendations)} recommendations "
            f"for HS code {request.hs_code}"
        )
        return result
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/quick",
    response_model=RecommendationResponse,
    summary="빠른 국가 추천",
    description="GET 방식으로 간단하게 추천받기"
)
async def quick_recommendations(
    hs_code: str,
    goal: ExportGoal = ExportGoal.NEW_MARKET,
    top_n: int = 5,
    exclude_countries: Optional[str] = None,
    service: RecommendationService = Depends(get_recommendation_service)
) -> RecommendationResponse:
    """Quick recommendation via GET request.
    
    Args:
        hs_code: HS Code (4-6 digits)
        goal: Export goal (new_market, market_expansion, risk_diversification)
        top_n: Number of recommendations (1-20)
        exclude_countries: Comma-separated country codes to exclude
    """
    # Parse exclude list
    current_countries = []
    if exclude_countries:
        current_countries = [c.strip().upper() for c in exclude_countries.split(",")]
    
    request = RecommendationRequest(
        hs_code=hs_code,
        current_export_countries=current_countries,
        goal=goal,
        top_n=min(max(1, top_n), 20)
    )
    
    try:
        return await service.get_recommendations(request)
    except Exception as e:
        logger.error(f"Quick recommendation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
