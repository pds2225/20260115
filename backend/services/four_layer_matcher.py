"""4중 AND 필터 통합 매칭 엔진 — FitScore™
스크린샷 목표: Trademo(활동) + Coface(대금) + Panjiva(규모) + Apollo(연락처) = 4중 검증 매칭

FitScore 산출 공식:
  Layer 1 (활동이력)   40%
  Layer 2 (대금지급)   30%
  Layer 3 (수입규모)   20%
  Layer 4 (담당자확보) 10%

최종 출력: 4개 Layer 모두 pass인 바이어만 Top 10 리스트
"""
import asyncio
import time
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

from backend.models.schemas import (
    FullPipelineRequest, SignalColor, HSCodeAnalysisRequest, TradeFilterRequest,
    ReadinessChecklist, ActiveBuyer, Layer3FilterInput
)
from backend.services.step1_hs_analyzer import HSCodeAnalyzer
from backend.services.step2_trade_filter import TradeHistoryFilter
from backend.services.step3_buyer_verifier import BuyerVerifier          # 베트남 법인 실사
from backend.services.step4_contact_enricher import ContactEnricher
from backend.services.step5_email_generator import EmailGenerator
from backend.services.layer1_activity_history import ActivityHistoryAnalyzer, ActivityResult
from backend.services.layer2_credit_verifier import CreditVerifier, CreditVerificationResult
from backend.services.layer3_import_volume import ImportVolumeVerifier, BuyingPowerResult, Layer3Filter
from backend.services.layer4_contact_finder import DecisionMakerFinder, EnrichedContact


# ── FitScore 결과 스키마 ──────────────────────────────────────────────────
class LayerPassStatus(BaseModel):
    layer1_activity: bool
    layer2_credit: bool
    layer3_volume: bool
    layer4_contact: bool

    @property
    def all_pass(self) -> bool:
        return all([
            self.layer1_activity,
            self.layer2_credit,
            self.layer3_volume,
            self.layer4_contact,
        ])

    @property
    def pass_count(self) -> int:
        return sum([
            self.layer1_activity,
            self.layer2_credit,
            self.layer3_volume,
            self.layer4_contact,
        ])


class VerifiedBuyerV2(BaseModel):
    rank: int
    company_name: str
    country: str

    # Layer 결과
    layer1: ActivityResult
    layer2: CreditVerificationResult
    layer3: BuyingPowerResult
    layer4: EnrichedContact
    layer_status: LayerPassStatus

    # FitScore
    fit_score: float = Field(..., ge=0, le=100, description="4중 검증 통합 점수")
    fit_grade: str                    # "S" | "A" | "B" | "C" | "F"

    # 컨택 정보 요약
    decision_maker_name: Optional[str]
    decision_maker_title: Optional[str]
    decision_maker_email: Optional[str]
    email_confidence_pct: float
    linkedin_search_url: Optional[str]

    # 추천
    recommended_contact_method: str   # "이메일" | "LinkedIn" | "전화"
    action_priority: str              # "즉시" | "1주 이내" | "검토 필요"


class FourLayerPipelineResult(BaseModel):
    pipeline_id: str
    hs_code: str
    target_country: str

    # 단계별 통계
    total_screened: int
    layer1_passed: int
    layer2_passed: int
    layer3_passed: int
    layer4_passed: int
    fully_verified: int               # 4개 Layer 모두 통과

    # 신호등
    signal_color: SignalColor
    signal_message: str

    # 최종 바이어 리스트 (FitScore 정렬)
    verified_buyers: list[VerifiedBuyerV2]

    # 이메일 결과
    email_results: list

    # 메타
    execution_time_seconds: float
    readiness: ReadinessChecklist


def _compute_fit_score(
    l1: ActivityResult,
    l2: CreditVerificationResult,
    l3: BuyingPowerResult,
    l4: EnrichedContact,
) -> float:
    """FitScore = L1×40% + L2×30% + L3×20% + L4×10%"""
    # Layer 1: 활동 이력 (6개월 내 거래 여부 — 점수화 없음)
    # pass=100점, fail=0점으로 단순 처리
    s1 = 100.0 if l1.pass_layer1 else 0.0

    # Layer 2: 신용 점수 (0~100) — 등급 기반
    # C등급도 PASS이므로 FitScore에 정상 반영 (단, A·B보다 낮게)
    credit_map = {"A": 95, "B": 80, "C": 62, "D": 15, "E": 5, "X": 0, "UNKNOWN": 50}
    raw_s2 = credit_map.get(l2.credit_grade.value, 50)
    s2 = raw_s2 if l2.pass_layer2 else raw_s2 * 0.15

    # Layer 3: Buying Power (0~100)
    s3 = l3.buying_power_score if l3.pass_layer3 else l3.buying_power_score * 0.3

    # Layer 4: 연락처 신뢰도 (0~100)
    email_conf = l4.email_verification.confidence if l4.email_verification else 0
    s4 = email_conf * 100 if l4.pass_layer4 else email_conf * 50

    fit = s1 * 0.40 + s2 * 0.30 + s3 * 0.20 + s4 * 0.10
    return round(fit, 1)


