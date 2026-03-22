"""FastAPI 라우터 v2 — VALUE-UP AI 4중 검증 파이프라인 API"""
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List
from backend.models.schemas import (
    FullPipelineRequest, HSCodeAnalysisRequest, TradeFilterRequest,
    BuyerVerificationRequest, ContactEnrichRequest,
)
from backend.services.four_layer_matcher import FourLayerMatcher
from backend.services.pipeline_orchestrator import AutomationPipeline   # v1 호환
from backend.services.step1_hs_analyzer import HSCodeAnalyzer
from backend.services.step2_trade_filter import TradeHistoryFilter
from backend.services.step3_buyer_verifier import BuyerVerifier
from backend.services.step4_contact_enricher import ContactEnricher
from backend.services.layer2_credit_verifier import CreditVerifier
from backend.services.layer3_import_volume import ImportVolumeVerifier
from backend.services.hs_recommender import HSCodeRecommender
from backend.services.supported_countries import get_supported_countries, get_country_by_hs
from backend.services.data_source_manager import get_source_status
from backend.models.schemas import ActiveBuyer


# ── 추가 요청 모델 ─────────────────────────────────────────────────────────
class HunterSearchRequest(BaseModel):
    domain: str = Field(..., description="회사 도메인 (예: wangfoodusa.com)")
    company: str = Field("", description="회사명 (도메인 없을 때 보조)")
    limit: int = Field(10, ge=1, le=50, description="최대 결과 수")
    department: str = Field("", description="부서 필터 (purchase / management / 빈값=전체)")


class EmailSendRequest(BaseModel):
    to_address: str = Field(..., description="수신자 이메일")
    subject: str = Field(..., description="제목")
    body_text: str = Field(..., description="본문 (플레인 텍스트)")
    buyer_company: str = Field("", description="바이어 회사명 (추적용)")


class OutreachBatchRequest(BaseModel):
    """4중 파이프라인 통과 바이어에게 일괄 아웃리치 이메일 발송"""
    seller_company: str
    seller_product: str
    certifications: List[str] = Field(default_factory=list)
    moq: int = 0
    unit_price_usd: float = 0.0
    language: str = "en"
    buyers: List[dict]  # [{"company": "...", "email": "...", "name": "...", "grade": "A", ...}]

router = APIRouter(prefix="/api/v1", tags=["VALUE-UP AI"])

# 서비스 인스턴스
four_layer = FourLayerMatcher()
pipeline_v1 = AutomationPipeline()
hs_analyzer = HSCodeAnalyzer()
trade_filter = TradeHistoryFilter()
buyer_verifier = BuyerVerifier()
contact_enricher = ContactEnricher()
credit_verifier = CreditVerifier()
volume_verifier = ImportVolumeVerifier()
hs_recommender = HSCodeRecommender()


# ══════════════════════════════════════════════════════════════════
# 입력 보조: HS 코드 추천 & 지원 국가 조회
# ══════════════════════════════════════════════════════════════════
@router.get(
    "/hs/recommend",
    summary="🔍 제품명 → HS 코드 추천 (한국어·영어 모두 가능)",
    tags=["입력 보조"],
)
def recommend_hs_code(
    q: str = Query(..., description="제품명. 예: '스킨케어', 'vegan serum', '자동차부품'"),
    top_k: int = Query(5, ge=1, le=10, description="추천 개수 (기본 5개)"),
):
    """
    ## 제품명 → HS 코드 추천

    - 한국어·영어 모두 입력 가능
    - 각 후보에 HS 코드, 품목명, 현재 DB에서 조회 가능한 국가 목록 포함
    - 사용자는 목록에서 원하는 HS 코드를 선택하여 파이프라인 실행

    **예시:** `q=스킨케어` → 330499, 330491, 340111 등 추천
    """
    return hs_recommender.recommend(q, top_k)


@router.get(
    "/countries",
    summary="🌍 지원 국가 전체 목록",
    tags=["입력 보조"],
)
def list_supported_countries():
    """
    ## 현재 DB 기준 사용 가능한 국가 목록

    각 국가별:
    - 데이터 품질 (Full / Partial / Limited)
    - 조회 가능한 HS 코드 목록
    - 신용등급 / K-SURE 가입 가능 여부
    - 주의사항
    """
    return get_supported_countries()


@router.get(
    "/countries/by-hs/{hs_code}",
    summary="🌍 HS 코드 기준 지원 국가 필터",
    tags=["입력 보조"],
)
def countries_by_hs(hs_code: str):
    """
    특정 HS 코드에 대해 데이터가 있는 국가만 반환.
    HS 코드 선택 후 진출 국가 드롭다운 필터링에 사용.
    """
    countries = get_country_by_hs(hs_code)
    return {
        "hs_code": hs_code,
        "available_countries": countries,
        "count": len(countries),
    }


