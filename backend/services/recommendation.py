"""
P1: 수출 유망 국가 추천 엔진.

4가지 지표 합산 점수 계산:
  - 무역 규모(40%) + 경제 성장률(25%) + 규제/리스크(20%) + 트렌드(15%)

참조: notebookLM 분석결과, docs/README_PATCH.md
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from backend.data.sanctions import (
    ComplianceResult,
    SanctionStatus,
    check_compliance,
    filter_blocked_countries,
    RESTRICTED_PENALTY,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 가중치 (4가지 지표, 합계 = 1.00)
# ---------------------------------------------------------------------------

WEIGHTS = {
    "trade_volume": 0.40,       # 무역 규모
    "economic_growth": 0.25,    # 경제 성장률
    "regulation_risk": 0.20,    # 규제/리스크
    "trend": 0.15,              # 트렌드
}


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


@dataclass
class DataQuality:
    """데이터 품질/신뢰도 정보."""

    available_fields: int = 0
    total_fields: int = 4  # 4가지 지표
    missing_fields: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        if self.total_fields == 0:
            return 0.0
        return self.available_fields / self.total_fields

    @property
    def confidence(self) -> float:
        return round(self.coverage, 2)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        c = self.confidence
        if c >= 0.8:
            return ConfidenceLevel.HIGH
        elif c >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif c >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def to_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "missing_fields": self.missing_fields,
            "data_coverage": self.coverage,
        }


@dataclass
class CountryScore:
    """국가별 추천 점수."""

    country_iso3: str
    country_name: str

    # 개별 정규화 점수 (0~1)
    trade_volume_score: float = 0.0
    economic_growth_score: float = 0.0
    regulation_risk_score: float = 0.0
    trend_score: float = 0.0

    # 최종 합산 점수 (0~100)
    total_score: float = 0.0

    # 제재/규제 정보
    compliance: Optional[ComplianceResult] = None

    # 데이터 품질
    data_quality: DataQuality = field(default_factory=DataQuality)

    # 제외 여부
    excluded: bool = False
    exclude_reason: str = ""

    @property
    def score_components(self) -> dict[str, float]:
        return {
            "trade_volume": round(self.trade_volume_score * WEIGHTS["trade_volume"] * 100, 2),
            "economic_growth": round(self.economic_growth_score * WEIGHTS["economic_growth"] * 100, 2),
            "regulation_risk": round(self.regulation_risk_score * WEIGHTS["regulation_risk"] * 100, 2),
            "trend": round(self.trend_score * WEIGHTS["trend"] * 100, 2),
        }

    def to_dict(self) -> dict:
        result = {
            "country_iso3": self.country_iso3,
            "country_name": self.country_name,
            "total_score": round(self.total_score, 2),
            "score_components": self.score_components,
            "data_quality": self.data_quality.to_dict(),
        }
        if self.compliance:
            result["compliance"] = self.compliance.to_dict()
        if self.excluded:
            result["excluded"] = True
            result["exclude_reason"] = self.exclude_reason
        return result


@dataclass
class CountryData:
    """추천 엔진 입력 데이터."""

    country_iso3: str
    country_name: str = ""
    trade_value_usd: float = 0.0
    gdp_usd: float = 0.0
    gdp_growth_pct: float = 0.0
    tariff_rate: float = 0.0
    market_trend_score: float = 0.0
    regulation_score: float = 0.0
    distance_km: float = 0.0


class RecommendationEngine:
    """
    수출 유망 국가 추천 엔진.

    4가지 지표를 정규화한 뒤 가중합으로 점수를 산출한다.
    제재국은 자동 차단, 제한국은 경고 + 감점 처리.

    사용법:
        engine = RecommendationEngine(countries_data)
        results = engine.score_all(top_n=5)
    """

    def __init__(self, countries: list[CountryData]):
        self.countries = countries

    def _normalize_log_minmax(
        self, values: list[float | None]
    ) -> list[float | None]:
        """로그 스케일 min-max 정규화."""
        log_vals = []
        for v in values:
            if v is not None and v > 0:
                log_vals.append(math.log(v))
            else:
                log_vals.append(None)

        valid = [v for v in log_vals if v is not None]
        if not valid:
            return [0.0 if v is None else 0.5 for v in log_vals]

        min_v, max_v = min(valid), max(valid)
        denom = max_v - min_v if max_v != min_v else 1.0

        result = []
        for v in log_vals:
            if v is None:
                result.append(None)
            else:
                result.append(max(0.0, min(1.0, (v - min_v) / denom)))
        return result

    def _normalize_clip(
        self, values: list[float | None], lower: float, upper: float
    ) -> list[float | None]:
        """클리핑 + 0-1 정규화."""
        result = []
        denom = upper - lower if upper != lower else 1.0
        for v in values:
            if v is None:
                result.append(None)
            else:
                clipped = max(lower, min(upper, v))
                result.append((clipped - lower) / denom)
        return result

    def _normalize_inverse(
        self, values: list[float | None], lower: float, upper: float
    ) -> list[float | None]:
        """역정규화 (높을수록 나쁨 -> 낮을수록 좋음). 규제/리스크용."""
        result = []
        denom = upper - lower if upper != lower else 1.0
        for v in values:
            if v is None:
                result.append(None)
            else:
                clipped = max(lower, min(upper, v))
                result.append(1.0 - (clipped - lower) / denom)
        return result

    def score_all(self, top_n: int = 10) -> list[CountryScore]:
        """
        전체 국가에 대해 추천 점수를 산출한다.

        Returns:
            점수 내림차순으로 정렬된 CountryScore 리스트
        """
        n = len(self.countries)
        if n == 0:
            return []

        # 1. 제재국 필터링
        compliance_map: dict[str, ComplianceResult] = {}
        for c in self.countries:
            compliance_map[c.country_iso3] = check_compliance(c.country_iso3)

        # 2. 정규화
        trade_vals = [c.trade_value_usd if c.trade_value_usd > 0 else None for c in self.countries]
        growth_vals = [c.gdp_growth_pct for c in self.countries]
        # 규제: tariff_rate -> 높으면 나쁨 (역정규화), regulation_score -> 높으면 좋음
        tariff_vals = [c.tariff_rate for c in self.countries]
        trend_vals = [c.market_trend_score for c in self.countries]

        norm_trade = self._normalize_log_minmax(trade_vals)
        norm_growth = self._normalize_clip(growth_vals, -5.0, 10.0)
        norm_regulation = self._normalize_inverse(tariff_vals, 0.0, 25.0)
        norm_trend = self._normalize_clip(trend_vals, 0.0, 1.0)

        # 3. 점수 계산
        results: list[CountryScore] = []

        for i, c in enumerate(self.countries):
            comp = compliance_map[c.country_iso3]

            score = CountryScore(
                country_iso3=c.country_iso3,
                country_name=c.country_name,
                compliance=comp,
            )

            # blocked -> 제외
            if comp.is_blocked:
                score.excluded = True
                score.exclude_reason = f"제재 대상국: {comp.warning}"
                score.total_score = 0.0
                results.append(score)
                continue

            # 데이터 품질 계산
            missing = []
            available = 0

            if norm_trade[i] is not None:
                score.trade_volume_score = norm_trade[i]
                available += 1
            else:
                missing.append("trade_volume")

            if norm_growth[i] is not None:
                score.economic_growth_score = norm_growth[i]
                available += 1
            else:
                missing.append("economic_growth")

            if norm_regulation[i] is not None:
                score.regulation_risk_score = norm_regulation[i]
                available += 1
            else:
                missing.append("regulation_risk")

            if norm_trend[i] is not None:
                score.trend_score = norm_trend[i]
                available += 1
            else:
                missing.append("trend")

            score.data_quality = DataQuality(
                available_fields=available,
                total_fields=4,
                missing_fields=missing,
            )

            # 가중합
            total = (
                score.trade_volume_score * WEIGHTS["trade_volume"]
                + score.economic_growth_score * WEIGHTS["economic_growth"]
                + score.regulation_risk_score * WEIGHTS["regulation_risk"]
                + score.trend_score * WEIGHTS["trend"]
            ) * 100

            # 제한국 감점
            if comp.is_restricted:
                total += comp.penalty  # -10

            score.total_score = max(0.0, min(100.0, total))
            results.append(score)

        # 정렬 (excluded 제외 후 점수 내림차순)
        active = [s for s in results if not s.excluded]
        excluded = [s for s in results if s.excluded]

        active.sort(key=lambda s: s.total_score, reverse=True)

        return active[:top_n] + excluded