def _fit_grade(score: float) -> str:
    if score >= 85:
        return "S"
    elif score >= 70:
        return "A"
    elif score >= 55:
        return "B"
    elif score >= 40:
        return "C"
    else:
        return "F"


def _signal_from_count(fully_verified: int, total: int) -> tuple[SignalColor, str]:
    if fully_verified >= 3:
        return SignalColor.GREEN, f"✅ 즉시 진입 가능 — {fully_verified}개 4중 검증 완료 바이어"
    elif fully_verified >= 1:
        return SignalColor.YELLOW, f"⚠️ 부분 검증 — {fully_verified}개 완전 검증, {total - fully_verified}개 추가 실사 필요"
    else:
        return SignalColor.RED, f"🚫 진입 보류 — 4중 검증 통과 바이어 없음 ({total}개 스크리닝)"


def _recommend_contact(l4: EnrichedContact, l2: CreditVerificationResult) -> tuple[str, str]:
    """추천 컨택 방법 + 액션 우선순위"""
    if l4.email and l4.email_verification and l4.email_verification.is_valid:
        method = "이메일"
        if l2.credit_grade.value in ("A", "B"):
            priority = "즉시"
        else:
            priority = "1주 이내"
    elif l4.linkedin_profile_url or l4.linkedin_search_url:
        method = "LinkedIn"
        priority = "1주 이내"
    elif l4.phone:
        method = "전화"
        priority = "즉시"
    else:
        method = "LinkedIn"
        priority = "검토 필요"
    return method, priority


