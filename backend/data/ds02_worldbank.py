"""
DS-02 World Bank 데이터 수집·로드 모듈.

실제 데이터 소스: World Bank CSV 파일 2종
  - WB_WDI_NY_GDP_MKTP_CD.csv     (GDP, current USD)
  - WB_WDI_NY_GDP_MKTP_KD_ZG.csv  (GDP growth, annual %)

CSV 컬럼 구조:
  REF_AREA        → country_iso3 (이미 ISO3)
  TIME_PERIOD     → year
  OBS_VALUE       → value
  INDICATOR       → indicator code (WB_WDI_NY_GDP_MKTP_CD 등)
  REF_AREA_LABEL  → country name (참조용)

참조: docs/DS02_WSB_SPEC.md
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (v1 확정: 2개 지표만)
# ---------------------------------------------------------------------------

# CSV INDICATOR 컬럼값 → 내부 필드명
CSV_INDICATOR_MAP: dict[str, str] = {
    "WB_WDI_NY_GDP_MKTP_CD": "gdp_usd",
    "WB_WDI_NY_GDP_MKTP_KD_ZG": "gdp_growth_pct",
}

# 내부 필드명 → World Bank 표준 코드 (문서 참조용)
STANDARD_INDICATOR_CODES: dict[str, str] = {
    "gdp_usd": "NY.GDP.MKTP.CD",
    "gdp_growth_pct": "NY.GDP.MKTP.KD.ZG",
}

# v1 확정 필드 목록
WSB_FIELDS: list[str] = ["gdp_usd", "gdp_growth_pct"]

# 연도 최신성 제약: current_year - target_year ≤ MAX_YEAR_GAP
MAX_YEAR_GAP = 3


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class DS02Record:
    """단일 국가의 DS-02 원본 데이터."""

    country_iso3: str
    country_name: str
    snapshot_date: str  # YYYY-MM-DD

    # 지표별 (value, year) 튜플. None이면 결측.
    gdp_usd: tuple[float, int] | None = None
    gdp_growth_pct: tuple[float, int] | None = None

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
        return [f for f in WSB_FIELDS if self.get_value(f) is None]

    @property
    def is_valid_for_scoring(self) -> bool:
        """
        필수 지표 존재 여부.

        v1 확정: GDP가 필수.
        GDP=0 또는 GDP=null → 결측으로 간주 (분석 결과 규칙 반영).
        """
        gdp = self.get_value("gdp_usd")
        if gdp is None or gdp <= 0:
            return False
        return True

    def warnings(self) -> list[str]:
        """이상값/결측 경고 목록."""
        w: list[str] = []
        gdp = self.get_value("gdp_usd")
        if gdp is not None and gdp <= 0:
            w.append(f"DS-02: GDP ≤ 0 for {self.country_iso3} (value={gdp})")
        for name in WSB_FIELDS:
            if self.get_value(name) is None:
                w.append(f"DS-02: {name} unavailable for {self.country_iso3}")
        return w


# ---------------------------------------------------------------------------
# CSV Loader
# ---------------------------------------------------------------------------

def _parse_csv_rows(
    csv_path: str | Path,
    current_year: int,
) -> dict[str, list[tuple[float, int, str]]]:
    """
    CSV 파일 파싱.

    Returns:
        { country_iso3: [(value, year, country_name), ...] }
    """
    path = Path(csv_path)
    if not path.exists():
        logger.error("DS-02: CSV file not found: %s", path)
        return {}

    result: dict[str, list[tuple[float, int, str]]] = {}

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iso3 = row.get("REF_AREA", "").strip()
            year_str = row.get("TIME_PERIOD", "").strip()
            val_str = row.get("OBS_VALUE", "").strip()
            name = row.get("REF_AREA_LABEL", "").strip()

            if not iso3 or not year_str or not val_str:
                continue

            try:
                year = int(year_str)
                value = float(val_str)
            except (ValueError, TypeError):
                continue

            # 연도 최신성 제약
            if current_year - year > MAX_YEAR_GAP:
                continue

            result.setdefault(iso3, []).append((value, year, name))

    return result


def _select_latest(
    entries: list[tuple[float, int, str]],
) -> tuple[float, int, str] | None:
    """최신 연도 선택: max(year WHERE value IS NOT NULL)."""
    if not entries:
        return None
    entries.sort(key=lambda x: x[1], reverse=True)
    return entries[0]


class DS02Loader:
    """
    DS-02 CSV 데이터 로더.

    사용법:
        loader = DS02Loader(
            gdp_csv="data/WB_WDI_NY_GDP_MKTP_CD.csv",
            gdp_growth_csv="data/WB_WDI_NY_GDP_MKTP_KD_ZG.csv",
        )
        records = loader.load()
    """

    def __init__(
        self,
        gdp_csv: str | Path,
        gdp_growth_csv: str | Path,
        current_year: int | None = None,
        target_countries_iso3: list[str] | None = None,
    ):
        self.gdp_csv = Path(gdp_csv)
        self.gdp_growth_csv = Path(gdp_growth_csv)
        self.current_year = current_year or date.today().year
        self.target_countries = (
            set(c.upper() for c in target_countries_iso3)
            if target_countries_iso3
            else None
        )

    def load(self) -> list[DS02Record]:
        """
        CSV 2개를 로드하고 국가별 DS02Record를 생성한다.

        연도 선택 규칙:
          - max(year WHERE value IS NOT NULL)
          - current_year - year ≤ 3
          - GDP=0 → 결측 간주
        """
        snapshot_date = date.today().isoformat()

        # GDP CSV 파싱
        gdp_data = _parse_csv_rows(self.gdp_csv, self.current_year)
        logger.info(
            "DS-02: GDP CSV loaded — %d countries from %s",
            len(gdp_data), self.gdp_csv.name,
        )

        # GDP growth CSV 파싱
        growth_data = _parse_csv_rows(self.gdp_growth_csv, self.current_year)
        logger.info(
            "DS-02: GDP growth CSV loaded — %d countries from %s",
            len(growth_data), self.gdp_growth_csv.name,
        )

        # 전체 국가 합집합
        all_countries = set(gdp_data.keys()) | set(growth_data.keys())

        if self.target_countries:
            all_countries &= self.target_countries

        records: list[DS02Record] = []

        for iso3 in sorted(all_countries):
            # GDP
            gdp_entry = _select_latest(gdp_data.get(iso3, []))
            gdp_val: tuple[float, int] | None = None
            country_name = ""
            if gdp_entry is not None:
                val, yr, name = gdp_entry
                country_name = name
                # GDP=0 → 결측 간주
                if val != 0:
                    gdp_val = (val, yr)

            # GDP growth
            growth_entry = _select_latest(growth_data.get(iso3, []))
            growth_val: tuple[float, int] | None = None
            if growth_entry is not None:
                val, yr, name = growth_entry
                if not country_name:
                    country_name = name
                # GDP growth=0 → 유효한 0값 (결측 아님)
                growth_val = (val, yr)

            rec = DS02Record(
                country_iso3=iso3,
                country_name=country_name,
                snapshot_date=snapshot_date,
                gdp_usd=gdp_val,
                gdp_growth_pct=growth_val,
            )
            records.append(rec)

        logger.info("DS-02: Total %d country records created", len(records))
        return records


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
            "country_name": rec.country_name,
            "snapshot_date": rec.snapshot_date,
            "indicators": {},
        }
        for field_name in WSB_FIELDS:
            val = rec.get_value(field_name)
            yr = rec.get_year(field_name)
            entry["indicators"][field_name] = {"value": val, "year": yr}
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
            country_name=entry.get("country_name", ""),
            snapshot_date=entry.get("snapshot_date", ""),
        )
        for field_name in WSB_FIELDS:
            ind = entry.get("indicators", {}).get(field_name, {})
            val = ind.get("value")
            yr = ind.get("year")
            if val is not None and yr is not None:
                setattr(rec, field_name, (float(val), int(yr)))
        records.append(rec)

    return records
