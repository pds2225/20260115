"""Pydantic schemas for API request/response models.

Defines data models for:
- Recommendation API
- Simulation API
- Matching API
- KOTRA API response models

Updated 2026-01-26:
- Added explanation field with kotra_status, fallback_used, confidence, data_coverage
- Added required_certs, preferred_certs for certification matching
- Added MOQ gate fields (moq_gate_passed, moq_score, order_value_usd)
- Added compliance_status for export blocklist
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


# =============================================================================
# Explanation & Confidence Models
# =============================================================================

class DataCoverage(BaseModel):
    """데이터 커버리지 정보."""
    missing_rate: float = Field(0.0, ge=0, le=1, description="결측률 (0-1)")
    missing_fields: List[str] = Field(default=[], description="결측 필드 목록")
    imputation_methods: Dict[str, str] = Field(default={}, description="대체 방법")


class Explanation(BaseModel):
    """결과 설명 정보."""
    kotra_status: str = Field("ok", description="KOTRA API 상태 (ok/unavailable)")
    fallback_used: bool = Field(False, description="fallback 데이터 사용 여부")
    confidence: float = Field(1.0, ge=0, le=1, description="신뢰도 (0-1)")
    data_coverage: DataCoverage = Field(default_factory=DataCoverage)
    warning: Optional[str] = Field(None, description="경고 메시지")
    interpretation: Optional[str] = Field(None, description="신뢰도 해석")


class ComplianceInfo(BaseModel):
    """규정 준수 정보."""
    compliance_status: str = Field("ok", description="ok/restricted/blocked")
    reason: Optional[str] = Field(None, description="제한/차단 사유")
    score_penalty: int = Field(0, description="점수 페널티")
    warning: Optional[str] = Field(None, description="경고 메시지")


# =============================================================================
# Enums
# =============================================================================

class ExportGoal(str, Enum):
    """Export strategy goal types."""
    NEW_MARKET = "new_market"  # 신시장 발굴
    MARKET_EXPANSION = "market_expansion"  # 시장 확대
    RISK_DIVERSIFICATION = "risk_diversification"  # 리스크 분산


class RiskLevel(str, Enum):
    """Risk level classifications."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SAFE = "SAFE"


class ProfileType(str, Enum):
    """Profile type for matching."""
    SELLER = "seller"
    BUYER = "buyer"


# =============================================================================
# Recommendation API Models
# =============================================================================

class RecommendationRequest(BaseModel):
    """Request model for /recommend endpoint."""
    
    hs_code: str = Field(
        ..., 
        description="HS Code (4-6 digits)",
        min_length=4,
        max_length=10,
        examples=["330499", "300490"]
    )
    current_export_countries: List[str] = Field(
        default=[],
        description="Current export countries (ISO 2-letter codes)",
        examples=[["US", "JP", "CN"]]
    )
    export_scale: Optional[str] = Field(
        default=None,
        description="Export scale category",
        examples=["small", "medium", "large"]
    )
    goal: ExportGoal = Field(
        default=ExportGoal.NEW_MARKET,
        description="Export strategy goal"
    )
    top_n: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of recommendations to return"
    )


class CountryRecommendation(BaseModel):
    """Single country recommendation."""
    
    rank: int = Field(..., description="Recommendation rank")
    country_code: str = Field(..., description="ISO 2-letter country code")
    country_name: str = Field(..., description="Country name in Korean")
    success_score: float = Field(
        ..., 
        ge=0, 
        le=30,  # Updated: 실제 API 데이터 범위 (1.04 ~ 25.65)
        description="ML-predicted success score (EXP_BHRC_SCR, 0-30 range)"
    )
    success_probability: float = Field(
        ...,
        ge=0,
        le=1,
        description="Normalized success probability (0-1)"
    )
    
    # Economic indicators
    gdp: Optional[float] = Field(None, description="GDP in USD billions")
    growth_rate: Optional[float] = Field(None, description="Economic growth rate %")
    risk_grade: Optional[str] = Field(None, description="Risk grade (A-E)")
    
    # Supporting data
    market_characteristics: Optional[str] = Field(None, description="Market overview")
    promising_products: List[str] = Field(default=[], description="Promising product list")
    recent_trends: List[Dict[str, Any]] = Field(default=[], description="Recent market trends")
    success_cases: List[Dict[str, Any]] = Field(default=[], description="Relevant success cases")
    
    # Calculation details
    score_breakdown: Dict[str, float] = Field(
        default={},
        description="Score calculation breakdown"
    )

    # Updated 2026-01-26: compliance 추가
    compliance: Optional[ComplianceInfo] = Field(None, description="규정 준수 정보")