class FourLayerMatcher:
    """4중 AND 필터 통합 매칭 서비스"""

    def __init__(self):
        self.hs_analyzer = HSCodeAnalyzer()
        self.trade_filter = TradeHistoryFilter()
        self.l1_analyzer = ActivityHistoryAnalyzer()
        self.l2_verifier = CreditVerifier()
        self.l3_verifier = ImportVolumeVerifier()
        self.erc_verifier = BuyerVerifier()          # 베트남 ERC 3중 검증
        self.contact_enricher = ContactEnricher()
        self.l4_finder = DecisionMakerFinder()
        self.email_gen = EmailGenerator()

    async def run(self, req: FullPipelineRequest) -> FourLayerPipelineResult:
        start = time.time()
        pid = str(uuid.uuid4())[:8].upper()

        print(f"\n[{pid}] ══════ VALUE-UP AI 4중 검증 파이프라인 시작 ══════")

        # Step 1: HS코드 분석
        print(f"[{pid}] Step 1: HS코드 분석...")
        hs_result = await self.hs_analyzer.analyze(
            HSCodeAnalysisRequest(hs_code=req.hs_code, target_country=req.target_country, top_buyers=50)
        )
        print(f"         → {hs_result.total_importers_found}개 수입자 발견")

        # Step 2: 거래 이력 1차 필터
        print(f"[{pid}] Step 2: 1차 거래 이력 필터링...")
        filter_result = self.trade_filter.filter(
            TradeFilterRequest(hs_code=req.hs_code, country=req.target_country),
            hs_result,
        )
        candidates = filter_result.active_buyers[:50]  # 최대 50개 처리
        print(f"         → {filter_result.active_buyers_count}개 활성 바이어 (상위 {len(candidates)}개 처리)")

        # Layer 1~4 병렬 실행
        print(f"[{pid}] Layer 1~4: 4중 검증 병렬 실행...")
        # Layer3Filter 변환 (schemas → services)
        l3_filter: Optional[Layer3Filter] = None
        if req.layer3_filter:
            fi = req.layer3_filter
            l3_filter = Layer3Filter(
                monthly_import_min_usd=fi.monthly_import_min_usd,
                seller_moq_units=fi.seller_moq_units,
                seller_unit_price_usd=fi.seller_unit_price_usd,
            )

        l1_task = self.l1_analyzer.analyze_batch(candidates)
        l2_task = self.l2_verifier.verify_batch(candidates)
        l3_task = self.l3_verifier.verify_batch(candidates, l3_filter)
        contact_task = self.contact_enricher.enrich_batch(candidates)

        l1_results, l2_results, l3_results, contact_results = await asyncio.gather(
            l1_task, l2_task, l3_task, contact_task
        )

        # Layer 4: EnrichedContact 생성
        l4_results = []
        for buyer, contact_r in zip(candidates, contact_results):
            enriched = await self.l4_finder.find(
                company_name=buyer.company_name,
                country=buyer.country,
                domain=contact_r.domain or "",
                existing_contacts=contact_r.contacts,
            )
            l4_results.append(enriched)

        # 4중 AND 필터 통합
        verified_buyers = []
        for i, (buyer, l1, l2, l3, l4) in enumerate(
            zip(candidates, l1_results, l2_results, l3_results, l4_results)
        ):
            layer_status = LayerPassStatus(
                layer1_activity=l1.pass_layer1,
                layer2_credit=l2.pass_layer2,
                layer3_volume=l3.pass_layer3,
                layer4_contact=l4.pass_layer4,
            )

            fit_score = _compute_fit_score(l1, l2, l3, l4)
            contact_method, priority = _recommend_contact(l4, l2)

            verified_buyers.append(VerifiedBuyerV2(
                rank=0,                       # 정렬 후 재부여
                company_name=buyer.company_name,
                country=buyer.country,
                layer1=l1,
                layer2=l2,
                layer3=l3,
                layer4=l4,
                layer_status=layer_status,
                fit_score=fit_score,
                fit_grade=_fit_grade(fit_score),
                decision_maker_name=l4.contact_name,
                decision_maker_title=l4.title,
                decision_maker_email=l4.email,
                email_confidence_pct=round(
                    (l4.email_verification.confidence if l4.email_verification else 0) * 100, 1
                ),
                linkedin_search_url=l4.linkedin_search_url,
                recommended_contact_method=contact_method,
                action_priority=priority,
            ))

        # FitScore 내림차순 정렬 + Rank 부여
        verified_buyers.sort(key=lambda b: (-b.fit_score, -b.layer_status.pass_count))
        for i, b in enumerate(verified_buyers, 1):
            b.rank = i

        # 통계
        l1_pass = sum(1 for b in verified_buyers if b.layer_status.layer1_activity)
        l2_pass = sum(1 for b in verified_buyers if b.layer_status.layer2_credit)
        l3_pass = sum(1 for b in verified_buyers if b.layer_status.layer3_volume)
        l4_pass = sum(1 for b in verified_buyers if b.layer_status.layer4_contact)
        fully_verified = sum(1 for b in verified_buyers if b.layer_status.all_pass)

        print(f"[{pid}] Layer 1 통과: {l1_pass}/{len(candidates)}")
        print(f"[{pid}] Layer 2 통과: {l2_pass}/{len(candidates)}")
        print(f"[{pid}] Layer 3 통과: {l3_pass}/{len(candidates)}")
        print(f"[{pid}] Layer 4 통과: {l4_pass}/{len(candidates)}")
        print(f"[{pid}] 4중 통과:    {fully_verified}/{len(candidates)}")

        # Step 5: 검증된 바이어 이메일 생성
        print(f"[{pid}] Step 5: 이메일 생성...")
        # 4중 통과 바이어 우선, 없으면 전체
        email_targets = [b for b in verified_buyers if b.layer_status.all_pass] or verified_buyers[:3]
        email_buyers = []
        email_contacts = []
        for b in email_targets:
            buyer_obj = next((c for c in candidates if c.company_name == b.company_name), None)
            contact_obj = next((c for c in contact_results if c.company_name == b.company_name), None)
            if buyer_obj and contact_obj:
                email_buyers.append(buyer_obj)
                email_contacts.append(contact_obj)

        email_results = await self.email_gen.generate_batch(
            email_buyers, email_contacts,
            req.seller_company, req.seller_product, req.hs_code,
            "en", req.seller_usp,
        )
        print(f"[{pid}] → {len(email_results)}개 이메일 생성 완료")

        elapsed = round(time.time() - start, 2)
        signal_color, signal_message = _signal_from_count(fully_verified, len(candidates))

        checklist = ReadinessChecklist(
            hs_code_valid=True,
            target_market_identified=hs_result.total_importers_found > 0,
            active_buyers_found=filter_result.active_buyers_count > 0,
            buyers_verified=fully_verified > 0,
            contacts_enriched=l4_pass > 0,
            emails_ready=len(email_results) > 0,
            completion_pct=round(
                (1 + (hs_result.total_importers_found > 0) +
                 (filter_result.active_buyers_count > 0) +
                 (fully_verified > 0) + (l4_pass > 0) + (len(email_results) > 0)) / 6 * 100, 1
            ),
        )

        print(f"[{pid}] ══ 완료: {elapsed}초 / 신호등: {signal_color.value} ══")

        return FourLayerPipelineResult(
            pipeline_id=pid,
            hs_code=req.hs_code,
            target_country=req.target_country,
            total_screened=len(candidates),
            layer1_passed=l1_pass,
            layer2_passed=l2_pass,
            layer3_passed=l3_pass,
            layer4_passed=l4_pass,
            fully_verified=fully_verified,
            signal_color=signal_color,
            signal_message=signal_message,
            verified_buyers=verified_buyers,
            email_results=email_results,
            execution_time_seconds=elapsed,
            readiness=checklist,
        )