@router.get(
    "/data-sources/status",
    summary="🔌 데이터 소스 연동 현황",
    tags=["입력 보조"],
)
def data_source_status():
    """
    ## 현재 데이터 소스 연동 상태

    각 소스별:
    - 연동 방식 (LIVE_API / CSV_DB / PATTERN_ENGINE)
    - 보유 레코드 수
    - 유료 API 키 설정 시 자동 전환 가능한 소스
    """
    return get_source_status()


@router.get(
    "/nipa/buyers",
    summary="🌐 NIPA 글로벌ICT포털 해외바이어 검색",
    tags=["바이어 검색"],
)
def search_nipa_buyers(
    country: str = "",
    keyword: str = "",
    limit: int = 20,
):
    """
    ## NIPA 글로벌ICT포털 해외바이어정보 검색
    - **총 1,853건** | ICT/IT 분야 특화
    - 국가별 분포: UAE/두바이 123건, 미국 40건, 싱가포르 60건, 베트남 47건 등
    - 제공 필드: 회사명, 국가, 전화번호, 등록일, 상세링크
    - **country**: ISO2 코드 또는 국가명 (예: US, 미국, VN, 베트남)
    - **keyword**: 회사명 검색어
    """
    from backend.services.data_source_manager import get_nipa_buyers
    results = get_nipa_buyers(country=country, keyword=keyword, limit=limit)
    return {
        "count": len(results),
        "country_filter": country or "전체",
        "keyword_filter": keyword or "없음",
        "source": "NIPA_글로벌ICT포털_해외바이어정보",
        "note": "ICT/IT 업종 특화 바이어. 이메일은 상세링크에서 확인 가능.",
        "buyers": results,
    }


@router.get(
    "/ksure/buyers",
    summary="🛡️ K-SURE 바이어검색 API (한국무역보험공사)",
    tags=["바이어 검색"],
)
def search_ksure_buyers_endpoint(
    country: str = "US",
    hs_code: str = "330499",
    prod_nm: str = "",
    max_buyers: int = 50,
):
    """
    ## K-SURE 바이어검색 API — HS코드 기반 실시간 조회
    - **50개국 지원** | 화장품·뷰티 미국 739건, 베트남 209건 등
    - HS코드 기반 업종 키워드 자동 매핑 (또는 직접 입력)
    - 제공 필드: 바이어명, 업종명, 품목명, K-SURE 대상자번호
    - **country**: ISO2 코드 (예: US, VN, TH, JP, SG, MY, ID, IN, DE, GB)
    - **hs_code**: HS 6자리 코드
    - **prod_nm**: 품목 키워드 직접 입력 (비워두면 HS코드 자동 변환)
    """
    from backend.services.data_source_manager import search_ksure_buyers
    buyers = search_ksure_buyers(
        country_iso2=country,
        hs_code=hs_code,
        prod_nm=prod_nm if prod_nm else None,
        max_buyers=max_buyers,
    )
    return {
        "count": len(buyers),
        "country": country,
        "hs_code": hs_code,
        "source": "K-SURE_바이어검색_API",
        "note": "바이어명·업종명·품목명 제공. 이메일은 KSURE 화장품DB 또는 Hunter.io 병합 필요.",
        "buyers": buyers,
    }