class RecommendationResponse(BaseModel):
    """Response model for /recommend endpoint."""

    hs_code: str
    goal: ExportGoal
    total_countries_analyzed: int
    recommendations: List[CountryRecommendation]
    data_sources: List[str] = Field(
        default=["KOTRA 수출유망추천정보", "KOTRA 국가정보", "KOTRA 상품DB"],
        description="Data sources used"
    )
    # Updated 2026-01-26: explanation 추가
    explanation: Explanation = Field(default_factory=Explanation)
    excluded_countries: List[Dict[str, str]] = Field(
        default=[],
        description="제외된 국가 목록 (blocked/restricted)"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Simulation API Models
# =============================================================================

class SimulationRequest(BaseModel):
    """Request model for /simulate endpoint."""
    
    hs_code: str = Field(..., description="HS Code (4-6 digits)")
    target_country: str = Field(..., description="Target country code (ISO 2-letter)")
    
    # Company parameters
    price_per_unit: float = Field(
        ..., 
        gt=0,
        description="Price per unit in USD"
    )
    moq: int = Field(
        ...,
        gt=0,
        description="Minimum Order Quantity"
    )
    annual_capacity: int = Field(
        ...,
        gt=0,
        description="Annual production capacity"
    )
    
    # Optional market parameters
    market_size_estimate: Optional[float] = Field(
        None,
        description="Estimated market size in USD millions"
    )
    
    # Risk adjustments
    include_news_risk: bool = Field(
        default=True,
        description="Include news-based risk analysis"
    )


class SimulationResult(BaseModel):
    """Response model for /simulate endpoint."""
    
    target_country: str
    country_name: str
    hs_code: str
    
    # Revenue projections
    estimated_revenue_min: float = Field(
        ..., 
        description="Minimum estimated annual revenue (USD)"
    )
    estimated_revenue_max: float = Field(
        ...,
        description="Maximum estimated annual revenue (USD)"
    )
    
    # Probability
    success_probability: float = Field(
        ...,
        ge=0,
        le=1,
        description="Success probability (0-1)"
    )
    
    # Market analysis
    market_size: Optional[float] = Field(None, description="Market size estimate")
    market_share_min: float = Field(..., description="Minimum market share %")
    market_share_max: float = Field(..., description="Maximum market share %")
    
    # Risk analysis
    news_risk_adjustment: Optional[Dict[str, Any]] = Field(
        None,
        description="News-based risk analysis"
    )
    economic_indicators: Dict[str, Any] = Field(
        default={},
        description="Country economic indicators"
    )
    
    # Breakdown
    calculation_breakdown: Dict[str, Any] = Field(
        default={},
        description="Detailed calculation breakdown"
    )

    # Updated 2026-01-26: explanation + compliance 추가
    explanation: Explanation = Field(default_factory=Explanation)
    compliance: Optional[ComplianceInfo] = Field(None, description="규정 준수 정보")

    # Metadata
    data_sources: List[str] = Field(default=[])
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Matching API Models
# =============================================================================

class ProfileBase(BaseModel):
    """Base profile model for buyer/seller."""

    hs_code: str = Field(..., description="Product HS Code")
    country: str = Field(..., description="Country code")
    price_range: List[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Price range [min, max] in USD"
    )
    moq: int = Field(..., gt=0, description="MOQ requirement")
    certifications: List[str] = Field(
        default=[],
        description="Available certifications (deprecated, use required_certs/preferred_certs)"
    )
    # Updated 2026-01-26: required vs preferred 인증 분리
    required_certs: List[str] = Field(
        default=[],
        description="필수 인증 목록 (미충족 시 탈락)"
    )
    preferred_certs: List[str] = Field(
        default=[],
        description="선호 인증 목록 (가점)"
    )
    # MOQ 고도화
    annual_capacity: Optional[int] = Field(None, gt=0, description="연간 생산 능력")
    min_order_usd: Optional[float] = Field(None, ge=0, description="최소 주문 금액 (USD)")


class SellerProfile(ProfileBase):
    """Seller profile for matching."""
    
    id: str = Field(default="", description="Seller ID")
    company_name: Optional[str] = Field(None, description="Company name")
    export_experience_years: int = Field(default=0, description="Export experience")
    languages: List[str] = Field(default=["ko"], description="Supported languages")


class BuyerProfile(ProfileBase):
    """Buyer profile for matching."""
    
    id: str = Field(default="", description="Buyer ID")
    company_name: Optional[str] = Field(None, description="Company name")
    import_volume_annual: Optional[int] = Field(None, description="Annual import volume")
    payment_terms: List[str] = Field(default=[], description="Accepted payment terms")


class MatchRequest(BaseModel):
    """Request model for /match endpoint."""
    
    profile_type: ProfileType = Field(
        ...,
        description="Type of profile being submitted"
    )
    profile: Dict[str, Any] = Field(
        ...,
        description="Profile data (SellerProfile or BuyerProfile)"
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of matches to return"
    )
    include_risk_analysis: bool = Field(
        default=True,
        description="Include fraud risk analysis"
    )


class MatchResult(BaseModel):
    """Single match result."""

    partner_id: str
    partner_type: ProfileType
    company_name: Optional[str] = None
    country: str
    country_name: Optional[str] = None

    # Scoring
    fit_score: float = Field(..., ge=0, le=100, description="Fit score (0-100)")
    score_breakdown: Dict[str, Any] = Field(
        default={},
        description="Score component breakdown"
    )

    # Match details
    hs_code_match: bool = Field(default=False)
    price_compatible: bool = Field(default=False)
    moq_compatible: bool = Field(default=False)
    certification_match: List[str] = Field(default=[])

    # Updated 2026-01-26: MOQ 고도화 필드
    moq_gate_passed: bool = Field(True, description="MOQ Hard Gate 통과 여부")
    moq_score: float = Field(1.0, ge=0, le=1, description="MOQ Soft Score (0-1)")
    order_value_usd: Optional[float] = Field(None, description="예상 주문 금액 (USD)")

    # Updated 2026-01-26: 인증 매칭 개선
    missing_required_certs: List[str] = Field(default=[], description="미충족 필수 인증")
    matched_preferred_certs: List[str] = Field(default=[], description="매칭된 선호 인증")

    # Risk analysis
    fraud_risk: Optional[Dict[str, Any]] = Field(None, description="Fraud risk info")

    # Compliance
    compliance: Optional[ComplianceInfo] = Field(None, description="규정 준수 정보")

    # Reference cases
    success_cases: List[Dict[str, Any]] = Field(default=[], description="Relevant success cases")


class MatchResponse(BaseModel):
    """Response model for /match endpoint."""

    profile_type: ProfileType
    total_candidates: int
    matches: List[MatchResult]

    # Risk summary
    countries_analyzed: List[str] = Field(default=[])
    high_risk_countries: List[str] = Field(default=[])
    blocked_countries: List[str] = Field(default=[], description="차단된 국가 목록")

    # Updated 2026-01-26: explanation 추가
    explanation: Explanation = Field(default_factory=Explanation)

    # Metadata
    data_sources: List[str] = Field(
        default=["KOTRA 무역사기사례", "KOTRA 기업성공사례"],
        description="Data sources used"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# KOTRA API Response Models (Internal)
# =============================================================================

class KotraExportRecommendation(BaseModel):
    """KOTRA Export Recommendation API response item."""
    
    HSCD: str = Field(..., description="HS Code")
    NAT_NAME: str = Field(..., description="Country name")
    EXPORTSCALE: Optional[str] = Field(None, description="Export scale")
    EXP_BHRC_SCR: float = Field(..., description="Export success score")
    UPDT_DT: Optional[str] = Field(None, description="Update datetime")


class KotraCountryInfo(BaseModel):
    """KOTRA Country Info API response (simplified)."""
    
    natnNm: str = Field(..., description="Country name")
    cptlNm: Optional[str] = Field(None, description="Capital")
    poplCnt: Optional[int] = Field(None, description="Population")
    gdp: Optional[float] = Field(None, description="GDP")
    growth_rate: Optional[float] = Field(None, description="Growth rate")
    risk_grade: Optional[str] = Field(None, description="Risk grade")


class KotraNewsItem(BaseModel):
    """KOTRA Overseas News API response item."""
    
    nttSn: Optional[str] = Field(None, description="Article ID")
    natNm: Optional[str] = Field(None, description="Country name")
    title: Optional[str] = Field(None, description="Title")
    cntnt: Optional[str] = Field(None, description="Content")
    wrtDt: Optional[str] = Field(None, description="Written date")


class KotraFraudCase(BaseModel):
    """KOTRA Fraud Case API response item."""
    
    nttSn: Optional[str] = Field(None, description="Case ID")
    natNm: Optional[str] = Field(None, description="Country name")
    title: Optional[str] = Field(None, description="Case title")
    fraudTypNm: Optional[str] = Field(None, description="Fraud type")
    prvntMthd: Optional[str] = Field(None, description="Prevention method")


class KotraSuccessCase(BaseModel):
    """KOTRA Success Case API response item."""
    
    nttSn: Optional[str] = Field(None, description="Case ID")
    natNm: Optional[str] = Field(None, description="Country name")
    corpNm: Optional[str] = Field(None, description="Company name")
    indutyNm: Optional[str] = Field(None, description="Industry")
    title: Optional[str] = Field(None, description="Case title")
    entryTypNm: Optional[str] = Field(None, description="Entry type")


# =============================================================================
# Health Check & Info Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = "healthy"
    version: str = "1.0.0"
    services: Dict[str, str] = Field(default={})


class APIInfo(BaseModel):
    """API information response."""
    
    name: str = "Global Export Intelligence Platform"
    version: str = "1.0.0"
    description: str = "AI-powered export market recommendation platform"
    endpoints: List[Dict[str, str]] = Field(default=[])
    kotra_apis_integrated: List[str] = Field(
        default=[
            "수출유망추천정보",
            "국가정보",
            "상품DB",
            "해외시장뉴스",
            "무역사기사례",
            "기업성공사례"
        ]
    )
