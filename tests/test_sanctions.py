"""
제재국/규제국 필터링 테스트 (18개).

TC-SAN-001 ~ TC-SAN-018
"""

import pytest
from backend.data.sanctions import (
    BLOCKED_COUNTRIES,
    RESTRICTED_COUNTRIES,
    SanctionStatus,
    check_compliance,
    filter_blocked_countries,
    RESTRICTED_PENALTY,
    ISO2_TO_ISO3,
)


# ---------------------------------------------------------------------------
# TC-SAN-001 ~ 004: Blocked 국가 검사
# ---------------------------------------------------------------------------

class TestBlockedCountries:
    def test_north_korea_blocked(self):
        """TC-SAN-001: 북한(PRK)은 blocked."""
        result = check_compliance("PRK")
        assert result.is_blocked
        assert result.status == SanctionStatus.BLOCKED
        assert "제재" in result.warning

    def test_iran_blocked(self):
        """TC-SAN-002: 이란(IRN)은 blocked."""
        result = check_compliance("IRN")
        assert result.is_blocked
        assert result.legal_notice is not None

    def test_syria_blocked(self):
        """TC-SAN-003: 시리아(SYR)은 blocked."""
        result = check_compliance("SYR")
        assert result.is_blocked

    def test_cuba_blocked(self):
        """TC-SAN-004: 쿠바(CUB)는 blocked."""
        result = check_compliance("CUB")
        assert result.is_blocked


# ---------------------------------------------------------------------------
# TC-SAN-005 ~ 008: Restricted 국가 검사
# ---------------------------------------------------------------------------

class TestRestrictedCountries:
    def test_russia_restricted(self):
        """TC-SAN-005: 러시아(RUS)는 restricted."""
        result = check_compliance("RUS")
        assert result.is_restricted
        assert result.penalty == RESTRICTED_PENALTY
        assert "수출 허가" in result.warning

    def test_belarus_restricted(self):
        """TC-SAN-006: 벨라루스(BLR)는 restricted."""
        result = check_compliance("BLR")
        assert result.is_restricted

    def test_myanmar_restricted(self):
        """TC-SAN-007: 미얀마(MMR)는 restricted."""
        result = check_compliance("MMR")
        assert result.is_restricted

    def test_venezuela_restricted(self):
        """TC-SAN-008: 베네수엘라(VEN)는 restricted."""
        result = check_compliance("VEN")
        assert result.is_restricted


# ---------------------------------------------------------------------------
# TC-SAN-009 ~ 012: Normal 국가 검사
# ---------------------------------------------------------------------------

class TestNormalCountries:
    def test_usa_normal(self):
        """TC-SAN-009: 미국(USA)은 normal."""
        result = check_compliance("USA")
        assert result.status == SanctionStatus.NORMAL
        assert result.penalty == 0.0

    def test_japan_normal(self):
        """TC-SAN-010: 일본(JPN)은 normal."""
        result = check_compliance("JPN")
        assert result.status == SanctionStatus.NORMAL

    def test_vietnam_normal(self):
        """TC-SAN-011: 베트남(VNM)은 normal."""
        result = check_compliance("VNM")
        assert not result.is_blocked
        assert not result.is_restricted

    def test_germany_normal(self):
        """TC-SAN-012: 독일(DEU)은 normal."""
        result = check_compliance("DEU")
        assert result.status == SanctionStatus.NORMAL


# ---------------------------------------------------------------------------
# TC-SAN-013 ~ 015: ISO2 코드 호환성
# ---------------------------------------------------------------------------

class TestISO2Compat:
    def test_iso2_kp_maps_to_prk(self):
        """TC-SAN-013: ISO2 KP -> PRK 변환 후 blocked."""
        result = check_compliance("KP")
        assert result.is_blocked
        assert result.country_iso3 == "PRK"

    def test_iso2_ru_maps_to_rus(self):
        """TC-SAN-014: ISO2 RU -> RUS 변환 후 restricted."""
        result = check_compliance("RU")
        assert result.is_restricted

    def test_iso2_unknown_normal(self):
        """TC-SAN-015: 알 수 없는 2자리 코드는 normal."""
        result = check_compliance("XX")
        assert result.status == SanctionStatus.NORMAL


# ---------------------------------------------------------------------------
# TC-SAN-016 ~ 018: 필터링 함수
# ---------------------------------------------------------------------------

class TestFilterBlocked:
    def test_filter_removes_blocked(self):
        """TC-SAN-016: blocked 국가가 필터링됨."""
        codes = ["USA", "PRK", "JPN", "IRN", "VNM"]
        passed, blocked = filter_blocked_countries(codes)
        assert "PRK" not in passed
        assert "IRN" not in passed
        assert "PRK" in blocked
        assert "IRN" in blocked
        assert len(passed) == 3

    def test_filter_keeps_restricted(self):
        """TC-SAN-017: restricted 국가는 유지됨."""
        codes = ["RUS", "VNM"]
        passed, blocked = filter_blocked_countries(codes)
        assert "RUS" in passed
        assert len(blocked) == 0

    def test_filter_empty_list(self):
        """TC-SAN-018: 빈 리스트 처리."""
        passed, blocked = filter_blocked_countries([])
        assert passed == []
        assert blocked == []
