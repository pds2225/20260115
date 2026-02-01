"""
DS-02 EconomicScore 테스트 (v1: GDP + GDP growth 2개 지표).

테스트 시나리오는 docs/DS02_WSB_SPEC.md 11장 기반.
"""

import math
import pytest

from backend.data.ds02_worldbank import DS02Record, WSB_FIELDS
from backend.services.ds02_scorer import (
    CLIP_RANGES,
    WEIGHTS,
    DS02Scorer,
    NormalizedDS02,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rec(
    iso3: str = "VNM",
    name: str = "Vietnam",
    gdp: float | None = 430e9,
    gdp_growth: float | None = 5.1,
    year: int = 2023,
) -> DS02Record:
    rec = DS02Record(
        country_iso3=iso3,
        country_name=name,
        snapshot_date="2026-01-28",
    )
    if gdp is not None:
        rec.gdp_usd = (gdp, year)
    if gdp_growth is not None:
        rec.gdp_growth_pct = (gdp_growth, year)
    return rec


def _multi() -> list[DS02Record]:
    """여러 국가 레코드 (정규화 min-max 테스트용)."""
    return [
        _rec("VNM", "Vietnam", gdp=430e9, gdp_growth=5.1),
        _rec("USA", "United States", gdp=25462e9, gdp_growth=2.1),
        _rec("DEU", "Germany", gdp=4072e9, gdp_growth=-0.87),
        _rec("CHN", "China", gdp=17963e9, gdp_growth=5.2),
        _rec("IND", "India", gdp=3638e9, gdp_growth=9.19),
        _rec("KOR", "Korea, Rep.", gdp=1845e9, gdp_growth=1.58),
    ]


# ---------------------------------------------------------------------------
# TC-DS02-001: 정상 수집 및 점수 산정
# ---------------------------------------------------------------------------

class TestNormalScoring:
    def test_score_range(self):
        """EconomicScore는 0 ~ 1 범위."""
        results = DS02Scorer(_multi()).score_all()
        for r in results:
            assert not r.excluded
            assert 0.0 <= r.economic_score <= 1.0, (
                f"{r.country_iso3}: score={r.economic_score}"
            )

    def test_no_missing_when_complete(self):
        """모든 지표 제공 시 missing_fields 비어있음."""
        results = DS02Scorer(_multi()).score_all()
        for r in results:
            assert r.missing_fields == []

    def test_normalized_values_range(self):
        """정규화 값은 0~1 범위."""
        results = DS02Scorer(_multi()).score_all()
        for r in results:
            if r.norm_gdp is not None:
                assert 0.0 <= r.norm_gdp <= 1.0
            if r.norm_gdp_growth is not None:
                assert 0.0 <= r.norm_gdp_growth <= 1.0


# ---------------------------------------------------------------------------
# TC-DS02-009: GDP가 큰 국가 → 높은 norm_gdp
# ---------------------------------------------------------------------------

class TestGDPOrdering:
    def test_usa_higher_than_vnm(self):
        results = DS02Scorer(_multi()).score_all()
        by = {r.country_iso3: r for r in results}
        assert by["USA"].norm_gdp > by["VNM"].norm_gdp

    def test_usa_highest_score(self):
        """GDP가 가장 큰 USA가 norm_gdp=1.0."""
        results = DS02Scorer(_multi()).score_all()
        by = {r.country_iso3: r for r in results}
        assert by["USA"].norm_gdp == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TC-DS02-002: GDP 결측 → 후보군 제외
# ---------------------------------------------------------------------------

class TestGDPMissing:
    def test_gdp_none_excluded(self):
        rec = _rec("XXX", "Unknown", gdp=None)
        results = DS02Scorer([rec]).score_all()
        assert results[0].excluded
        assert "GDP missing" in results[0].exclude_reason

    def test_gdp_none_still_in_results(self):
        """excluded=True여도 결과 리스트에는 포함 (설명용)."""
        rec = _rec("XXX", "Unknown", gdp=None)
        results = DS02Scorer([rec]).score_all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# TC-DS02-003: GDP=0 → 결측 간주 → 제외
# ---------------------------------------------------------------------------

class TestGDPZero:
    def test_gdp_zero_excluded(self):
        """GDP=0은 결측 간주 → is_valid_for_scoring=False."""
        rec = _rec("ZZZ", "Zero GDP", gdp=0.0)
        assert not rec.is_valid_for_scoring

        results = DS02Scorer([rec]).score_all()
        assert results[0].excluded


# ---------------------------------------------------------------------------
# TC-DS02-004: GDP < 0 → 이상값 → 제외
# ---------------------------------------------------------------------------

class TestGDPNegative:
    def test_negative_gdp_excluded(self):
        rec = _rec("NEG", "Negative", gdp=-100.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].excluded
        assert "anomaly" in results[0].exclude_reason.lower()

    def test_negative_gdp_warning(self):
        rec = _rec("NEG", "Negative", gdp=-100.0)
        assert any("GDP ≤ 0" in w for w in rec.warnings())


# ---------------------------------------------------------------------------
# TC-DS02-005: GDP growth 결측 → 0점 처리 (국가 유지)
# ---------------------------------------------------------------------------

class TestGrowthMissing:
    def test_growth_missing_not_excluded(self):
        rec = _rec("MMR", "Myanmar", gdp=80e9, gdp_growth=None)
        results = DS02Scorer([rec]).score_all()
        assert not results[0].excluded
        assert results[0].norm_gdp_growth is None

    def test_growth_missing_lower_score(self):
        """growth 결측 → GDP만으로 점수 산정 → 완전 데이터보다 낮음."""
        full = _rec("VNM", "Vietnam", gdp=430e9, gdp_growth=5.1)
        partial = _rec("VN2", "Vietnam2", gdp=430e9, gdp_growth=None)
        results = DS02Scorer([full, partial]).score_all()
        by = {r.country_iso3: r for r in results}
        assert by["VN2"].economic_score < by["VNM"].economic_score

    def test_growth_missing_in_fields(self):
        rec = _rec("MMR", "Myanmar", gdp=80e9, gdp_growth=None)
        assert "gdp_growth_pct" in rec.missing_fields


# ---------------------------------------------------------------------------
# TC-DS02-006: Growth 클리핑 상한 (15% → 10% → norm=1.0)
# ---------------------------------------------------------------------------

class TestClippingUpper:
    def test_growth_15_clips_to_10(self):
        rec = _rec("AAA", "Fast", gdp=100e9, gdp_growth=15.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].norm_gdp_growth == pytest.approx(1.0)

    def test_growth_10_is_max(self):
        rec = _rec("BBB", "Max", gdp=100e9, gdp_growth=10.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].norm_gdp_growth == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TC-DS02-007: Growth 클리핑 하한 (-10% → -5% → norm=0.0)
# ---------------------------------------------------------------------------

class TestClippingLower:
    def test_growth_neg10_clips_to_neg5(self):
        rec = _rec("CCC", "Decline", gdp=100e9, gdp_growth=-10.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].norm_gdp_growth == pytest.approx(0.0)

    def test_growth_neg5_is_min(self):
        rec = _rec("DDD", "Min", gdp=100e9, gdp_growth=-5.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].norm_gdp_growth == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Growth 중간값 검증
# ---------------------------------------------------------------------------

class TestClippingMid:
    def test_growth_zero_normalized(self):
        """GDP growth 0% → (0+5)/15 ≈ 0.333."""
        rec = _rec("EEE", "Flat", gdp=100e9, gdp_growth=0.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].norm_gdp_growth == pytest.approx(5.0 / 15.0)

    def test_growth_5_normalized(self):
        """GDP growth 5% → (5+5)/15 ≈ 0.667."""
        rec = _rec("FFF", "Mid", gdp=100e9, gdp_growth=5.0)
        results = DS02Scorer([rec]).score_all()
        assert results[0].norm_gdp_growth == pytest.approx(10.0 / 15.0)


# ---------------------------------------------------------------------------
# 가중치 검증
# ---------------------------------------------------------------------------

class TestWeights:
    def test_weights_sum_to_one(self):
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)

    def test_weight_count(self):
        assert len(WEIGHTS) == 2

    def test_gdp_weight_dominant(self):
        """GDP 가중치가 growth보다 높음."""
        assert WEIGHTS["gdp_usd"] > WEIGHTS["gdp_growth_pct"]


