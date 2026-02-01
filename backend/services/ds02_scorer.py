"""
DS-02 EconomicScore 산정 모듈 (v1 확정: 2개 지표).

v1 확정 지표:
  - GDP (current USD) → 로그 스케일 min-max 정규화
  - GDP growth (annual %) → 클리핑(-5%~+10%) + 0-1 정규화

EconomicScore = w1 * norm(GDP) + w2 * norm_clip(GDP_growth)

참조: docs/DS02_WSB_SPEC.md
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from backend.data.ds02_worldbank import DS02Record, WSB_FIELDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 클리핑 범위 (고정)
# ---------------------------------------------------------------------------

CLIP_RANGES: dict[str, tuple[float, float]] = {
    "gdp_growth_pct": (-5.0, 10.0),
}

# ---------------------------------------------------------------------------
# EconomicScore 가중치 (v1 확정, 2개 지표)
#
# GDP가 시장규모의 핵심 지표이므로 비중 높게 설정.
# GDP growth는 성장성 보정용.
# 합계 = 1.00
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "gdp_usd": 0.70,          # + 시장 규모 (로그 정규화)
    "gdp_growth_pct": 0.30,   # + 성장성 (클리핑 정규화)
}

# 로그 정규화 대상
LOG_NORM_FIELDS = {"gdp_usd"}

# 클리핑 정규화 대상
CLIP_NORM_FIELDS = {"gdp_growth_pct"}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class NormalizedDS02:
    """정규화된 DS-02 데이터 + EconomicScore."""

    country_iso3: str
    country_name: str
    year: int | None

    # 원본 값
    raw_gdp_usd: float | None = None
    raw_gdp_growth_pct: float | None = None

    # 정규화된 값 (0~1)
    norm_gdp: float | None = None
    norm_gdp_growth: float | None = None

    # 최종 점수
    economic_score: float = 0.0

    # 데이터 품질
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    excluded: bool = False
    exclude_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """API 응답용 직렬화."""
        return {
            "country_iso3": self.country_iso3,
            "country_name": self.country_name,
            "year": self.year,
            "indicators": {
                "gdp_usd": self.raw_gdp_usd,
                "gdp_growth_pct": self.raw_gdp_growth_pct,
            },
            "normalized": {
                "norm_gdp": self.norm_gdp,
                "norm_gdp_growth": self.norm_gdp_growth,
            },
            "economic_score": self.economic_score,
            "data_quality": {
                "missing_fields": self.missing_fields,
                "warnings": self.warnings,
            },
        }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class DS02Scorer:
    """
    DS-02 EconomicScore 산정기 (v1: GDP + GDP growth).

    사용법:
        scorer = DS02Scorer(records)
        results = scorer.score_all()
    """

    def __init__(self, records: list[DS02Record]):
        self.records = records
        self._log_stats: dict[str, tuple[float, float]] = {}

    def _compute_log_stats(self, records: list[DS02Record]) -> None:
        """유효 레코드 기준 로그 min/max 계산."""
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

    @staticmethod
    def _compute_economic_score(norm: NormalizedDS02) -> float:
        """
        EconomicScore 가중합 산정 (v1 수식 고정).

        score = 0.70 * norm(GDP) + 0.30 * norm_clip(GDP_growth)

        결측 항목은 기여분 = 0 (가중치 재분배 없음).
        결과는 max(0, score) 적용.
        """
        score = 0.0

        if norm.norm_gdp is not None:
            score += WEIGHTS["gdp_usd"] * norm.norm_gdp

        if norm.norm_gdp_growth is not None:
            score += WEIGHTS["gdp_growth_pct"] * norm.norm_gdp_growth

        return max(0.0, score)

    def score_all(self) -> list[NormalizedDS02]:
        """
        전체 레코드에 대해 정규화 + EconomicScore 산정.

        Returns:
            NormalizedDS02 리스트 (excluded=True인 항목 포함).
        """
        # 유효 레코드 기준으로 로그 통계 계산
        valid_records = [r for r in self.records if r.is_valid_for_scoring]
        self._compute_log_stats(valid_records)

        results: list[NormalizedDS02] = []

        for rec in self.records:
            norm = NormalizedDS02(
                country_iso3=rec.country_iso3,
                country_name=rec.country_name,
                year=rec.get_year("gdp_usd"),
                raw_gdp_usd=rec.get_value("gdp_usd"),
                raw_gdp_growth_pct=rec.get_value("gdp_growth_pct"),
                missing_fields=rec.missing_fields,
                warnings=rec.warnings(),
            )

            # 필수 지표(GDP) 결측/이상 → 제외
            if not rec.is_valid_for_scoring:
                norm.excluded = True
                gdp = rec.get_value("gdp_usd")
                if gdp is None:
                    norm.exclude_reason = "GDP missing"
                elif gdp <= 0:
                    norm.exclude_reason = f"GDP anomaly ({gdp})"
                else:
                    norm.exclude_reason = "Required indicators missing"
                results.append(norm)
                continue

            # 정규화
            norm.norm_gdp = self._norm_log(
                rec.get_value("gdp_usd"), "gdp_usd",
            )
            norm.norm_gdp_growth = self._norm_clip(
                rec.get_value("gdp_growth_pct"), "gdp_growth_pct",
            )

            # EconomicScore 산정
            norm.economic_score = self._compute_economic_score(norm)

            results.append(norm)

        scored = sum(1 for r in results if not r.excluded)
        excluded = sum(1 for r in results if r.excluded)
        logger.info(
            "DS-02 Scoring: %d scored, %d excluded (total %d)",
            scored, excluded, len(results),
        )

        return results