@router.post(
    "/pipeline/v2/run",
    summary="🚀 4중 검증 파이프라인 (Layer1~4 AND 필터 + FitScore™)",
    tags=["4중 검증 파이프라인"],
)
async def run_four_layer_pipeline(req: FullPipelineRequest):
    """
    ## VALUE-UP AI 4중 검증 매칭

    **스크린샷 목표 구조 완전 구현:**
    - Layer 1: 활동 이력 (세관 B/L + KOTRA + UN Comtrade → 빈도 점수화 월/분기/반기)
    - Layer 2: 대금 지급 (Coface 스타일 + K-SURE + 무역사기 DB → D등급 이하 자동 제외)
    - Layer 3: 수입 규모 (HS코드 통계 + Buying Power 점수 → 최소 $5만 필터)
    - Layer 4: 담당자 확보 (Hunter.io + Apollo.io + Clay/Lusha → 이메일 3중 검증)

    **4개 Layer AND 통과 바이어만 최종 출력 + FitScore™ 순위 정렬**

    ### FitScore 산출
    - Layer 1 (활동) × 40%
    - Layer 2 (신용) × 30%
    - Layer 3 (규모) × 20%
    - Layer 4 (연락처) × 10%
    """
    try:
        return await four_layer.run(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# v1 호환 (기존 5단계 파이프라인)
# ══════════════════════════════════════════════════════════════════
@router.post(
    "/pipeline/run",
    summary="5단계 파이프라인 v1 (호환)",
    tags=["5단계 파이프라인 v1"],
)
async def run_pipeline_v1(req: FullPipelineRequest):
    try:
        return await pipeline_v1.run(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# 개별 Layer API
# ══════════════════════════════════════════════════════════════════
@router.post("/layer1/analyze", summary="Layer 1: 활동 이력 분석")
async def layer1_analyze(req: HSCodeAnalysisRequest):
    try:
        return await hs_analyzer.analyze(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/layer2/credit", summary="Layer 2: 대금 지급 신용 검증")
async def layer2_credit(company_name: str, country: str = "VN"):
    try:
        return await credit_verifier.verify(company_name, country)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/layer3/volume", summary="Layer 3: 수입 규모 & Buying Power")
async def layer3_volume(
    company_name: str,
    country: str = "VN",
    hs_code: str = "330499",
    trade_value_usd: float = 100000,
    shipment_count: int = 6,
):
    try:
        return await volume_verifier.verify(
            company_name, country, hs_code, trade_value_usd, shipment_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/layer4/contact", summary="Layer 4: 담당자 확보 + 이메일 3중 검증")
async def layer4_contact(req: ContactEnrichRequest):
    try:
        buyer = ActiveBuyer(
            company_name=req.company_name,
            country=req.country or "VN",
            shipment_count=0,
            total_trade_value_usd=0,
            last_shipment_date="",
            average_order_value_usd=0,
            activity_score=0,
            hs_codes=[],
        )
        return await contact_enricher.enrich(buyer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step3/verify", summary="베트남 법인 실사 (ERC·TaxID·법적상태 3중)")
async def verify_vietnam_erc(req: BuyerVerificationRequest):
    try:
        return await buyer_verifier.verify_single(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="헬스 체크")
async def health():
    return {
        "status": "ok",
        "service": "VALUE-UP AI v2.0",
        "pipeline": "4중 검증 (Layer1~4)",
        "features": {
            "layer1": "활동 이력 (UN Comtrade + KOTRA + Volza)",
            "layer2": "대금 지급 (Coface + K-SURE + 무역사기DB)",
            "layer3": "수입 규모 (Buying Power Score)",
            "layer4": "담당자 확보 (이메일 3중 검증)",
            "fit_score": "4중 통합 FitScore™",
        },
    }


# ══════════════════════════════════════════════════════════════════
# ✅ 실연동 도구 — Hunter.io / Gmail (실제 작동 확인)
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/hunter/search",
    summary="✅ Hunter.io 실연동 — 도메인으로 담당자 이메일 즉시 확보",
    tags=["실연동 도구"],
)
async def hunter_domain_search(req: HunterSearchRequest):
    """
    ## Hunter.io 도메인 검색 (✅ 실제 작동 확인)

    **확인된 사실:** wangfoodusa.com → 10명 이메일 즉시 확보

    ### 환경변수 설정 필요
    ```
    HUNTER_IO_API_KEY=your_key_here
    ```
    - 무료 티어: 월 25건 검색
    - 유료 플랜: 월 500건 ~ 무제한

    ### 반환값
    - 담당자 이름, 직함, 이메일, 신뢰도 (0~100%)
    - 구매결정권자 우선 정렬 (buyer / procurement / director 등)
    """
    try:
        from backend.services.hunter_client import HunterClient
        client = HunterClient()

        if not client.is_available:
            return {
                "success": False,
                "error": "HUNTER_IO_API_KEY 환경변수가 설정되지 않았습니다.",
                "setup_guide": "https://hunter.io/api-documentation/v2",
                "free_tier": "월 25건 무료",
            }

        result = await client.domain_search(
            domain=req.domain,
            company=req.company,
            limit=req.limit,
            department=req.department,
        )

        return {
            "domain": result.domain,
            "organization": result.organization,
            "total_emails": result.total_emails,
            "emails_found": len(result.emails),
            "contacts": [
                {
                    "email": c.value,
                    "name": c.full_name,
                    "position": c.position,
                    "department": c.department,
                    "confidence_pct": c.confidence,
                    "is_decision_maker": c.is_decision_maker,
                    "linkedin": c.linkedin,
                    "phone": c.phone_number,
                }
                for c in result.emails
            ],
            "decision_makers": [c.full_name for c in result.decision_makers],
            "best_contact": {
                "email": result.best_contact.value,
                "name": result.best_contact.full_name,
                "confidence_pct": result.best_contact.confidence,
            } if result.best_contact else None,
            "error": result.error,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/gmail/preview",
    summary="✅ Gmail 발송 미리보기 — 바이어 아웃리치 이메일 초안",
    tags=["실연동 도구"],
)
async def gmail_preview(req: EmailSendRequest):
    """
    ## Gmail 이메일 미리보기

    발송하지 않고 이메일 내용을 미리 확인합니다.
    환경변수 미설정 시에도 미리보기 가능.
    """
    from backend.services.gmail_sender import GmailSender, EmailMessage
    sender = GmailSender()
    msg = EmailMessage(
        to_address=req.to_address,
        subject=req.subject,
        body_text=req.body_text,
        tags=[req.buyer_company],
    )
    return {
        "preview": sender.preview(msg),
        "sender_configured": sender.is_available,
        "setup_guide": "GMAIL_ADDRESS + GMAIL_APP_PASSWORD 환경변수 설정 필요",
    }


@router.post(
    "/gmail/send",
    summary="✅ Gmail 실제 발송 — 아웃리치 이메일 즉시 발송",
    tags=["실연동 도구"],
)
async def gmail_send(req: EmailSendRequest):
    """
    ## Gmail 이메일 실제 발송 (✅ 실제 작동 확인)

    **확인된 사실:** ImportGenius·TradeInt·Panjiva 3개사 초안 실제 발송 성공

    ### 환경변수 설정 필요
    ```
    GMAIL_ADDRESS=your@gmail.com
    GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
    ```
    Gmail 앱 비밀번호: https://myaccount.google.com/security
    """
    from backend.services.gmail_sender import GmailSender, EmailMessage
    sender = GmailSender()

    if not sender.is_available:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Gmail 인증 정보 미설정",
                "setup": "GMAIL_ADDRESS + GMAIL_APP_PASSWORD 환경변수 설정 필요",
                "guide": "https://myaccount.google.com/security → 앱 비밀번호",
            }
        )

    msg = EmailMessage(
        to_address=req.to_address,
        subject=req.subject,
        body_text=req.body_text,
        tags=[req.buyer_company],
    )
    result = sender.send(msg)
    return {
        "success": result.success,
        "to": result.to_address,
        "message_id": result.message_id,
        "error": result.error,
    }


@router.post(
    "/outreach/batch",
    summary="🚀 아웃리치 이메일 일괄 발송 (4중 통과 바이어 전체)",
    tags=["실연동 도구"],
)
async def outreach_batch(req: OutreachBatchRequest):
    """
    ## 4중 파이프라인 통과 바이어에게 일괄 아웃리치 이메일 발송

    파이프라인 결과에서 바이어 목록을 그대로 붙여넣어 일괄 발송.
    Gmail 미설정 시 미리보기 모드로 전환.

    ### 사용 방법
    1. `/pipeline/v2/run` 실행 → `verified_buyers` 복사
    2. 본 API에 붙여넣기 → 전체 발송
    """
    from backend.services.gmail_sender import GmailSender, build_outreach_email
    sender = GmailSender()
    preview_only = not sender.is_available

    results = []
    for buyer in req.buyers:
        msg = build_outreach_email(
            sender_company=req.seller_company,
            sender_product=req.seller_product,
            buyer_company=buyer.get("company", ""),
            contact_name=buyer.get("name", ""),
            contact_email=buyer.get("email", ""),
            monthly_volume_usd=float(buyer.get("monthly_volume_usd", 0)),
            credit_grade=buyer.get("grade", "A"),
            payment_terms=buyer.get("payment_terms", "T/T 30일"),
            certifications=req.certifications,
            moq=req.moq,
            unit_price_usd=req.unit_price_usd,
            language=req.language,
        )

        if preview_only:
            results.append({
                "company": buyer.get("company"),
                "to": msg.to_address,
                "subject": msg.subject,
                "preview": msg.body_text[:300] + "...",
                "mode": "PREVIEW",
            })
        else:
            result = sender.send(msg)
            results.append({
                "company": buyer.get("company"),
                "to": result.to_address,
                "success": result.success,
                "error": result.error,
                "mode": "SENT",
            })

    return {
        "mode": "PREVIEW" if preview_only else "SENT",
        "total": len(results),
        "success_count": sum(1 for r in results if r.get("success", preview_only)),
        "results": results,
        "gmail_setup_required": preview_only,
    }
