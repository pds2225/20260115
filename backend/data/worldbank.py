"""
DS-02 World Bank 데이터 수집/로드 모듈.

실제 데이터 소스: World Bank API / CSV
  - GDP (current USD): NY.GDP.MKTP.CD
  - GDP growth (annual %): NY.GDP.MKTP.KD.ZG

참조: docs/DS02_WSB_SPEC.md, docs/CONTRACT_GAP_ANALYSIS.md
"""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WSB_FIELDS: list[str] = ["gdp_usd", "gdp_growth_pct"]
MAX_YEAR_GAP = 3

CSV_INDICATOR_MAP: dict[str, str] = {
    "WB_WDI_NY_GDP_MKTP_CD": "gdp_usd",
    "WB_WDI_NY_GDP_MKTP_KD_ZG": "gdp_growth_pct",
    "NY.GDP.MKTP.CD": "gdp_usd",
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class WorldBankRecord:
    """단일 국가의 World Bank 원본 데이터."""

    country_iso3: str
    country_name: str
    snapshot_date: str

    gdp_usd: tuple[float, int] | None = None
    gdp_growth_pct: tuple[float, int] | None = None

    def get_value(self, field_name: str) -> float | None:
        entry = getattr(self, field_name, None)
        if entry is None:
            return None
        return entry[0]

    def get_year(self, field_name: str) -> int | None:
        entry = getattr(self, field_name, None)
        if entry is None:
            return None
        return entry[1]

    @property
    def missing_fields(self) -> list[str]:
        return [f for f in WSB_FIELDS if self.get_value(f) is None]

    @property
    def is_valid_for_scoring(self) -> bool:
        gdp = self.get_value("gdp_usd")
        if gdp is None or gdp <= 0:
            return False
        return True

    def warnings(self) -> list[str]:
        w: list[str] = []
        gdp = self.get_value("gdp_usd")
        if gdp is not None and gdp <= 0:
            w.append(f"DS-02: GDP <= 0 for {self.country_iso3} (value={gdp})")
        for name in WSB_FIELDS:
            if self.get_value(name) is None:
                w.append(f"DS-02: {name} unavailable for {self.country_iso3}")
        return w


# ---------------------------------------------------------------------------
# Built-in data (주요 교역국)
# ---------------------------------------------------------------------------

BUILTIN_WORLDBANK_DATA: dict[str, dict] = {
    "USA": {"name": "United States", "gdp_usd": 25462e9, "gdp_growth_pct": 2.1},
    "CHN": {"name": "China", "gdp_usd": 17963e9, "gdp_growth_pct": 5.2},
    "JPN": {"name": "Japan", "gdp_usd": 4231e9, "gdp_growth_pct": 1.1},
    "DEU": {"name": "Germany", "gdp_usd": 4072e9, "gdp_growth_pct": -0.87},
    "GBR": {"name": "United Kingdom", "gdp_usd": 3070e9, "gdp_growth_pct": 0.1},
    "IND": {"name": "India", "gdp_usd": 3638e9, "gdp_growth_pct": 9.19},
    "FRA": {"name": "France", "gdp_usd": 2783e9, "gdp_growth_pct": 0.9},
    "CAN": {"name": "Canada", "gdp_usd": 2139e9, "gdp_growth_pct": 1.5},
    "KOR": {"name": "Korea, Rep.", "gdp_usd": 1845e9, "gdp_growth_pct": 1.58},
    "AUS": {"name": "Australia", "gdp_usd": 1675e9, "gdp_growth_pct": 2.0},
    "BRA": {"name": "Brazil", "gdp_usd": 1920e9, "gdp_growth_pct": 2.9},
    "RUS": {"name": "Russia", "gdp_usd": 2240e9, "gdp_growth_pct": 3.6},
    "MEX": {"name": "Mexico", "gdp_usd": 1320e9, "gdp_growth_pct": 3.2},
    "IDN": {"name": "Indonesia", "gdp_usd": 1319e9, "gdp_growth_pct": 5.0},
    "TUR": {"name": "Turkey", "gdp_usd": 1150e9, "gdp_growth_pct": 4.5},
    "SAU": {"name": "Saudi Arabia", "gdp_usd": 1061e9, "gdp_growth_pct": -0.9},
    "NLD": {"name": "Netherlands", "gdp_usd": 1009e9, "gdp_growth_pct": 0.1},
    "CHE": {"name": "Switzerland", "gdp_usd": 869e9, "gdp_growth_pct": 0.7},
    "POL": {"name": "Poland", "gdp_usd": 842e9, "gdp_growth_pct": 0.2},
    "TWN": {"name": "Taiwan", "gdp_usd": 790e9, "gdp_growth_pct": 1.3},
    "SGP": {"name": "Singapore", "gdp_usd": 497e9, "gdp_growth_pct": 1.1},
    "THA": {"name": "Thailand", "gdp_usd": 495e9, "gdp_growth_pct": 1.9},
    "VNM": {"name": "Vietnam", "gdp_usd": 430e9, "gdp_growth_pct": 5.1},
    "PHL": {"name": "Philippines", "gdp_usd": 404e9, "gdp_growth_pct": 5.6},
    "MYS": {"name": "Malaysia", "gdp_usd": 399e9, "gdp_growth_pct": 3.7},
    "HKG": {"name": "Hong Kong", "gdp_usd": 360e9, "gdp_growth_pct": 3.2},
    "ARE": {"name": "UAE", "gdp_usd": 509e9, "gdp_growth_pct": 3.4},
    "HUN": {"name": "Hungary", "gdp_usd": 212e9, "gdp_growth_pct": -0.9},
    "CZE": {"name": "Czech Republic", "gdp_usd": 330e9, "gdp_growth_pct": -0.4},
    "BEL": {"name": "Belgium", "gdp_usd": 624e9, "gdp_growth_pct": 1.4},
}


def get_builtin_records() -> list[WorldBankRecord]:
    """내장 World Bank 데이터로 레코드 목록 생성."""
    records = []
    snapshot = date.today().isoformat()
    for iso3, data in BUILTIN_WORLDBANK_DATA.items():
        rec = WorldBankRecord(
            country_iso3=iso3,
            country_name=data["name"],
            snapshot_date=snapshot,
            gdp_usd=(data["gdp_usd"], 2023),
            gdp_growth_pct=(data["gdp_growth_pct"], 2023),
        )
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# CSV Loader
# ---------------------------------------------------------------------------

def load_csv_records(
    gdp_csv: str | Path,
    gdp_growth_csv: str | Path,
    current_year: int | None = None,
) -> list[WorldBankRecord]:
    """
    World Bank CSV 2개를 로드하고 국가별 레코드를 생성한다.

    CSV 컬럼: REF_AREA, TIME_PERIOD, OBS_VALUE, INDICATOR, REF_AREA_LABEL
    """
    cur_year = current_year or date.today().year
    snapshot = date.today().isoformat()

    def parse_csv(csv_path: str | Path) -> dict[str, list[tuple[float, int, str]]]:
        path = Path(csv_path)
        if not path.exists():
            logger.error("CSV file not found: %s", path)
            return {}
        result: dict[str, list[tuple[float, int, str]]] = {}
        with open(path, "r", encoding="utf-8-sig") as f:
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
                if cur_year - year > MAX_YEAR_GAP:
                    continue
                result.setdefault(iso3, []).append((value, year, name))
        return result

    gdp_data = parse_csv(gdp_csv)
    growth_data = parse_csv(gdp_growth_csv)

    all_countries = set(gdp_data.keys()) | set(growth_data.keys())
    records = []

    for iso3 in sorted(all_countries):
        gdp_entries = gdp_data.get(iso3, [])
        growth_entries = growth_data.get(iso3, [])

        gdp_val = None
        growth_val = None
        country_name = ""

        if gdp_entries:
            gdp_entries.sort(key=lambda x: x[1], reverse=True)
            val, yr, name = gdp_entries[0]
            country_name = name
            if val != 0:
                gdp_val = (val, yr)

        if growth_entries:
            growth_entries.sort(key=lambda x: x[1], reverse=True)
            val, yr, name = growth_entries[0]
            if not country_name:
                country_name = name
            growth_val = (val, yr)

        rec = WorldBankRecord(
            country_iso3=iso3,
            country_name=country_name,
            snapshot_date=snapshot,
            gdp_usd=gdp_val,
            gdp_growth_pct=growth_val,
        )
        records.append(rec)

    logger.info("World Bank: %d country records loaded", len(records))
    return records


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

def save_snapshot(records: list[WorldBankRecord], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for rec in records:
        entry = {
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
            f, ensure_ascii=False, indent=2,
        )


def load_snapshot(path: str | Path) -> list[WorldBankRecord]:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    records = []
    for entry in raw.get("records", []):
        rec = WorldBankRecord(
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
