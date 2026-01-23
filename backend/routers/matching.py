"""Matching Router

Endpoints for buyer-seller matching:
- POST /match - Find matching partners
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from ..models.schemas import (
    MatchRequest,
    MatchResponse,
    ProfileType,
)
from ..services.matching_service import (
    MatchingService,
    get_matching_service
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=MatchResponse,
    summary="바이어-셀러 매칭",
    description="""
    셀러 또는 바이어 프로필을 기반으로 적합한 거래 파트너를 찾습니다.
    
    **KOTRA API 연동:**
    - 무역사기사례 (리스크 평가)
    - 기업성공사례 (참고 사례)
    
    **FitScore 계산 (0-100):**
    - 기본 점수: 50점
    - HS코드 매칭 (4자리): +20점
    - 가격 호환성: +15점
    - MOQ 호환성: +10점
    - 인증 매칭: +5점/개 (최대 +15점)
    - 무역사기 리스크: -15~0점
    - 성공사례 보너스: +5점
    """
)
async def find_matches(
    request: MatchRequest,
    service: MatchingService = Depends(get_matching_service)
) -> MatchResponse:
    """Find matching partners for a profile."""
    try:
        result = await service.find_matches(request)
        logger.info(
            f"Found {len(result.matches)} matches for {request.profile_type}"
        )
        return result
    except Exception as e:
        logger.error(f"Matching error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/seller",
    response_model=MatchResponse,
    summary="셀러용 바이어 매칭",
    description="셀러가 적합한 바이어를 찾습니다"
)
async def find_buyers_for_seller(
    hs_code: str,
    country: str = "KR",
    price_min: float = 1.0,
    price_max: float = 100.0,
    moq: int = 1000,
    certifications: Optional[str] = None,
    top_n: int = 10,
    include_risk: bool = True,
    service: MatchingService = Depends(get_matching_service)
) -> MatchResponse:
    """Find buyers for a seller via query parameters.
    
    Args:
        hs_code: Product HS Code
        country: Seller's country (default: KR)
        price_min: Minimum price per unit (USD)
        price_max: Maximum price per unit (USD)
        moq: Minimum Order Quantity
        certifications: Comma-separated certifications (e.g., "FDA,ISO,CE")
        top_n: Number of matches to return
        include_risk: Include fraud risk analysis
    """
    # Parse certifications
    certs = []
    if certifications:
        certs = [c.strip().upper() for c in certifications.split(",")]
    
    request = MatchRequest(
        profile_type=ProfileType.SELLER,
        profile={
            "hs_code": hs_code,
            "country": country.upper(),
            "price_range": [price_min, price_max],
            "moq": moq,
            "certifications": certs
        },
        top_n=min(max(1, top_n), 50),
        include_risk_analysis=include_risk
    )
    
    try:
        return await service.find_matches(request)
    except Exception as e:
        logger.error(f"Seller matching error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/buyer",
    response_model=MatchResponse,
    summary="바이어용 셀러 매칭",
    description="바이어가 적합한 셀러를 찾습니다"
)
async def find_sellers_for_buyer(
    hs_code: str,
    country: str,
    budget_min: float = 1.0,
    budget_max: float = 100.0,
    moq: int = 1000,
    required_certs: Optional[str] = None,
    top_n: int = 10,
    include_risk: bool = True,
    service: MatchingService = Depends(get_matching_service)
) -> MatchResponse:
    """Find sellers for a buyer via query parameters.
    
    Args:
        hs_code: Product HS Code
        country: Buyer's country
        budget_min: Minimum budget per unit (USD)
        budget_max: Maximum budget per unit (USD)
        moq: Acceptable MOQ
        required_certs: Required certifications (comma-separated)
        top_n: Number of matches to return
        include_risk: Include fraud risk analysis
    """
    # Parse certifications
    certs = []
    if required_certs:
        certs = [c.strip().upper() for c in required_certs.split(",")]
    
    request = MatchRequest(
        profile_type=ProfileType.BUYER,
        profile={
            "hs_code": hs_code,
            "country": country.upper(),
            "price_range": [budget_min, budget_max],
            "moq": moq,
            "certifications": certs
        },
        top_n=min(max(1, top_n), 50),
        include_risk_analysis=include_risk
    )
    
    try:
        return await service.find_matches(request)
    except Exception as e:
        logger.error(f"Buyer matching error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
