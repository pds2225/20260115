"""Simulation Router

Endpoints for export performance simulation:
- POST /simulate - Run export simulation
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from ..models.schemas import (
    SimulationRequest,
    SimulationResult,
)
from ..services.simulation_service import (
    SimulationService,
    get_simulation_service
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=SimulationResult,
    summary="수출 성과 시뮬레이션",
    description="""
    특정 국가/품목에 대한 수출 성과를 시뮬레이션합니다.
    
    **KOTRA API 연동:**
    - 수출유망추천정보 (ML 기반 성공확률)
    - 국가정보 (경제지표)
    - 해외시장뉴스 (리스크 보정)
    
    **출력:**
    - 예상 매출 범위 (최소/최대)
    - 성공 확률 (0-1)
    - 시장 점유율 추정
    - 뉴스 기반 리스크 분석
    """
)
async def run_simulation(
    request: SimulationRequest,
    service: SimulationService = Depends(get_simulation_service)
) -> SimulationResult:
    """Run export performance simulation."""
    try:
        result = await service.simulate(request)
        logger.info(
            f"Simulation completed for {request.target_country}, "
            f"probability: {result.success_probability:.2%}"
        )
        return result
    except Exception as e:
        logger.error(f"Simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/quick",
    response_model=SimulationResult,
    summary="빠른 시뮬레이션",
    description="GET 방식으로 간단한 시뮬레이션 실행"
)
async def quick_simulation(
    hs_code: str,
    country: str,
    price: float,
    moq: int = 1000,
    capacity: int = 10000,
    include_news: bool = True,
    service: SimulationService = Depends(get_simulation_service)
) -> SimulationResult:
    """Quick simulation via GET request.
    
    Args:
        hs_code: HS Code (4-6 digits)
        country: Target country code (ISO 2-letter)
        price: Price per unit in USD
        moq: Minimum Order Quantity
        capacity: Annual production capacity
        include_news: Include news-based risk analysis
    """
    request = SimulationRequest(
        hs_code=hs_code,
        target_country=country.upper(),
        price_per_unit=price,
        moq=moq,
        annual_capacity=capacity,
        include_news_risk=include_news
    )
    
    try:
        return await service.simulate(request)
    except Exception as e:
        logger.error(f"Quick simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
