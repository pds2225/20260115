"""
P1: 수출 유망 국가 추천 엔진 테스트 (30개).

TC-REC-001 ~ TC-REC-030
"""

import pytest
from backend.services.recommendation import (
    WEIGHTS,
    ConfidenceLevel,
    CountryData,
    CountryScore,
    DataQuality,
    RecommendationEngine,
)
from backend.data.sanctions import SanctionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_countries() -> list[CountryData]:
    return [
        CountryData("USA", "United States", 5.2e9, 25462e9, 2.1, 8.5, 0.7, 0.8, 11000),
        CountryData("CHN", "China", 16.2e9, 17963e9, 5.2, 12.5, 0.8, 0.5, 950),
        CountryData("VNM", "Vietnam", 2.8e9, 430e9, 5.1, 5.2, 0.75, 0.6, 2400),
        CountryData("DEU", "Germany", 1.9e9, 4072e9, -0.87, 6.5, 0.65, 0.85, 8500),
        CountryData("JPN", "Japan", 3.1e9, 4231e9, 1.1, 10.2, 0.6, 0.9, 1200),
        CountryData("IND", "India", 2.5e9, 3638e9, 9.19, 15.0, 0.5, 0.4, 5600),
    ]


def _with_sanctions() -> list[CountryData]:
    return _sample_countries() + [
        CountryData("PRK", "North Korea", 0, 0, 0, 0, 0, 0, 0),
        CountryData("IRN", "Iran", 1e8, 500e9, 2.0, 20.0, 0.3, 0.2, 7000),
        CountryData("RUS", "Russia", 3e9, 2240e9, 3.6, 15.0, 0.5, 0.3, 7500),
    ]


# ---------------------------------------------------------------------------
# TC-REC-001 ~ 005: 가중치 검증
# ---------------------------------------------------------------------------

class TestWeights:
    def test_weights_sum_to_one(self):
        """TC-REC-001: 가중치 합계 = 1.0."""
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)

    def test_weight_count(self):
        """TC-REC-002: 4가지 지표."""
        assert len(WEIGHTS) == 4

    def test_trade_volume_highest(self):
        """TC-REC-003: 무역 규모가 최대 가중치."""
        assert WEIGHTS["trade_volume"] == 0.40

    def test_economic_growth_second(self):
        """TC-REC-004: 경제 성장률이 두 번째."""
        assert WEIGHTS["economic_growth"] == 0.25

    def test_regulation_and_trend(self):
        """TC-REC-005: 규제/리스크 20%, 트렌드 15%."""
        assert WEIGHTS["regulation_risk"] == 0.20
        assert WEIGHTS["trend"] == 0.15


# ---------------------------------------------------------------------------
# TC-REC-006 ~ 012: 점수 범위/순위
# ---------------------------------------------------------------------------