# ---------------------------------------------------------------------------
# DS02Record 유틸리티
# ---------------------------------------------------------------------------

class TestDS02Record:
    def test_missing_fields_partial(self):
        rec = _rec("AAA", "Test", gdp=100e9, gdp_growth=None)
        assert rec.missing_fields == ["gdp_growth_pct"]

    def test_missing_fields_none(self):
        rec = _rec("BBB", "Full")
        assert rec.missing_fields == []

    def test_is_valid_true(self):
        rec = _rec("VNM", "Vietnam")
        assert rec.is_valid_for_scoring

    def test_is_valid_false_no_gdp(self):
        rec = _rec("XXX", "No GDP", gdp=None)
        assert not rec.is_valid_for_scoring

    def test_wsb_fields_count(self):
        assert len(WSB_FIELDS) == 2


# ---------------------------------------------------------------------------
# NormalizedDS02 직렬화
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_structure(self):
        results = DS02Scorer([_rec("VNM", "Vietnam")]).score_all()
        d = results[0].to_dict()

        assert d["country_iso3"] == "VNM"
        assert d["country_name"] == "Vietnam"
        assert "economic_score" in d
        assert "indicators" in d
        assert "gdp_usd" in d["indicators"]
        assert "gdp_growth_pct" in d["indicators"]
        assert "normalized" in d
        assert "norm_gdp" in d["normalized"]
        assert "norm_gdp_growth" in d["normalized"]
        assert "data_quality" in d

    def test_to_dict_score_positive(self):
        results = DS02Scorer(_multi()).score_all()
        for r in results:
            d = r.to_dict()
            assert d["economic_score"] >= 0.0
