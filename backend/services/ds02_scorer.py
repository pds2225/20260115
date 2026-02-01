"""
DS-02 EconomicScore 산정 모듈.

WSB 기준 정규화 + 가중합으로 EconomicScore를 계산한다.
수식은 docs/DS02_WSB_SPEC.md 7장에 고정.

참조:
  - 정규화: 6장 (로그 스케일 + 클리핑)
  - 가중치: 7장 (0.30/0.25/0.20/0.15/-0.10)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from backend.data.ds02_worldbank import DS02Record, WSB_INDICATORS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 클리핑 범위 (고정)
# ---------------------------------------------------------------------------

CLIP_RANGES: dict[str, tuple[float, float]] = {
    "gdp_growth_pct": (-5.0, 10.0),
    "import_growth_pct": (-5.0, 15.0),
    "inflation_pct": (0.0, 15.0),
}

# ---------------------------------------------------------------------------
# EconomicScore 가중치 (고정, 합계 = 1.00)
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "gdp_usd": 0.30,           # + 시장 규모
    "import_value_usd": 0.25,  # + 수입 수요
    "gdp_growth_pct": 0.20,    # + 성장성
    "import_growth_pct": 0.15, # + 수요 증가
    "inflation_pct": -0.10,    # - 리스크 감점
}

# 로그 정규화 대상
LOG_NORM_FIELDS = {"gdp_usd", "import_value_usd", "population"}

# 클리핑 정규화 대상
CLIP_NORM_FIELDS = {"gdp_growth_pct", "import_growth_pct", "inflation_pct"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NormalizedDS02:
    """정규화된 DS-02 데이터 + EconomicScore."""

    country_iso3: str
    year: int | None

    # 원본 값
    raw_indicators: dict[str, float | None] = field(default_factory=dict)

    # 정규화된 값 (0~1)
    norm_gdp: float | None = None
    norm_import_value: float | None = None
    norm_gdp_growth: float | None = None
    norm_import_growth: float | None = None
    norm_inflation: float | None = None
    norm_population: float | None = None

    # 최종 점수
    economic_score: float = 0.0

    # 데이터 품질
    missing_fields: list[str] = field(default_factory=list)
    stale_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    excluded: bool = False
    exclude_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """API 응답용 직렬화."""
        return {
            "country_iso3": self.country_iso3,
            "year": self.year,
            "indicators": self.raw_indicators,
            "normalized": {
                "norm_gdp": self.norm_gdp,
                "norm_import_value": self.norm_import_value,
                "norm_gdp_growth": self.norm_gdp_growth,
                "norm_import_growth": self.norm_import_growth,
                "norm_inflation": self.norm_inflation,
                "norm_population": self.norm_population,
            },
            "economic_score": self.economic_score,
            "data_quality": {
                "missing_fields": self.missing_fields,
                "stale_fields": self.stale_fields,
                "warnings": self.warnings,
            },
        }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class DS02Scorer:
    """
    DS-02 EconomicScore 산정기.

    사용법:
        scorer = DS02Scorer(records)
        results = scorer.score_all()
    """

    def __init__(self, records: list[DS02Record]):
        self.records = records
        # 로그 정규화용 min/max 캐시
        self._log_stats: dict[str, tuple[float, float]] = {}

    def _compute_log_stats(self) -> None:
        """로그 정규화 대상 필드의 min_log/max_log 계산."""
        for field_name in LOG_NORM_FIELDS:
            values = []
            for rec in self.records:
                v = rec.get_value(field_name)
                if v is not None and v > 0:
                    values.append(math.log(v))

            if values:
                self._log_stats[field_name] = (min(values), max(values))
            else:
                self._log_stats[field_name] = (0.0, 1.0)

    def _norm_log(self, value: float | None, field_name: str) -> float | None:
        """로그 스케일 정규화: (log(x) - min_log) / (max_log - min_log)."""
        if value is None or value <= 0:
            return None

        min_log, max_log = self._log_stats.get(field_name, (0.0, 1.0))
        log_val = math.log(value)

        denom = max_log - min_log
        if denom == 0:
            return 0.5  # 모든 값 동일

        return max(0.0, min(1.0, (log_val - min_log) / denom))

    @staticmethod
    def _norm_clip(value: float | None, field_name: str) -> float | None:
        """클리핑 + 0-1 정규화."""
        if value is None:
            return None

        lower, upper = CLIP_RANGES[field_name]
        clipped = max(lower, min(upper, value))

        denom = upper - lower
        if denom == 0:
            return 0.0

        return (clipped - lower) / denom

    def _compute_economic_score(self, norm: NormalizedDS02) -> float:
        """
        EconomicScore 가중합 산정 (수식 고정).

        score = 0.30*norm_gdp + 0.25*norm_import
              + 0.20*norm_gdp_growth + 0.15*norm_import_growth
              - 0.10*norm_inflation

        결측 항목은 기여분 = 0 (가중치 재분배 없음).
        결과는 max(0, score) 적용.
        """
        score = 0.0

        # GDP (+ 0.30)
        if norm.norm_gdp is not None:
            score += WEIGHTS["gdp_usd"] * norm.norm_gdp

        # Import value (+ 0.25)
        if norm.norm_import_value is not None:
            score += WEIGHTS["import_value_usd"] * norm.norm_import_value

        # GDP growth (+ 0.20)
        if norm.norm_gdp_growth is not None:
            score += WEIGHTS["gdp_growth_pct"] * norm.norm_gdp_growth

        # Import growth (+ 0.15)
        if norm.norm_import_growth is not None:
            score += WEIGHTS["import_growth_pct"] * norm.norm_import_growth

        # Inflation (- 0.10)
        if norm.norm_inflation is not None:
            score += WEIGHTS["inflation_pct"] * norm.norm_inflation  # 가중치가 음수

        return max(0.0, score)

    def score_all(self) -> list[NormalizedDS02]:
        """
        전체 레코드에 대해 정규화 + EconomicScore 산정.

        Returns:
            NormalizedDS02 리스트 (excluded=True인 항목 포함).
        """
        # 1. 로그 정규화 통계 계산 (유효 레코드 기준)
        valid_records = [r for r in self.records if r.is_valid_for_scoring]
        temp_scorer = DS02Scorer(valid_records)
        temp_scorer.records = valid_records
        self._compute_log_stats_from(valid_records)

        results: list[NormalizedDS02] = []

        for rec in self.records:
            norm = NormalizedDS02(
                country_iso3=rec.country_iso3,
                year=rec.get_year("gdp_usd"),
                raw_indicators={
                    name: rec.get_value(name) for name in WSB_INDICATORS
                },
                missing_fields=rec.missing_fields,
                warnings=rec.warnings(),
            )

            # 필수 지표 결측 → 제외
            if not rec.is_valid_for_scoring:
                norm.excluded = True
                gdp = rec.get_value("gdp_usd")
                imp = rec.get_value("import_value_usd")
                if gdp is None:
                    norm.exclude_reason = "GDP missing"
                elif gdp <= 0:
                    norm.exclude_reason = f"GDP anomaly ({gdp})"
                elif imp is None:
                    norm.exclude_reason = "Import value missing"
                elif imp < 0:
                    norm.exclude_reason = f"Import value anomaly ({imp})"
                else:
                    norm.exclude_reason = "Required indicators missing"
                results.append(norm)
                continue

            # 정규화
            norm.norm_gdp = self._norm_log(
                rec.get_value("gdp_usd"), "gdp_usd",
            )
            norm.norm_import_value = self._norm_log(
                rec.get_value("import_value_usd"), "import_value_usd",
            )
            norm.norm_population = self._norm_log(
                rec.get_value("population"), "population",
            )
            norm.norm_gdp_growth = self._norm_clip(
                rec.get_value("gdp_growth_pct"), "gdp_growth_pct",
            )
            norm.norm_import_growth = self._norm_clip(
                rec.get_value("import_growth_pct"), "import_growth_pct",
            )
            norm.norm_inflation = self._norm_clip(
                rec.get_value("inflation_pct"), "inflation_pct",
            )

            # EconomicScore 산정
            norm.economic_score = self._compute_economic_score(norm)

            results.append(norm)

        scored_count = sum(1 for r in results if not r.excluded)
        excluded_count = sum(1 for r in results if r.excluded)
        logger.info(
            "DS-02 Scoring: %d scored, %d excluded (total %d)",
            scored_count, excluded_count, len(results),
        )

        return results

    def _compute_log_stats_from(self, records: list[DS02Record]) -> None:
        """유효 레코드 기준 로그 통계 계산."""
        for field_name in LOG_NORM_FIELDS:
            values = []
            for rec in records:
                v = rec.get_value(field_name)
                if v is not None and v > 0:
                    values.append(math.log(v))

            if values:
                self._log_stats[field_name] = (min(values), max(values))
            else:
                self._log_stats[field_name] = (0.0, 1.0)
