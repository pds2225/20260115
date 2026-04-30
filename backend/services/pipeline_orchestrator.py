"""통합 파이프라인 오케스트레이터
5분 이내 전 과정 자동화:
HS코드 분석 → 거래이력 필터링 → 바이어 검증 → 연락처 확보 → 이메일 생성
"""
import asyncio
import time
import uuid
from backend.models.schemas import (
    FullPipelineRequest, PipelineResult, SignalColor,
    ReadinessChecklist, HSCodeAnalysisRequest, TradeFilterRequest,
    VerificationStatus
)
from backend.services.step1_hs_analyzer import HSCodeAnalyzer
from backend.services.step2_trade_filter import TradeHistoryFilter
from backend.services.step3_buyer_verifier import BuyerVerifier
from backend.services.step4_contact_enricher import ContactEnricher
from backend.services.step5_email_generator import EmailGenerator


def _compute_signal(
    verified_count: int,
    contact_count: int,
    active_buyer_count: int,
) -> tuple[SignalColor, str]:
    """진입 가능성 신호등 산출"""
    if verified_count >= 3 and contact_count >= 3:
        return SignalColor.GREEN, f"✅ 즉시 진입 가능 — {verified_count}개 검증 완료 바이어, {contact_count}개 컨택 확보"
    elif verified_count >= 1 and contact_count >= 1:
        return SignalColor.YELLOW, f"⚠️ 진입 가능 (주의) — {verified_count}개 바이어 검증, 추가 실사 권장"
    else:
        return SignalColor.RED, f"🚫 진입 어려움 — 검증 바이어 부족 ({active_buyer_count}개 스크리닝 완료)"


def _build_checklist(result: PipelineResult) -> ReadinessChecklist:
    items = {
        "hs_code_valid": result.step1_hs_analysis is not None,
        "target_market_identified": (
            result.step1_hs_analysis is not None
            and result.step1_hs_analysis.total_importers_found > 0
        ),
        "active_buyers_found": (
            result.step2_filter_result is not None
            and result.step2_filter_result.active_buyers_count > 0
        ),
        "buyers_verified": len(result.step3_verified_buyers) > 0,
        "contacts_enriched": result.total_contacts_found > 0,
        "emails_ready": result.total_emails_generated > 0,
    }
    pct = sum(items.values()) / len(items) * 100
    return ReadinessChecklist(**items, completion_pct=round(pct, 1))


class AutomationPipeline:
    """5단계 자동화 파이프라인"""

    def __init__(self):
        self.hs_analyzer = HSCodeAnalyzer()
        self.trade_filter = TradeHistoryFilter()
        self.buyer_verifier = BuyerVerifier()
        self.contact_enricher = ContactEnricher()
        self.email_generator = EmailGenerator()

    async def run(self, req: FullPipelineRequest) -> PipelineResult:
        start_time = time.time()
        pipeline_id = str(uuid.uuid4())[:8].upper()

        # ── Step 1: HS코드 분석 ────────────────────────────────────────
        print(f"[{pipeline_id}] Step 1: HS코드 분석 시작 ({req.hs_code})")
        hs_result = await self.hs_analyzer.analyze(
            HSCodeAnalysisRequest(
                hs_code=req.hs_code,
                target_country=req.target_country,
                top_buyers=50,
            )
        )
        print(f"[{pipeline_id}] Step 1 완료 — {hs_result.total_importers_found}개 수입자 발견")

        # ── Step 2: 거래 이력 필터링 ─────────────────────────────────
        print(f"[{pipeline_id}] Step 2: 거래 이력 필터링 시작")
        filter_result = self.trade_filter.filter(
            TradeFilterRequest(
                hs_code=req.hs_code,
                country=req.target_country,
                min_shipments=5,
                months_back=6,
                min_trade_value_usd=50000,
            ),
            hs_result,
        )
        print(f"[{pipeline_id}] Step 2 완료 — {filter_result.active_buyers_count}개 활성 바이어 선별")

        # 최대 max_buyers 개만 처리
        target_buyers = filter_result.active_buyers[:req.max_buyers]

        # ── Step 3 + 4 병렬 실행 ─────────────────────────────────────
        print(f"[{pipeline_id}] Step 3+4: 바이어 검증 + 연락처 확보 병렬 실행")
        verify_task = self.buyer_verifier.verify_batch(target_buyers)
        enrich_task = self.contact_enricher.enrich_batch(target_buyers)
        verified_results, contact_results = await asyncio.gather(verify_task, enrich_task)

        # PASS/WARNING만 유지 (FAIL 제외)
        safe_verified = [
            v for v in verified_results
            if v.overall_status != VerificationStatus.FAIL
        ]
        safe_buyers = [
            b for b, v in zip(target_buyers, verified_results)
            if v.overall_status != VerificationStatus.FAIL
        ]
        safe_contacts = [
            c for c, v in zip(contact_results, verified_results)
            if v.overall_status != VerificationStatus.FAIL
        ]

        print(f"[{pipeline_id}] Step 3 완료 — {len(safe_verified)}/{len(target_buyers)}개 검증 통과")
        total_contacts = sum(c.total_contacts_found for c in safe_contacts)
        print(f"[{pipeline_id}] Step 4 완료 — 총 {total_contacts}개 연락처 확보")

        # ── Step 5: 이메일 생성 ───────────────────────────────────────
        print(f"[{pipeline_id}] Step 5: 맞춤형 이메일 생성 시작")
        email_results = await self.email_generator.generate_batch(
            buyers=safe_buyers,
            contact_results=safe_contacts,
            seller_company=req.seller_company,
            seller_product=req.seller_product,
            hs_code=req.hs_code,
            language=req.email_language,
            seller_usp=req.seller_usp,
        )
        print(f"[{pipeline_id}] Step 5 완료 — {len(email_results)}개 이메일 생성")

        elapsed = round(time.time() - start_time, 2)
        signal_color, signal_message = _compute_signal(
            len(safe_verified), total_contacts, filter_result.active_buyers_count
        )

        result = PipelineResult(
            pipeline_id=pipeline_id,
            hs_code=req.hs_code,
            target_country=req.target_country,
            signal_color=signal_color,
            signal_message=signal_message,
            step1_hs_analysis=hs_result,
            step2_filter_result=filter_result,
            step3_verified_buyers=safe_verified,
            step4_contacts=safe_contacts,
            step5_emails=email_results,
            readiness_checklist=ReadinessChecklist(
                hs_code_valid=True,
                target_market_identified=True,
                active_buyers_found=filter_result.active_buyers_count > 0,
                buyers_verified=len(safe_verified) > 0,
                contacts_enriched=total_contacts > 0,
                emails_ready=len(email_results) > 0,
                completion_pct=0,  # 아래에서 다시 계산
            ),
            execution_time_seconds=elapsed,
            total_verified_buyers=len(safe_verified),
            total_contacts_found=total_contacts,
            total_emails_generated=len(email_results),
        )
        result.readiness_checklist = _build_checklist(result)

        print(f"[{pipeline_id}] ✅ 전체 파이프라인 완료 — {elapsed}초 / 신호: {signal_color.value}")
        return result
