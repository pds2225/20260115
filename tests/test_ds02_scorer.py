"""
DS-02 EconomicScore 테스트.

테스트 시나리오는 docs/DS02_WSB_SPEC.md 13장 기반.
"""

import math
import pytest

from backend.data.ds02_worldbank import DS02Record
from backend.services.ds02_scorer import (
    CLIP_RANGES,
    WEIGHTS,
    DS02Scorer,
    NormalizedDS02,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_record(
    iso3: str = "VNM",
    gdp: float | None = 430e9,
    gdp_pc: float | None = 4400.0,
    gdp_growth: float | None = 5.1,
    import_val: float | None = 345e9,
    import_growth: float | None = 8.2,
    inflation: float | None = 3.4,
    population: float | None = 100_300_000,
    year: int = 2023,
) -> DS02Record:
    rec = DS02Record(
        country_iso3=iso3,
        country_iso2="VN",
        snapshot_date="2026-01-28",
    )
    if gdp is not None:
        rec.gdp_usd = (gdp, year)
    if gdp_pc is not None:
        rec.gdp_per_capita_usd = (gdp_pc, year)
    if gdp_growth is not None:
        rec.gdp_growth_pct = (gdp_growth, year)
    if import_val is not None:
        rec.import_value_usd = (import_val, year)
    if import_growth is not None:
        rec.import_growth_pct = (import_growth, year)
    if inflation is not None:
        rec.inflation_pct = (inflation, year)
    if population is not None:
        rec.population = (population, year)
    return rec


def _make_multi_records() -> list[DS02Record]:
    """여러 국가 레코드 (정규화 min-max 테스트용)."""
    return [
        _make_record("VNM", gdp=430e9, import_val=345e9, gdp_growth=5.1,
                      import_growth=8.2, inflation=3.4, population=100e6),
        _make_record("USA", gdp=25462e9, import_val=3800e9, gdp_growth=2.1,
                      import_growth=3.5, inflation=4.1, population=333e6),
        _make_record("DEU", gdp=4072e9, import_val=1600e9, gdp_growth=0.3,
                      import_growth=-1.2, inflation=5.9, population=84e6),
        _make_record("CHN", gdp=17963e9, import_val=2700e9, gdp_growth=5.2,
                      import_growth=1.8, inflation=0.2, population=1400e6),
    ]


# ---------------------------------------------------------------------------
# TC-DS02-001: 정상 수집 및 점수 산정
# ---------------------------------------------------------------------------

class TestNormalScoring:
    def test_score_range(self):
        """EconomicScore는 0 ~ 1 범위."""
        records = _make_multi_records()
        scorer = DS02Scorer(records)
        results = scorer.score_all()

        for r in results:
            assert not r.excluded
            assert 0.0 <= r.economic_score <= 1.0, (
                f"{r.country_iso3}: score={r.economic_score} out of range"
            )

    def test_no_missing_fields_when_complete(self):
        """모든 지표 제공 시 missing_fields 비어있음."""
        records = _make_multi_records()
        scorer = DS02Scorer(records)
        results = scorer.score_all()

        for r in results:
            assert r.missing_fields == [], f"{r.country_iso3} has missing: {r.missing_fields}"

    def test_normalized_values_range(self):
        """정규화 값은 0~1 범위."""
        records = _make_multi_records()
        scorer = DS02Scorer(records)
        results = scorer.score_all()

        for r in results:
            for attr in ["norm_gdp", "norm_import_value", "norm_gdp_growth",
                         "norm_import_growth", "norm_inflation"]:
                val = getattr(r, attr)
                if val is not None:
                    assert 0.0 <= val <= 1.0, f"{r.country_iso3}.{attr}={val}"

    def test_higher_gdp_higher_score(self):
        """GDP가 큰 국가가 더 높은 norm_gdp."""
        records = _make_multi_records()
        scorer = DS02Scorer(records)
        results = scorer.score_all()

        by_iso3 = {r.country_iso3: r for r in results}
        assert by_iso3["USA"].norm_gdp > by_iso3["VNM"].norm_gdp


# ---------------------------------------------------------------------------
# TC-DS02-002: 필수 지표 결측 → 후보군 제외
# ---------------------------------------------------------------------------

class TestMandatoryMissing:
    def test_gdp_missing_excluded(self):
        """GDP 결측 → excluded=True."""
        rec = _make_record("XXX", gdp=None)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert len(results) == 1
        assert results[0].excluded
        assert "GDP missing" in results[0].exclude_reason

    def test_import_missing_excluded(self):
        """Import value 결측 → excluded=True."""
        rec = _make_record("YYY", import_val=None)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].excluded
        assert "Import value missing" in results[0].exclude_reason


# ---------------------------------------------------------------------------
# TC-DS02-003: 선택 지표 결측 → 0점 처리
# ---------------------------------------------------------------------------

class TestOptionalMissing:
    def test_growth_missing_still_scored(self):
        """GDP growth, inflation 결측 → 점수 산출됨 (해당 항목 0 기여)."""
        rec = _make_record("MMR", gdp_growth=None, inflation=None)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert not results[0].excluded
        assert results[0].economic_score > 0
        assert results[0].norm_gdp_growth is None
        assert results[0].norm_inflation is None
        assert "gdp_growth_pct" in results[0].missing_fields
        assert "inflation_pct" in results[0].missing_fields

    def test_optional_missing_lower_score(self):
        """선택 지표 결측 시 점수가 완전 데이터보다 낮음."""
        full = _make_record("VNM")
        partial = _make_record("VN2", gdp_growth=None, import_growth=None, inflation=None)
        # 동일 GDP/Import로 비교하려면 같은 배치에서 정규화
        scorer = DS02Scorer([full, partial])
        results = scorer.score_all()

        by_iso3 = {r.country_iso3: r for r in results}
        assert by_iso3["VN2"].economic_score < by_iso3["VNM"].economic_score


