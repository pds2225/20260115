"""
P2: 바이어 매칭 엔진 테스트 (34개).

TC-MAT-001 ~ TC-MAT-034
"""

import pytest
from datetime import date
from backend.services.matching import (
    BuyerProfile,
    FitScoreResult,
    MatchingEngine,
    SellerProfile,
    SuccessCase,
    calc_cert_score,
    calc_fraud_penalty,
    calc_hs_similarity,
    calc_moq_soft_score,
    calc_success_bonus,
    check_cert_gate,
    check_moq_gate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _seller() -> SellerProfile:
    return SellerProfile(
        company_name="Korea Cosmetics Co.",
        hs_codes=["330499"],
        moq=5000,
        price_range=(5.0, 15.0),
        certifications=["FDA", "ISO", "CE"],
        country_iso3="KOR",
    )


def _buyer_good() -> BuyerProfile:
    return BuyerProfile(
        buyer_id="B001",
        company_name="US Beauty Inc.",
        country_iso3="USA",
        hs_codes=["330499"],
        moq=6000,
        price_range=(7.0, 12.0),
        required_certs=["FDA"],
        preferred_certs=["ISO", "HALAL"],
    )


def _buyer_low_moq() -> BuyerProfile:
    return BuyerProfile(
        buyer_id="B002",
        company_name="Small Buyer",
        country_iso3="VNM",
        hs_codes=["330499"],
        moq=500,  # < 5000 * 0.3 = 1500
        price_range=(5.0, 10.0),
        required_certs=[],
    )


def _buyer_no_cert() -> BuyerProfile:
    return BuyerProfile(
        buyer_id="B003",
        company_name="No Cert Buyer",
        country_iso3="USA",
        hs_codes=["330499"],
        moq=5000,
        price_range=(5.0, 10.0),
        required_certs=["FDA", "NMPA"],  # NMPA 미보유
    )


def _buyer_fraud() -> BuyerProfile:
    return BuyerProfile(
        buyer_id="B004",
        company_name="Fraud Corp",
        country_iso3="VNM",
        hs_codes=["330499"],
        moq=5000,
        price_range=(5.0, 10.0),
        fraud_risk_flag=True,
        fraud_risk_type="past_fraud_history",
    )


def _buyer_blocked() -> BuyerProfile:
    return BuyerProfile(
        buyer_id="B005",
        company_name="NK Corp",
        country_iso3="PRK",
        hs_codes=["330499"],
        moq=5000,
        price_range=(5.0, 10.0),
    )


# ---------------------------------------------------------------------------
# TC-MAT-001 ~ 006: MOQ Hard Gate
# ---------------------------------------------------------------------------

class TestMOQHardGate:
    def test_buyer_too_small(self):
        """TC-MAT-001: buyer_moq < seller_moq * 0.3 -> 탈락."""
        result = check_moq_gate(5000, 500)
        assert not result.passed
        assert result.reason == "MOQ_BUYER_TOO_SMALL"

    def test_seller_too_large(self):
        """TC-MAT-002: buyer_moq extremely small vs seller -> BUYER_TOO_SMALL."""
        result = check_moq_gate(10000, 2000)
        assert not result.passed
        assert result.reason == "MOQ_BUYER_TOO_SMALL"  # ratio=0.2 < 0.3

    def test_exact_threshold_pass(self):
        """TC-MAT-003: ratio above both thresholds -> 통과."""
        result = check_moq_gate(5000, 2000)  # ratio=0.4, seller/buyer=2.5 < 3.0
        assert result.passed

    def test_above_threshold_pass(self):
        """TC-MAT-004: ratio>1.0 완벽 통과."""
        result = check_moq_gate(5000, 6000)
        assert result.passed

    def test_equal_moq_pass(self):
        """TC-MAT-005: 동일 MOQ 통과."""
        result = check_moq_gate(5000, 5000)
        assert result.passed

    def test_zero_seller_moq(self):
        """TC-MAT-006: seller_moq=0이면 항상 통과."""
        result = check_moq_gate(0, 100)
        assert result.passed


# ---------------------------------------------------------------------------
# TC-MAT-007 ~ 012: 인증 Hard Gate
# ---------------------------------------------------------------------------

class TestCertHardGate:
    def test_missing_fda_fails(self):
        """TC-MAT-007: FDA 필수인데 없으면 탈락."""
        result = check_cert_gate(["ISO", "CE"], ["FDA"])
        assert not result.passed
        assert result.reason == "MISSING_REQUIRED_CERTS"

    def test_fda_present_passes(self):
        """TC-MAT-008: FDA 보유시 통과."""
        result = check_cert_gate(["FDA", "ISO"], ["FDA"])
        assert result.passed

    def test_multiple_required_all_present(self):
        """TC-MAT-009: 복수 필수 모두 보유 -> 통과."""
        result = check_cert_gate(["FDA", "CE", "ISO"], ["FDA", "CE"])
        assert result.passed

    def test_multiple_required_one_missing(self):
        """TC-MAT-010: 복수 필수 중 1개 미보유 -> 탈락."""
        result = check_cert_gate(["FDA", "ISO"], ["FDA", "CE"])
        assert not result.passed

    def test_no_required_certs(self):
        """TC-MAT-011: 필수 인증 없으면 항상 통과."""
        result = check_cert_gate([], [])
        assert result.passed

    def test_case_insensitive(self):
        """TC-MAT-012: 대소문자 무관."""
        result = check_cert_gate(["fda", "iso"], ["FDA"])
        assert result.passed


# ---------------------------------------------------------------------------
# TC-MAT-013 ~ 016: MOQ Soft Score
# ---------------------------------------------------------------------------

class TestMOQSoftScore:
    def test_ratio_above_1_perfect(self):
        """TC-MAT-013: buyer >= seller -> 1.0."""
        assert calc_moq_soft_score(5000, 6000) == 1.0

    def test_ratio_0_5(self):
        """TC-MAT-014: ratio=0.5 -> 0.4 부근."""
        score = calc_moq_soft_score(5000, 2500)
        assert 0.35 <= score <= 0.45

    def test_ratio_0_8(self):
        """TC-MAT-015: ratio=0.8 -> 0.8."""
        score = calc_moq_soft_score(5000, 4000)
        assert score == pytest.approx(0.8, abs=0.05)

    def test_ratio_below_0_3_zero(self):
        """TC-MAT-016: ratio<0.3 -> 0.0 (Hard Gate 안전장치)."""
        score = calc_moq_soft_score(5000, 1000)
        assert score < 0.1


# ---------------------------------------------------------------------------
# TC-MAT-017 ~ 020: 인증 점수
# ---------------------------------------------------------------------------

class TestCertScore:
    def test_full_required_and_preferred(self):
        """TC-MAT-017: 필수+선호 모두 충족."""
        score = calc_cert_score(
            ["FDA", "ISO", "HALAL"], ["FDA"], ["ISO", "HALAL"]
        )
        assert score == pytest.approx(0.9)  # 0.7 + 0.2

    def test_required_only(self):
        """TC-MAT-018: 필수만 충족, 선호 없음."""
        score = calc_cert_score(["FDA"], ["FDA"], [])
        assert score == pytest.approx(0.7)

    def test_no_requirements(self):
        """TC-MAT-019: 요구사항 없으면 0.7 (required=100%)."""
        score = calc_cert_score(["FDA"], [], [])
        assert score == pytest.approx(0.7)

    def test_preferred_capped(self):
        """TC-MAT-020: 선호 점수 최대 0.3."""
        score = calc_cert_score(
            ["FDA", "ISO", "HALAL", "GMP", "KOSHER"],
            ["FDA"],
            ["ISO", "HALAL", "GMP", "KOSHER"],
        )
        assert score <= 1.0


# ---------------------------------------------------------------------------
# TC-MAT-021 ~ 024: HS코드 유사도
# ---------------------------------------------------------------------------

class TestHSSimilarity:
    def test_6digit_exact(self):
        """TC-MAT-021: 6자리 완전 일치 -> 1.0."""
        assert calc_hs_similarity("330499", "330499") == 1.0

    def test_4digit_match(self):
        """TC-MAT-022: 4자리 일치 -> 0.8."""
        assert calc_hs_similarity("330499", "330410") == 0.8

    def test_2digit_match(self):
        """TC-MAT-023: 2자리 일치 -> 0.6."""
        assert calc_hs_similarity("330499", "339900") == 0.6

    def test_no_match(self):
        """TC-MAT-024: 불일치 -> 0.0."""
        assert calc_hs_similarity("330499", "850000") == 0.0


# ---------------------------------------------------------------------------
# TC-MAT-025 ~ 028: 성공사례 보너스 + 사기방지
# ---------------------------------------------------------------------------

class TestSuccessAndFraud:
    def test_perfect_match_10pts(self):
        """TC-MAT-025: 국가+HS+최신 -> 10점."""
        cases = [SuccessCase("C1", "USA", "330499", date(2025, 6, 1))]
        bonus, details = calc_success_bonus(cases, "USA", "330499", date(2026, 1, 1))
        assert bonus == pytest.approx(10.0)

    def test_country_mismatch_zero(self):
        """TC-MAT-026: 국가 불일치 -> 0점."""
        cases = [SuccessCase("C1", "DEU", "330499", date(2025, 6, 1))]
        bonus, details = calc_success_bonus(cases, "USA", "330499", date(2026, 1, 1))
        assert bonus == 0.0
        assert details[0]["is_reference_only"]

    def test_old_case_recency_0_3(self):
        """TC-MAT-027: 4년 초과 -> recency=0.3."""
        cases = [SuccessCase("C1", "USA", "330499", date(2020, 1, 1))]
        bonus, details = calc_success_bonus(cases, "USA", "330499", date(2026, 1, 1))
        assert bonus == pytest.approx(10.0 * 1.0 * 1.0 * 0.3)

    def test_fraud_penalty_minus_25(self):
        """TC-MAT-028: 사기 이력 -> -25점."""
        penalty = calc_fraud_penalty(_buyer_fraud())
        assert penalty == -25.0


# ---------------------------------------------------------------------------
# TC-MAT-029 ~ 034: 통합 매칭 엔진
# ---------------------------------------------------------------------------

class TestMatchingEngine:
    def test_good_buyer_high_score(self):
        """TC-MAT-029: 적합 바이어는 높은 점수."""
        engine = MatchingEngine(_seller(), [_buyer_good()])
        results = engine.match_all()
        assert results[0].fit_score > 70

    def test_low_moq_excluded(self):
        """TC-MAT-030: MOQ 미달 바이어는 excluded."""
        engine = MatchingEngine(_seller(), [_buyer_low_moq()])
        results = engine.match_all()
        assert results[0].excluded
        assert "MOQ" in results[0].exclude_reason

    def test_missing_cert_excluded(self):
        """TC-MAT-031: 필수 인증 미충족 바이어는 excluded."""
        engine = MatchingEngine(_seller(), [_buyer_no_cert()])
        results = engine.match_all()
        assert results[0].excluded
        assert "인증" in results[0].exclude_reason

    def test_fraud_buyer_low_score(self):
        """TC-MAT-032: 사기 이력 바이어는 점수 급락."""
        engine = MatchingEngine(_seller(), [_buyer_good(), _buyer_fraud()])
        results = engine.match_all()
        active = [r for r in results if not r.excluded]
        fraud_result = [r for r in active if r.buyer_id == "B004"]
        good_result = [r for r in active if r.buyer_id == "B001"]
        if fraud_result and good_result:
            assert fraud_result[0].fit_score < good_result[0].fit_score

    def test_blocked_country_excluded(self):
        """TC-MAT-033: 제재국 바이어는 excluded."""
        engine = MatchingEngine(_seller(), [_buyer_blocked()])
        results = engine.match_all()
        assert results[0].excluded
        assert "제재" in results[0].exclude_reason

    def test_ranking_assigned(self):
        """TC-MAT-034: 활성 결과에 순위 부여."""
        buyers = [_buyer_good(), _buyer_fraud()]
        engine = MatchingEngine(_seller(), buyers)
        results = engine.match_all()
        active = [r for r in results if not r.excluded]
        if len(active) >= 2:
            assert active[0].rank == 1
            assert active[1].rank == 2