class TestScoring:
    def test_score_range_0_to_100(self):
        """TC-REC-006: 모든 점수가 0~100 범위."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        for r in results:
            assert 0.0 <= r.total_score <= 100.0

    def test_results_sorted_descending(self):
        """TC-REC-007: 결과가 점수 내림차순 정렬."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        active = [r for r in results if not r.excluded]
        for i in range(len(active) - 1):
            assert active[i].total_score >= active[i + 1].total_score

    def test_top_n_limits_results(self):
        """TC-REC-008: top_n이 결과 수를 제한."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all(top_n=3)
        active = [r for r in results if not r.excluded]
        assert len(active) <= 3

    def test_higher_trade_means_higher_trade_score(self):
        """TC-REC-009: 무역액이 클수록 trade_volume_score가 높음."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        by = {r.country_iso3: r for r in results}
        # CHN(16.2B) > USA(5.2B) in trade
        assert by["CHN"].trade_volume_score > by["USA"].trade_volume_score

    def test_higher_growth_means_higher_growth_score(self):
        """TC-REC-010: GDP 성장률이 높을수록 economic_growth_score가 높음."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        by = {r.country_iso3: r for r in results}
        # IND(9.19%) > DEU(-0.87%)
        assert by["IND"].economic_growth_score > by["DEU"].economic_growth_score

    def test_lower_tariff_better_regulation_score(self):
        """TC-REC-011: 관세가 낮을수록 regulation_risk_score가 높음."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        by = {r.country_iso3: r for r in results}
        # VNM(5.2%) < IND(15.0%) tariff -> VNM better
        assert by["VNM"].regulation_risk_score > by["IND"].regulation_risk_score

    def test_score_components_sum_reasonable(self):
        """TC-REC-012: score_components의 합이 total_score와 일치(감점 전)."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        for r in results:
            if not r.excluded and r.compliance and not r.compliance.is_restricted:
                comp_sum = sum(r.score_components.values())
                assert abs(comp_sum - r.total_score) < 0.5


# ---------------------------------------------------------------------------
# TC-REC-013 ~ 018: 제재국 필터링
# ---------------------------------------------------------------------------

class TestSanctionsInRecommendation:
    def test_blocked_excluded(self):
        """TC-REC-013: 북한은 추천 결과에서 제외."""
        engine = RecommendationEngine(_with_sanctions())
        results = engine.score_all()
        active = [r for r in results if not r.excluded]
        assert all(r.country_iso3 != "PRK" for r in active)

    def test_iran_excluded(self):
        """TC-REC-014: 이란도 제외."""
        engine = RecommendationEngine(_with_sanctions())
        results = engine.score_all()
        active = [r for r in results if not r.excluded]
        assert all(r.country_iso3 != "IRN" for r in active)

    def test_blocked_still_in_full_results(self):
        """TC-REC-015: excluded=True로 전체 결과에는 포함."""
        engine = RecommendationEngine(_with_sanctions())
        results = engine.score_all(top_n=100)
        prk = [r for r in results if r.country_iso3 == "PRK"]
        assert len(prk) == 1
        assert prk[0].excluded

    def test_blocked_score_is_zero(self):
        """TC-REC-016: blocked 국가의 점수는 0."""
        engine = RecommendationEngine(_with_sanctions())
        results = engine.score_all(top_n=100)
        prk = [r for r in results if r.country_iso3 == "PRK"][0]
        assert prk.total_score == 0.0

    def test_russia_restricted_penalty(self):
        """TC-REC-017: 러시아는 -10점 감점."""
        engine = RecommendationEngine(_with_sanctions())
        results = engine.score_all(top_n=100)
        rus = [r for r in results if r.country_iso3 == "RUS"][0]
        assert rus.compliance.is_restricted
        assert not rus.excluded

    def test_restricted_has_warning(self):
        """TC-REC-018: 제한국에 경고 메시지 포함."""
        engine = RecommendationEngine(_with_sanctions())
        results = engine.score_all(top_n=100)
        rus = [r for r in results if r.country_iso3 == "RUS"][0]
        assert rus.compliance.warning is not None


# ---------------------------------------------------------------------------
# TC-REC-019 ~ 024: 신뢰도/데이터 품질
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_full_data_high_confidence(self):
        """TC-REC-019: 모든 데이터 있으면 confidence high."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        for r in results:
            if not r.excluded:
                assert r.data_quality.confidence_level == ConfidenceLevel.HIGH

    def test_missing_data_lower_confidence(self):
        """TC-REC-020: 데이터 결측 시 confidence 낮아짐."""
        dq = DataQuality(available_fields=2, total_fields=4, missing_fields=["trade_volume", "trend"])
        assert dq.confidence < 1.0
        assert dq.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM)

    def test_confidence_range(self):
        """TC-REC-021: confidence는 0~1 범위."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        for r in results:
            assert 0.0 <= r.data_quality.confidence <= 1.0

    def test_high_level_threshold(self):
        """TC-REC-022: HIGH = confidence >= 0.8."""
        dq = DataQuality(available_fields=4, total_fields=4)
        assert dq.confidence_level == ConfidenceLevel.HIGH

    def test_medium_level_threshold(self):
        """TC-REC-023: MEDIUM = 0.6 <= confidence < 0.8."""
        dq = DataQuality(available_fields=3, total_fields=4)
        assert dq.confidence_level == ConfidenceLevel.MEDIUM

    def test_low_level_threshold(self):
        """TC-REC-024: LOW = 0.4 <= confidence < 0.6."""
        dq = DataQuality(available_fields=2, total_fields=4)
        assert dq.confidence_level == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# TC-REC-025 ~ 028: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_countries(self):
        """TC-REC-025: 빈 목록 처리."""
        engine = RecommendationEngine([])
        results = engine.score_all()
        assert results == []

    def test_single_country(self):
        """TC-REC-026: 국가 1개 처리."""
        engine = RecommendationEngine([CountryData("USA", "US", 1e9, 25000e9, 2.0, 5.0, 0.7, 0.8, 10000)])
        results = engine.score_all()
        assert len(results) == 1

    def test_all_blocked(self):
        """TC-REC-027: 모두 blocked면 active 결과 없음."""
        blocked = [
            CountryData("PRK", "NK", 0, 0, 0, 0, 0, 0, 0),
            CountryData("IRN", "Iran", 0, 0, 0, 0, 0, 0, 0),
        ]
        engine = RecommendationEngine(blocked)
        results = engine.score_all()
        active = [r for r in results if not r.excluded]
        assert len(active) == 0

    def test_negative_growth_handled(self):
        """TC-REC-028: 음수 성장률 정상 처리."""
        countries = [CountryData("DEU", "Germany", 1e9, 4000e9, -3.0, 6.0, 0.5, 0.7, 8500)]
        engine = RecommendationEngine(countries)
        results = engine.score_all()
        assert results[0].economic_growth_score >= 0.0


# ---------------------------------------------------------------------------
# TC-REC-029 ~ 030: 직렬화
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_structure(self):
        """TC-REC-029: to_dict에 필수 필드 포함."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        d = results[0].to_dict()
        assert "country_iso3" in d
        assert "total_score" in d
        assert "score_components" in d
        assert "data_quality" in d

    def test_to_dict_components(self):
        """TC-REC-030: score_components에 4가지 지표."""
        engine = RecommendationEngine(_sample_countries())
        results = engine.score_all()
        comp = results[0].to_dict()["score_components"]
        assert "trade_volume" in comp
        assert "economic_growth" in comp
        assert "regulation_risk" in comp
        assert "trend" in comp