# ---------------------------------------------------------------------------
# TC-DS02-005: 이상값 (GDP ≤ 0)
# ---------------------------------------------------------------------------

class TestAnomalies:
    def test_negative_gdp_excluded(self):
        """GDP ≤ 0 → 이상값 → excluded."""
        rec = _make_record("ZZZ", gdp=-100.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].excluded
        assert "anomaly" in results[0].exclude_reason.lower()

    def test_zero_gdp_excluded(self):
        """GDP = 0 → excluded."""
        rec = _make_record("ZZZ", gdp=0.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()
        assert results[0].excluded

    def test_negative_import_excluded(self):
        """Import value < 0 → excluded."""
        rec = _make_record("ZZZ", import_val=-500.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()
        assert results[0].excluded


# ---------------------------------------------------------------------------
# TC-DS02-006: 클리핑 경계값
# ---------------------------------------------------------------------------

class TestClipping:
    def test_gdp_growth_clip_upper(self):
        """GDP growth 15% → clip to 10% → norm = 1.0."""
        rec = _make_record("AAA", gdp_growth=15.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].norm_gdp_growth == pytest.approx(1.0)

    def test_gdp_growth_clip_lower(self):
        """GDP growth -10% → clip to -5% → norm = 0.0."""
        rec = _make_record("BBB", gdp_growth=-10.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].norm_gdp_growth == pytest.approx(0.0)

    def test_inflation_clip_range(self):
        """Inflation 20% → clip to 15% → norm = 1.0."""
        rec = _make_record("CCC", inflation=20.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].norm_inflation == pytest.approx(1.0)

    def test_inflation_negative_clipped_to_zero(self):
        """Inflation -2% → clip to 0% → norm = 0.0."""
        rec = _make_record("DDD", inflation=-2.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].norm_inflation == pytest.approx(0.0)

    def test_import_growth_midpoint(self):
        """Import growth 5% → clip(5, -5, 15) → norm = (5+5)/20 = 0.5."""
        rec = _make_record("EEE", import_growth=5.0)
        scorer = DS02Scorer([rec])
        results = scorer.score_all()

        assert results[0].norm_import_growth == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# TC-DS02-007: EconomicScore 최소값 클램핑
# ---------------------------------------------------------------------------

class TestScoreFloor:
    def test_min_zero_clamping(self):
        """모든 양(+) 항목 최소, Inflation 최대 → score ≥ 0."""
        # 가장 작은 GDP/Import + 가장 높은 인플레이션
        records = [
            _make_record("MIN", gdp=1e6, import_val=1e6,
                         gdp_growth=-5.0, import_growth=-5.0, inflation=15.0),
            _make_record("MAX", gdp=25000e9, import_val=5000e9,
                         gdp_growth=10.0, import_growth=15.0, inflation=0.0),
        ]
        scorer = DS02Scorer(records)
        results = scorer.score_all()

        by_iso3 = {r.country_iso3: r for r in results}
        assert by_iso3["MIN"].economic_score >= 0.0
        assert by_iso3["MAX"].economic_score > by_iso3["MIN"].economic_score


# ---------------------------------------------------------------------------
# 가중치 합계 검증
# ---------------------------------------------------------------------------

class TestWeights:
    def test_weights_sum_to_one(self):
        """가중치 절대값 합계 = 1.00."""
        total = sum(abs(w) for w in WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_weight_count(self):
        """가중치는 정확히 5개."""
        assert len(WEIGHTS) == 5


# ---------------------------------------------------------------------------
# DS02Record 유틸리티 테스트
# ---------------------------------------------------------------------------

class TestDS02Record:
    def test_missing_fields(self):
        rec = _make_record("AAA", gdp_growth=None, inflation=None)
        assert "gdp_growth_pct" in rec.missing_fields
        assert "inflation_pct" in rec.missing_fields
        assert "gdp_usd" not in rec.missing_fields

    def test_is_valid_for_scoring_true(self):
        rec = _make_record("VNM")
        assert rec.is_valid_for_scoring

    def test_is_valid_for_scoring_false_no_gdp(self):
        rec = _make_record("XXX", gdp=None)
        assert not rec.is_valid_for_scoring

    def test_warnings_anomaly(self):
        rec = _make_record("ZZZ", gdp=-100.0)
        w = rec.warnings()
        assert any("GDP ≤ 0" in msg for msg in w)

    def test_to_dict(self):
        records = [_make_record("VNM")]
        scorer = DS02Scorer(records)
        results = scorer.score_all()
        d = results[0].to_dict()

        assert d["country_iso3"] == "VNM"
        assert "economic_score" in d
        assert "data_quality" in d
        assert isinstance(d["normalized"], dict)


# ---------------------------------------------------------------------------
# 연도 선택 규칙 테스트
# ---------------------------------------------------------------------------

class TestYearSelection:
    def test_latest_year_selected(self):
        """가장 최신 연도의 값이 선택됨."""
        rec = DS02Record(
            country_iso3="KOR",
            country_iso2="KR",
            snapshot_date="2026-01-28",
        )
        rec.gdp_usd = (1800e9, 2023)
        rec.import_value_usd = (700e9, 2022)

        assert rec.get_year("gdp_usd") == 2023
        assert rec.get_year("import_value_usd") == 2022
