"""
Claude 레포 → VALUE-UP AI 통합: 바이어 매칭 엔진 (Hard Gate 로직)
출처: github.com/pds2225/20260115 (genspark_ai_developer 브랜치)
통합일: 2026-03-18

주요 기능:
  - MOQ Hard Gate: buyer_moq < seller_moq * 0.3 → 즉시 탈락
  - 인증 Hard Gate: 필수 인증 미충족 → 즉시 탈락
  - FitScore: base(50) + hs_match(20) + price(15) + moq(10) + cert(15)
              + fraud_penalty(-25) + success_bonus(0~20)

VALUE-UP AI 4중 파이프라인의 Layer 2~3 정밀 필터링에 통합 활용.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from backend.services.sanctions import check_compliance, SanctionStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SellerProfile:
    """셀러(우리 회사) 프로필."""

    company_name: str
    hs_codes: list[str]
    moq: int  # 최소주문수량
    price_range: tuple[float, float]  # (min_usd, max_usd)
    certifications: list[str]  # ["FDA", "ISO", "CE", ...]
    country_iso3: str = "KOR"


@dataclass
class BuyerProfile:
    """바이어 프로필."""

    buyer_id: str
    company_name: str
    country_iso3: str
    hs_codes: list[str]
    moq: int
    price_range: tuple[float, float]
    required_certs: list[str] = field(default_factory=list)
    preferred_certs: list[str] = field(default_factory=list)
    fraud_risk_flag: bool = False
    fraud_risk_type: str = ""


@dataclass
class SuccessCase:
    """과거 성공 사례."""

    case_id: str
    country_iso3: str
    hs_code: str
    case_date: date
    description: str = ""


@dataclass
class GateResult:
    """Hard Gate 검사 결과."""

    passed: bool
    reason: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class FitScoreResult:
    """매칭 적합도 점수 결과."""

    buyer_id: str
    buyer_name: str
    country_iso3: str
    fit_score: float  # 0~100
    rank: int = 0

    # Gate 결과
    moq_gate: GateResult = field(default_factory=lambda: GateResult(True))
    cert_gate: GateResult = field(default_factory=lambda: GateResult(True))

    # 점수 breakdown
    base_score: float = 50.0
    hs_match_bonus: float = 0.0
    price_bonus: float = 0.0
    moq_score: float = 0.0
    cert_score: float = 0.0
    fraud_penalty: float = 0.0
    success_bonus: float = 0.0

    # 추가 정보
    compliance_status: str = "normal"
    warnings: list[str] = field(default_factory=list)
    excluded: bool = False
    exclude_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "buyer_id": self.buyer_id,
            "buyer_name": self.buyer_name,
            "country_iso3": self.country_iso3,
            "fit_score": round(self.fit_score, 1),
            "rank": self.rank,
            "score_breakdown": {
                "base_score": self.base_score,
                "hs_match_bonus": self.hs_match_bonus,
                "price_bonus": self.price_bonus,
                "moq_score": round(self.moq_score, 2),
                "cert_score": round(self.cert_score, 2),
                "fraud_penalty": self.fraud_penalty,
                "success_bonus": round(self.success_bonus, 2),
            },
            "gates": {
                "moq_gate_passed": self.moq_gate.passed,
                "moq_gate_reason": self.moq_gate.reason,
                "cert_gate_passed": self.cert_gate.passed,
                "cert_gate_reason": self.cert_gate.reason,
            },
            "compliance_status": self.compliance_status,
            "warnings": self.warnings,
            "excluded": self.excluded,
            "exclude_reason": self.exclude_reason,
        }


# ---------------------------------------------------------------------------
# Hard Gate 검사
# ---------------------------------------------------------------------------

def check_moq_gate(seller_moq: int, buyer_moq: int) -> GateResult:
    """
    MOQ Hard Gate 검사.

    - buyer_moq < seller_moq * 0.3 -> 탈락 (MOQ_BUYER_TOO_SMALL)
    - seller_moq > buyer_moq * 3.0 -> 탈락 (MOQ_SELLER_TOO_LARGE)
    """
    if seller_moq <= 0:
        return GateResult(True)

    ratio = buyer_moq / seller_moq if seller_moq > 0 else 0

    # buyer_moq < seller_moq * 0.3 -> buyer requests too little
    if ratio < 0.3:
        return GateResult(
            passed=False,
            reason="MOQ_BUYER_TOO_SMALL",
            details={
                "seller_moq": seller_moq,
                "buyer_moq": buyer_moq,
                "moq_ratio": round(ratio, 3),
                "threshold": 0.3,
            },
        )

    # seller_moq > buyer_moq * 3.0 -> seller requires too much
    # (only when ratio >= 0.3 but still structurally mismatched)
    if buyer_moq > 0 and seller_moq > buyer_moq * 3.0:
        return GateResult(
            passed=False,
            reason="MOQ_SELLER_TOO_LARGE",
            details={
                "seller_moq": seller_moq,
                "buyer_moq": buyer_moq,
                "moq_ratio": round(ratio, 3),
                "threshold": 3.0,
            },
        )

    return GateResult(
        passed=True,
        details={
            "seller_moq": seller_moq,
            "buyer_moq": buyer_moq,
            "moq_ratio": round(ratio, 3),
        },
    )


def check_cert_gate(
    seller_certs: list[str], buyer_required_certs: list[str]
) -> GateResult:
    """
    인증 Hard Gate 검사.

    필수 인증이 1개라도 없으면 즉시 탈락.
    """
    if not buyer_required_certs:
        return GateResult(True)

    seller_set = set(c.upper() for c in seller_certs)
    required_set = set(c.upper() for c in buyer_required_certs)

    missing = required_set - seller_set

    if missing:
        return GateResult(
            passed=False,
            reason="MISSING_REQUIRED_CERTS",
            details={
                "missing_required_certs": sorted(missing),
                "seller_certs": sorted(seller_set),
                "buyer_required_certs": sorted(required_set),
            },
        )

    return GateResult(
        passed=True,
        details={
            "matched_required_certs": sorted(required_set & seller_set),
        },
    )


# ---------------------------------------------------------------------------
# Soft 점수 계산
# ---------------------------------------------------------------------------

def calc_moq_soft_score(seller_moq: int, buyer_moq: int) -> float:
    """
    MOQ Soft Score (0~1).

    moq_ratio = buyer_moq / seller_moq
    1.0+ -> 1.0
    0.8~1.0 -> 0.8~1.0
    0.5~0.8 -> 0.4~0.8
    0.3~0.5 -> 0.0~0.4
    """
    if seller_moq <= 0:
        return 1.0

    ratio = buyer_moq / seller_moq

    if ratio >= 1.0:
        return 1.0
    elif ratio >= 0.8:
        return 0.8 + (ratio - 0.8) * 1.0
    elif ratio >= 0.5:
        return 0.4 + (ratio - 0.5) * (0.4 / 0.3)
    elif ratio >= 0.3:
        return (ratio - 0.3) * (0.4 / 0.2)
    else:
        return 0.0


def calc_cert_score(
    seller_certs: list[str],
    buyer_required_certs: list[str],
    buyer_preferred_certs: list[str],
) -> float:
    """인증 점수 (0~1)."""
    seller_set = set(c.upper() for c in seller_certs)
    required_set = set(c.upper() for c in buyer_required_certs)
    preferred_set = set(c.upper() for c in buyer_preferred_certs)

    # 필수 충족률 (70%)
    if required_set:
        required_match = len(required_set & seller_set) / len(required_set)
    else:
        required_match = 1.0
    required_score = required_match * 0.7

    # 선호 인증 가중치 (30%)
    preferred_count = len(preferred_set & seller_set)
    preferred_score = min(preferred_count * 0.1, 0.3)

    return required_score + preferred_score


def calc_hs_similarity(hs1: str, hs2: str) -> float:
    """HS코드 유사도 (0~1)."""
    if len(hs1) >= 6 and len(hs2) >= 6 and hs1[:6] == hs2[:6]:
        return 1.0
    elif len(hs1) >= 4 and len(hs2) >= 4 and hs1[:4] == hs2[:4]:
        return 0.8
    elif len(hs1) >= 2 and len(hs2) >= 2 and hs1[:2] == hs2[:2]:
        return 0.6
    return 0.0


def calc_success_bonus(
    cases: list[SuccessCase],
    target_country: str,
    target_hs: str,
    today: date | None = None,
) -> tuple[float, list[dict]]:
    """
    성공사례 보너스 계산.

    success_bonus = 10 * country_match * hs_similarity * recency
    최대 캡: 20점

    Returns:
        (total_bonus, case_details)
    """
    if today is None:
        today = date.today()

    total = 0.0
    details = []

    for case in cases:
        # 국가 일치
        country_match = 1.0 if case.country_iso3.upper() == target_country.upper() else 0.0

        # HS 유사도
        hs_sim = calc_hs_similarity(case.hs_code, target_hs)

        # 최신도
        days_ago = (today - case.case_date).days
        if days_ago <= 730:
            recency = 1.0
        elif days_ago <= 1460:
            recency = 0.6
        else:
            recency = 0.3

        bonus = 10.0 * country_match * hs_sim * recency

        details.append({
            "case_id": case.case_id,
            "bonus": round(bonus, 2),
            "country_match": bool(country_match),
            "hs_similarity": hs_sim,
            "recency": recency,
            "is_reference_only": country_match == 0,
        })

        total += bonus

    # 캡 20점
    return min(total, 20.0), details


def calc_fraud_penalty(buyer: BuyerProfile) -> float:
    """
    사기 방지 감점 (0 ~ -25).

    fraud_risk_flag가 True이면 -25점.
    """
    if buyer.fraud_risk_flag:
        return -25.0
    return 0.0


# ---------------------------------------------------------------------------
# 매칭 엔진
# ---------------------------------------------------------------------------

class MatchingEngine:
    """
    바이어 매칭 엔진.

    FitScore = base(50) + hs_match(0~20) + price(0~15) + moq(0~10)
               + cert(0~15) + fraud_penalty(-25~0) + success_bonus(0~20)

    Hard Gate 불통과 시 즉시 탈락.

    사용법:
        engine = MatchingEngine(seller, buyers, success_cases)
        results = engine.match_all()
    """

    def __init__(
        self,
        seller: SellerProfile,
        buyers: list[BuyerProfile],
        success_cases: list[SuccessCase] | None = None,
    ):
        self.seller = seller
        self.buyers = buyers
        self.success_cases = success_cases or []

    def match_single(self, buyer: BuyerProfile) -> FitScoreResult:
        """단일 바이어에 대해 FitScore를 계산한다."""
        result = FitScoreResult(
            buyer_id=buyer.buyer_id,
            buyer_name=buyer.company_name,
            country_iso3=buyer.country_iso3,
            fit_score=0.0,
        )

        # 제재국 체크
        comp = check_compliance(buyer.country_iso3)
        result.compliance_status = comp.status.value
        if comp.is_blocked:
            result.excluded = True
            result.exclude_reason = f"제재 대상국: {comp.warning}"
            return result

        if comp.is_restricted:
            result.warnings.append(comp.warning or "수출 제한국")

        # Hard Gate 1: MOQ
        moq_gate = check_moq_gate(self.seller.moq, buyer.moq)
        result.moq_gate = moq_gate
        if not moq_gate.passed:
            result.excluded = True
            result.exclude_reason = f"MOQ 불일치: {moq_gate.reason}"
            return result

        # Hard Gate 2: 인증
        cert_gate = check_cert_gate(self.seller.certifications, buyer.required_certs)
        result.cert_gate = cert_gate
        if not cert_gate.passed:
            result.excluded = True
            result.exclude_reason = f"필수 인증 미충족: {cert_gate.reason}"
            return result

        # --- Soft 점수 계산 ---

        # HS코드 일치 (최대 20점)
        best_hs_sim = 0.0
        for s_hs in self.seller.hs_codes:
            for b_hs in buyer.hs_codes:
                sim = calc_hs_similarity(s_hs, b_hs)
                best_hs_sim = max(best_hs_sim, sim)
        result.hs_match_bonus = best_hs_sim * 20.0

        # 가격대 일치 (최대 15점)
        s_min, s_max = self.seller.price_range
        b_min, b_max = buyer.price_range
        if s_min <= b_max and s_max >= b_min:
            # 겹치는 구간 비율
            overlap_start = max(s_min, b_min)
            overlap_end = min(s_max, b_max)
            overlap = overlap_end - overlap_start
            total_range = max(s_max, b_max) - min(s_min, b_min)
            price_ratio = overlap / total_range if total_range > 0 else 0
            result.price_bonus = price_ratio * 15.0
        else:
            result.price_bonus = 0.0

        # MOQ 적합도 (최대 10점)
        moq_soft = calc_moq_soft_score(self.seller.moq, buyer.moq)
        result.moq_score = moq_soft * 10.0

        # 인증 점수 (최대 15점)
        cert_sc = calc_cert_score(
            self.seller.certifications,
            buyer.required_certs,
            buyer.preferred_certs,
        )
        result.cert_score = cert_sc * 15.0

        # 사기 방지 (-25 ~ 0)
        result.fraud_penalty = calc_fraud_penalty(buyer)

        # 성공사례 보너스 (0 ~ 20)
        if self.success_cases:
            bonus, _ = calc_success_bonus(
                self.success_cases,
                buyer.country_iso3,
                buyer.hs_codes[0] if buyer.hs_codes else "",
            )
            result.success_bonus = bonus

        # 합산
        total = (
            result.base_score
            + result.hs_match_bonus
            + result.price_bonus
            + result.moq_score
            + result.cert_score
            + result.fraud_penalty
            + result.success_bonus
        )

        result.fit_score = max(0.0, min(100.0, total))
        return result

    def match_all(self) -> list[FitScoreResult]:
        """전체 바이어에 대해 매칭을 수행하고 FitScore 순으로 정렬한다."""
        results = []
        for buyer in self.buyers:
            result = self.match_single(buyer)
            results.append(result)

        # 활성 결과 정렬
        active = [r for r in results if not r.excluded]
        excluded = [r for r in results if r.excluded]

        active.sort(key=lambda r: r.fit_score, reverse=True)

        # 순위 부여
        for i, r in enumerate(active, 1):
            r.rank = i

        return active + excluded
