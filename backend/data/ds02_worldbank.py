"""
DS-02 World Bank Indicators 수집 모듈.

WSB 기준 7개 지표를 World Bank API에서 수집하고,
스냅샷 형태로 저장한다.

참조: docs/DS02_WSB_SPEC.md
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

from backend.data.iso_mapping import ISO3_TO_ISO2, iso3_to_iso2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (WSB 고정)
# ---------------------------------------------------------------------------

WORLDBANK_BASE_URL = "https://api.worldbank.org/v2"

# WSB Field ID → World Bank Indicator Code (7개 고정)
WSB_INDICATORS: dict[str, str] = {
    "gdp_usd": "NY.GDP.MKTP.CD",
    "gdp_per_capita_usd": "NY.GDP.PCAP.CD",
    "gdp_growth_pct": "NY.GDP.MKTP.KD.ZG",
    "import_value_usd": "NE.IMP.GNFS.CD",
    "import_growth_pct": "NE.IMP.GNFS.KD.ZG",
    "inflation_pct": "FP.CPI.TOTL.ZG",
    "population": "SP.POP.TOTL",
}

# 연도 최신성 제약: current_year - target_year ≤ MAX_YEAR_GAP
MAX_YEAR_GAP = 3

# API 호출 설정
REQUEST_TIMEOUT = 10  # seconds
RATE_LIMIT_DELAY = 0.5  # seconds between requests
MAX_RETRIES = 3
PER_PAGE = 1000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DS02Record:
    """단일 국가의 DS-02 원본 데이터."""

    country_iso3: str
    country_iso2: str
    snapshot_date: str  # YYYY-MM-DD
    # 지표별 (value, year) 튜플. None이면 결측.
    gdp_usd: tuple[float, int] | None = None
    gdp_per_capita_usd: tuple[float, int] | None = None
    gdp_growth_pct: tuple[float, int] | None = None
    import_value_usd: tuple[float, int] | None = None
    import_growth_pct: tuple[float, int] | None = None
    inflation_pct: tuple[float, int] | None = None
    population: tuple[float, int] | None = None

    def get_value(self, field_name: str) -> float | None:
        """지표 값만 반환 (연도 제외)."""
        entry = getattr(self, field_name, None)
        if entry is None:
            return None
        return entry[0]

    def get_year(self, field_name: str) -> int | None:
        """지표 연도만 반환."""
        entry = getattr(self, field_name, None)
        if entry is None:
            return None
        return entry[1]

    @property
    def missing_fields(self) -> list[str]:
        """결측 필드 목록."""
        fields = []
        for name in WSB_INDICATORS:
            if self.get_value(name) is None:
                fields.append(name)
        return fields

    @property
    def is_valid_for_scoring(self) -> bool:
        """필수 지표(GDP, Import value) 존재 여부."""
        gdp = self.get_value("gdp_usd")
        imp = self.get_value("import_value_usd")
        if gdp is None or imp is None:
            return False
        if gdp <= 0 or imp < 0:
            return False
        return True

    def warnings(self) -> list[str]:
        """이상값/결측 경고 목록."""
        w = []
        gdp = self.get_value("gdp_usd")
        imp = self.get_value("import_value_usd")
        if gdp is not None and gdp <= 0:
            w.append(f"DS-02: GDP ≤ 0 for {self.country_iso3} (value={gdp})")
        if imp is not None and imp < 0:
            w.append(f"DS-02: Import value < 0 for {self.country_iso3} (value={imp})")
        for name in WSB_INDICATORS:
            if self.get_value(name) is None:
                w.append(
                    f"DS-02: {name} unavailable for {self.country_iso3}"
                )
        return w


# ---------------------------------------------------------------------------
# World Bank API Client
# ---------------------------------------------------------------------------

class WorldBankClient:
    """World Bank API v2 호출 클라이언트."""

    def __init__(
        self,
        base_url: str = WORLDBANK_BASE_URL,
        timeout: int = REQUEST_TIMEOUT,
        rate_limit_delay: float = RATE_LIMIT_DELAY,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()

    def fetch_indicator(
        self,
        country_iso2: str,
        indicator_code: str,
        year_start: int,
        year_end: int,
    ) -> list[dict[str, Any]]:
        """
        단일 국가·단일 지표 조회.

        Returns:
            [{date: "2023", value: 430000000000.0}, ...] 형태의 리스트.
            값이 null인 항목도 포함될 수 있다.
        """
        url = (
            f"{self.base_url}/country/{country_iso2}/indicator/{indicator_code}"
            f"?date={year_start}:{year_end}&format=json&per_page={PER_PAGE}"
        )

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()

                # World Bank API는 [메타, 데이터] 형태로 반환
                if isinstance(data, list) and len(data) >= 2:
                    return data[1] or []
                return []

            except requests.RequestException as e:
                logger.warning(
                    "DS-02 API error (attempt %d/%d) %s/%s: %s",
                    attempt + 1, MAX_RETRIES, country_iso2, indicator_code, e,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        logger.error(
            "DS-02 API failed after %d retries: %s/%s",
            MAX_RETRIES, country_iso2, indicator_code,
        )
        return []

    def fetch_indicator_bulk(
        self,
        indicator_code: str,
        year_start: int,
        year_end: int,
    ) -> list[dict[str, Any]]:
        """
        전체 국가 일괄 조회 (all countries).

        World Bank API는 country="all"로 전체 조회 가능.
        """
        url = (
            f"{self.base_url}/country/all/indicator/{indicator_code}"
            f"?date={year_start}:{year_end}&format=json&per_page={PER_PAGE}"
        )

        all_records: list[dict] = []
        page = 1

        while True:
            paged_url = f"{url}&page={page}"
            for attempt in range(MAX_RETRIES):
                try:
                    resp = self.session.get(paged_url, timeout=self.timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except requests.RequestException as e:
                    logger.warning(
                        "DS-02 bulk API error (page=%d, attempt %d/%d) %s: %s",
                        page, attempt + 1, MAX_RETRIES, indicator_code, e,
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                    else:
                        return all_records

            if not isinstance(data, list) or len(data) < 2 or not data[1]:
                break

            all_records.extend(data[1])

            meta = data[0]
            total_pages = meta.get("pages", 1)
            if page >= total_pages:
                break
            page += 1
            time.sleep(self.rate_limit_delay)

        return all_records


# ---------------------------------------------------------------------------
# DS-02 Collector
# ---------------------------------------------------------------------------

class DS02Collector:
    """
    DS-02 데이터 수집기.

    World Bank API에서 WSB 7개 지표를 수집하고,
    연도 선택 규칙(최신 유효 연도, 3년 제약)을 적용하여
    DS02Record 리스트를 반환한다.
    """

    def __init__(
        self,
        client: WorldBankClient | None = None,
        current_year: int | None = None,
        target_countries_iso3: list[str] | None = None,
    ):
        self.client = client or WorldBankClient()
        self.current_year = current_year or date.today().year
        self.target_countries_iso3 = target_countries_iso3

    def _select_latest_value(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[float, int] | None:
        """
        연도 선택 규칙 적용:
        - max(year WHERE value IS NOT NULL)
        - current_year - target_year ≤ 3
        """
        candidates: list[tuple[float, int]] = []
        for rec in records:
            val = rec.get("value")
            year_str = rec.get("date", "")
            if val is None:
                continue
            try:
                year = int(year_str)
            except (ValueError, TypeError):
                continue
            if self.current_year - year > MAX_YEAR_GAP:
                continue
            candidates.append((float(val), year))

        if not candidates:
            return None

        # 최신 연도 선택
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    def collect_bulk(self) -> list[DS02Record]:
        """
        전체 국가 일괄 수집 (권장).

        지표별로 bulk API 호출 후 국가별로 집계한다.
        """
        snapshot_date = date.today().isoformat()
        year_start = self.current_year - MAX_YEAR_GAP
        year_end = self.current_year

        # 국가별 지표 데이터를 임시 저장
        # { iso2: { field_name: [(value, year), ...] } }
        country_data: dict[str, dict[str, list[dict]]] = {}

        for field_name, indicator_code in WSB_INDICATORS.items():
            logger.info("DS-02: Fetching %s (%s)...", field_name, indicator_code)
            records = self.client.fetch_indicator_bulk(
                indicator_code, year_start, year_end,
            )
            for rec in records:
                country_info = rec.get("country", {})
                iso2 = country_info.get("id", "")
                if not iso2 or len(iso2) != 2:
                    continue
                country_data.setdefault(iso2, {}).setdefault(field_name, []).append(rec)

            time.sleep(self.client.rate_limit_delay)

        # DS02Record 생성
        results: list[DS02Record] = []
        target_iso2_set = None
        if self.target_countries_iso3:
            target_iso2_set = {
                iso3_to_iso2(c) for c in self.target_countries_iso3
                if iso3_to_iso2(c) is not None
            }

        for iso2, indicators in country_data.items():
            if target_iso2_set and iso2 not in target_iso2_set:
                continue

            from backend.data.iso_mapping import iso2_to_iso3
            iso3 = iso2_to_iso3(iso2)
            if iso3 is None:
                continue

            record = DS02Record(
                country_iso3=iso3,
                country_iso2=iso2,
                snapshot_date=snapshot_date,
            )

            for field_name in WSB_INDICATORS:
                field_records = indicators.get(field_name, [])
                latest = self._select_latest_value(field_records)
                setattr(record, field_name, latest)

            results.append(record)

        logger.info("DS-02: Collected %d country records", len(results))
        return results

    def collect_single(self, country_iso3: str) -> DS02Record | None:
        """단일 국가 수집."""
        iso2 = iso3_to_iso2(country_iso3)
        if iso2 is None:
            logger.warning("DS-02: Unknown ISO3 code: %s", country_iso3)
            return None

        snapshot_date = date.today().isoformat()
        year_start = self.current_year - MAX_YEAR_GAP
        year_end = self.current_year

        record = DS02Record(
            country_iso3=country_iso3,
            country_iso2=iso2,
            snapshot_date=snapshot_date,
        )

        for field_name, indicator_code in WSB_INDICATORS.items():
            raw = self.client.fetch_indicator(
                iso2, indicator_code, year_start, year_end,
            )
            latest = self._select_latest_value(raw)
            setattr(record, field_name, latest)
            time.sleep(self.client.rate_limit_delay)

        return record


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

def save_snapshot(records: list[DS02Record], path: str | Path) -> None:
    """DS-02 스냅샷을 JSON 파일로 저장."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for rec in records:
        entry: dict[str, Any] = {
            "country_iso3": rec.country_iso3,
            "country_iso2": rec.country_iso2,
            "snapshot_date": rec.snapshot_date,
            "indicators": {},
        }
        for field_name in WSB_INDICATORS:
            val = rec.get_value(field_name)
            yr = rec.get_year(field_name)
            entry["indicators"][field_name] = {
                "value": val,
                "year": yr,
            }
        data.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"snapshot_date": date.today().isoformat(), "records": data},
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info("DS-02: Snapshot saved to %s (%d records)", path, len(data))


def load_snapshot(path: str | Path) -> list[DS02Record]:
    """DS-02 스냅샷 JSON 파일에서 로드."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    records: list[DS02Record] = []
    for entry in raw.get("records", []):
        rec = DS02Record(
            country_iso3=entry["country_iso3"],
            country_iso2=entry["country_iso2"],
            snapshot_date=entry.get("snapshot_date", ""),
        )
        for field_name in WSB_INDICATORS:
            ind = entry.get("indicators", {}).get(field_name, {})
            val = ind.get("value")
            yr = ind.get("year")
            if val is not None and yr is not None:
                setattr(rec, field_name, (float(val), int(yr)))
            else:
                setattr(rec, field_name, None)
        records.append(rec)

    return records
