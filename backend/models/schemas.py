"""VALUE-UP AI — 전체 Pydantic 스키마 정의"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────
class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    PENDING = "PENDING"


class SignalColor(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ContactChannel(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    LINKEDIN = "linkedin"


# ── Step 1: HS코드 분석 ──────────────────────────────────────────────────
class HSCodeAnalysisRequest(BaseModel):
    hs_code: str = Field(..., description="HS코드 4~10자리", example="330499")
    target_country: Optional[str] = Field("VN", description="대상국 ISO2코드")
    top_buyers: int = Field(20, ge=5, le=100, description="추출할 바이어 수")


class TradeRecord(BaseModel):
    buyer_name: str
    country: str
    hs_code: str
    trade_value_usd: float
    shipment_count: int
    last_shipment_date: str
    product_description: str


class HSCodeAnalysisResult(BaseModel):
    hs_code: str
    category: str
    product_description: str
    total_importers_found: int
    trade_records: List[TradeRecord]
    market_summary: Dict[str, Any]


# ── Step 2: 거래 이력 필터링 ─────────────────────────────────────────────
class TradeFilterRequest(BaseModel):
    hs_code: str
    country: str = "VN"
    min_shipments: int = Field(5, description="최소 수입 횟수")
    months_back: int = Field(6, description="최근 N개월")
    min_trade_value_usd: float = Field(10000, description="최소 거래금액")


class ActiveBuyer(BaseModel):
    company_name: str
    country: str
    shipment_count: int
    total_trade_value_usd: float
    last_shipment_date: str
    average_order_value_usd: float
    activity_score: float = Field(..., ge=0, le=100)
    hs_codes: List[str]


class TradeFilterResult(BaseModel):
    total_screened: int
    active_buyers_count: int
    active_buyers: List[ActiveBuyer]
    filter_criteria: Dict[str, Any]


# ── Step 3: 바이어 검증 ───────────────────────────────────────────────────
class BuyerVerificationRequest(BaseModel):
    company_name: str
    country: str = "VN"
    tax_id: Optional[str] = None
    registration_number: Optional[str] = None


class VietnamERC(BaseModel):
    company_name_vn: Optional[str]
    company_name_en: Optional[str]
    registration_number: Optional[str]
    incorporation_date: Optional[str]
    legal_type: Optional[str]
    status: VerificationStatus
    raw_response: Optional[str]


class TaxIDVerification(BaseModel):
    tax_id: Optional[str]
    tax_office: Optional[str]
    compliance_status: VerificationStatus  # PASS=정상납세, WARNING=체납이력
    details: Optional[str]


class LegalStatusCheck(BaseModel):
    operating_status: str  # "Đang hoạt động" | "Đã giải thể"
    last_change_date: Optional[str]
    representative_change: bool
    status: VerificationStatus  # PASS=Active, FAIL=Inactive


class BuyerVerificationResult(BaseModel):
    company_name: str
    country: str
    erc_check: VietnamERC
    tax_id_check: TaxIDVerification
    legal_status_check: LegalStatusCheck
    overall_status: VerificationStatus
    risk_score: float = Field(..., ge=0, le=100, description="0=안전, 100=위험")
    recommendation: str


# ── Step 4: 연락처 확보 ───────────────────────────────────────────────────
class ContactEnrichRequest(BaseModel):
    company_name: str
    country: str
    domain: Optional[str] = None
    linkedin_url: Optional[str] = None


class DecisionMakerContact(BaseModel):
    name: Optional[str]
    title: Optional[str]
    email: Optional[str]
    email_confidence: Optional[float]
    phone: Optional[str]
    linkedin_url: Optional[str]
    channel: List[ContactChannel]
    source: str  # "hunter.io" | "apollo.io" | "linkedin" | "estimated"


class ContactEnrichResult(BaseModel):
    company_name: str
    domain: Optional[str]
    contacts: List[DecisionMakerContact]
    total_contacts_found: int
    best_contact: Optional[DecisionMakerContact]


# ── Step 5: 맞춤형 이메일 생성 ───────────────────────────────────────────
class EmailGenerationRequest(BaseModel):
    seller_company: str
    seller_product: str
    hs_code: str
    target_buyer: ActiveBuyer
    contact: DecisionMakerContact
    target_language: str = Field("en", description="이메일 언어 (en/vi/ko)")
    tone: str = Field("professional", description="professional|friendly|formal")
    seller_usp: Optional[str] = None


class GeneratedEmail(BaseModel):
    subject: str
    body: str
    language: str
    personalization_points: List[str]
    call_to_action: str


class EmailGenerationResult(BaseModel):
    buyer_company: str
    contact_name: Optional[str]
    email_address: Optional[str]
    generated_email: GeneratedEmail
    follow_up_sequence: List[str]


# ── Export AI 대시보드 ────────────────────────────────────────────────────
class Layer3FilterInput(BaseModel):
    """사용자가 직접 입력하는 Layer 3 필터 조건"""
    monthly_import_min_usd: float = Field(
        0, ge=0, description="월 수입금액 최솟값 ($) — 0이면 필터 미적용"
    )
    seller_moq_units: int = Field(
        0, ge=0, description="판매자 MOQ (개) — 0이면 MOQ 필터 미적용"
    )
    seller_unit_price_usd: float = Field(
        0, ge=0, description="판매자 단가 ($) — MOQ 금액 환산용"
    )


class FullPipelineRequest(BaseModel):
    hs_code: str
    target_country: str = "VN"
    seller_company: str
    seller_product: str
    seller_usp: Optional[str] = None
    layer3_filter: Optional[Layer3FilterInput] = Field(
        None,
        description="Layer 3 필터 (월 수입금액 최솟값 + MOQ). 미입력 시 필터 없이 통과"
    )


class ReadinessChecklist(BaseModel):
    hs_code_valid: bool
    target_market_identified: bool
    active_buyers_found: bool
    buyers_verified: bool
    contacts_enriched: bool
    emails_ready: bool
    completion_pct: float


class PipelineResult(BaseModel):
    pipeline_id: str
    hs_code: str
    target_country: str
    signal_color: SignalColor
    signal_message: str
    step1_hs_analysis: Optional[HSCodeAnalysisResult]
    step2_filter_result: Optional[TradeFilterResult]
    step3_verified_buyers: List[BuyerVerificationResult]
    step4_contacts: List[ContactEnrichResult]
    step5_emails: List[EmailGenerationResult]
    readiness_checklist: ReadinessChecklist
    execution_time_seconds: float
    total_verified_buyers: int
    total_contacts_found: int
    total_emails_generated: int
