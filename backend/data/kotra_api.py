"""
KOTRA API 연동 모듈.

데이터 소스 우선순위:
  1. KOTRA 수출유망추천정보 API (실시간)
  2. 캐시된 데이터 (API 실패 시 fallback)
  3. 기본값 (캐시도 없을 때)

참조: docs/README_PATCH.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 캐시 설정
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 3600  # 1시간
CACHE_DIR = Path("cache/kotra")


@dataclass
class CacheEntry:
    """캐시 항목."""

    data: Any
    cached_at: datetime
    ttl_seconds: int = CACHE_TTL_SECONDS

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.cached_at + timedelta(seconds=self.ttl_seconds)

    @property
    def ttl_remaining_seconds(self) -> int:
        remaining = (
            self.cached_at + timedelta(seconds=self.ttl_seconds) - datetime.now()
        )
        return max(0, int(remaining.total_seconds()))


class KOTRACache:
    """KOTRA 데이터 인메모리 캐시 (파일 백업 포함)."""

    def __init__(self, cache_dir: Path | str = CACHE_DIR):
        self._memory: dict[str, CacheEntry] = {}
        self._cache_dir = Path(cache_dir)

    def _make_key(self, hs_code: str, goal: str) -> str:
        raw = f"{hs_code}:{goal}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, hs_code: str, goal: str) -> Optional[CacheEntry]:
        """캐시에서 데이터 조회. 메모리 → 파일 순서."""
        key = self._make_key(hs_code, goal)

        # 메모리 캐시
        if key in self._memory:
            entry = self._memory[key]
            if not entry.is_expired:
                logger.info("KOTRA cache HIT (memory): hs=%s goal=%s", hs_code, goal)
                return entry
            else:
                del self._memory[key]

        # 파일 캐시
        file_path = self._cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                entry = CacheEntry(
                    data=raw["data"],
                    cached_at=datetime.fromisoformat(raw["cached_at"]),
                    ttl_seconds=raw.get("ttl_seconds", CACHE_TTL_SECONDS),
                )
                if not entry.is_expired:
                    self._memory[key] = entry
                    logger.info(
                        "KOTRA cache HIT (file): hs=%s goal=%s", hs_code, goal
                    )
                    return entry
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        logger.info("KOTRA cache MISS: hs=%s goal=%s", hs_code, goal)
        return None

    def put(self, hs_code: str, goal: str, data: Any) -> None:
        """캐시에 데이터 저장 (메모리 + 파일)."""
        key = self._make_key(hs_code, goal)
        entry = CacheEntry(data=data, cached_at=datetime.now())
        self._memory[key] = entry

        # 파일 캐시 저장
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = self._cache_dir / f"{key}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "data": data,
                        "cached_at": entry.cached_at.isoformat(),
                        "ttl_seconds": entry.ttl_seconds,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError as e:
            logger.warning("KOTRA cache file write failed: %s", e)


@dataclass
class KOTRACountryInfo:
    """KOTRA API에서 반환하는 국가 정보."""

    country_code: str  # ISO3
    country_name: str
    trade_value_usd: float = 0.0
    gdp_usd: float = 0.0
    gdp_growth_pct: float = 0.0
    tariff_rate: float = 0.0
    market_trend_score: float = 0.0
    regulation_score: float = 0.0
    distance_km: float = 0.0

    def to_dict(self) -> dict:
        return {
            "country_code": self.country_code,
            "country_name": self.country_name,
            "trade_value_usd": self.trade_value_usd,
            "gdp_usd": self.gdp_usd,
            "gdp_growth_pct": self.gdp_growth_pct,
            "tariff_rate": self.tariff_rate,
            "market_trend_score": self.market_trend_score,
            "regulation_score": self.regulation_score,
            "distance_km": self.distance_km,
        }


# ---------------------------------------------------------------------------
# 기본 국가 데이터 (API + 캐시 모두 실패 시 fallback)
# ---------------------------------------------------------------------------

DEFAULT_COUNTRIES: list[KOTRACountryInfo] = [
    KOTRACountryInfo("USA", "United States", 5.2e9, 25462e9, 2.1, 8.5, 0.7, 0.8, 11000),
    KOTRACountryInfo("CHN", "China", 16.2e9, 17963e9, 5.2, 12.5, 0.8, 0.5, 950),
    KOTRACountryInfo("JPN", "Japan", 3.1e9, 4231e9, 1.1, 10.2, 0.6, 0.9, 1200),
    KOTRACountryInfo("VNM", "Vietnam", 2.8e9, 430e9, 5.1, 5.2, 0.75, 0.6, 2400),
    KOTRACountryInfo("DEU", "Germany", 1.9e9, 4072e9, -0.87, 6.5, 0.65, 0.85, 8500),
]


class KOTRAClient:
    """
    KOTRA API 클라이언트.

    데이터 조회 우선순위:
      1. 실시간 API 호출
      2. 캐시된 데이터 (API 실패 시)
      3. 기본값 (캐시도 없을 때)
    """

    # KOTRA API 엔드포인트 (실제 환경에서 설정)
    API_BASE_URL = "https://api.kotra.or.kr/v1"
    API_KEY: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, cache: Optional[KOTRACache] = None):
        self.api_key = api_key or self.API_KEY
        self.cache = cache or KOTRACache()
        self._last_data_source: str = ""

    @property
    def last_data_source(self) -> str:
        """마지막 데이터 조회에 사용된 소스."""
        return self._last_data_source

    def fetch_promising_countries(
        self,
        hs_code: str,
        goal: str = "new_market",
        top_n: int = 10,
    ) -> list[KOTRACountryInfo]:
        """
        수출 유망 국가 정보를 조회한다.

        우선순위: API → 캐시 → 기본값
        """
        # 1. API 호출 시도
        api_result = self._call_api(hs_code, goal, top_n)
        if api_result is not None:
            self._last_data_source = "KOTRA 수출유망추천정보 API"
            self.cache.put(hs_code, goal, [c.to_dict() for c in api_result])
            return api_result

        # 2. 캐시 fallback
        cached = self.cache.get(hs_code, goal)
        if cached is not None:
            self._last_data_source = (
                f"캐시 데이터 ({cached.cached_at.strftime('%Y-%m-%d %H:%M')})"
            )
            return [
                KOTRACountryInfo(**entry)
                for entry in cached.data[:top_n]
            ]

        # 3. 기본값 fallback
        logger.warning(
            "KOTRA API + cache failed for hs=%s. Using defaults.", hs_code
        )
        self._last_data_source = "기본 데이터 (fallback)"
        return DEFAULT_COUNTRIES[:top_n]

    def _call_api(
        self,
        hs_code: str,
        goal: str,
        top_n: int,
    ) -> Optional[list[KOTRACountryInfo]]:
        """
        KOTRA API 실제 호출.

        실제 API 키가 설정되지 않은 경우 None 반환 (캐시/기본값으로 fallback).
        """
        if not self.api_key:
            logger.info("KOTRA API key not configured. Skipping API call.")
            return None

        try:
            import requests

            url = f"{self.API_BASE_URL}/export/promising-countries"
            params = {
                "hs_code": hs_code,
                "goal": goal,
                "top_n": top_n,
                "apiKey": self.api_key,
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            results = []
            for item in data.get("countries", []):
                results.append(
                    KOTRACountryInfo(
                        country_code=item.get("country_code", ""),
                        country_name=item.get("country_name", ""),
                        trade_value_usd=float(item.get("trade_value_usd", 0)),
                        gdp_usd=float(item.get("gdp_usd", 0)),
                        gdp_growth_pct=float(item.get("gdp_growth_pct", 0)),
                        tariff_rate=float(item.get("tariff_rate", 0)),
                        market_trend_score=float(item.get("market_trend_score", 0)),
                        regulation_score=float(item.get("regulation_score", 0)),
                        distance_km=float(item.get("distance_km", 0)),
                    )
                )
            return results if results else None

        except Exception as e:
            logger.warning("KOTRA API call failed: %s", e)
            return None
