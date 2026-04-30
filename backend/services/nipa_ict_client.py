"""
NIPA 글로벌ICT포털 해외바이어정보 클라이언트
EndPoint: https://apis.data.go.kr/B552551/overseasBuyerList/getOverseasBuyerList
총 1,853건 | 국가: UAE/두바이(123건), 미국(40건), 싱가포르(60건), 베트남(47건) 등
활용: Layer 4 담당자 확보 보조 소스, 회사명/전화번호/국가/등록일 제공
"""
from __future__ import annotations

import logging
import os
import math
import time
from pathlib import Path
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

NIPA_BASE_URL = "https://apis.data.go.kr/B552551/overseasBuyerList/getOverseasBuyerList"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
NIPA_CSV = DATA_DIR / "nipa_ict_buyers.csv"


def _get_api_key() -> Optional[str]:
    return os.getenv("NIPA_API_KEY") or os.getenv(
        "PUBLIC_DATA_API_KEY",
        "83b96790de580e57527e049d59bfcb18ae34d2bfe646c11a5d2ee6b3d95e9b23"
    )


def fetch_nipa_buyers_all(force_refresh: bool = False) -> pd.DataFrame:
    """전체 NIPA 해외바이어 데이터 반환 (CSV 캐시 우선, 없으면 API 호출)"""
    if NIPA_CSV.exists() and not force_refresh:
        df = pd.read_csv(NIPA_CSV)
        logger.info(f"[NIPA] CSV 캐시 로드: {len(df)}건")
        return df

    api_key = _get_api_key()
    logger.info("[NIPA] API 전체 수집 시작...")

    all_items = []
    per_page = 100

    # 1페이지로 총 건수 확인
    r = requests.get(NIPA_BASE_URL, params={
        "serviceKey": api_key, "numOfRows": "1", "pageNo": "1", "_type": "json"
    }, timeout=10)
    total = r.json().get("response", {}).get("body", {}).get("totalCount", 0)
    total_pages = math.ceil(total / per_page)
    logger.info(f"[NIPA] 총 {total}건 / {total_pages}페이지")

    for page in range(1, total_pages + 1):
        try:
            r = requests.get(NIPA_BASE_URL, params={
                "serviceKey": api_key,
                "numOfRows": str(per_page),
                "pageNo": str(page),
                "_type": "json"
            }, timeout=10)
            items = r.json().get("response", {}).get("body", {}).get("items", [])
            all_items.extend(items)
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"[NIPA] 페이지 {page} 오류: {e}")
            continue

    df = pd.DataFrame(all_items)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(NIPA_CSV, index=False, encoding="utf-8-sig")
    logger.info(f"[NIPA] 수집 완료 {len(df)}건 → {NIPA_CSV}")
    return df


def search_nipa_buyers(
    country: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    NIPA 해외바이어 검색
    - country: 국가명 키워드 (예: '미국', 'USA', '베트남')
    - keyword: 회사명 키워드
    - limit: 최대 반환 건수
    """
    df = fetch_nipa_buyers_all()
    if df.empty:
        return []

    # 국가 필터
    COUNTRY_ALIASES = {
        "US": ["미국", "usa", "united states", "america"],
        "VN": ["베트남", "vietnam", "viet nam"],
        "TH": ["태국", "thailand"],
        "JP": ["일본", "japan"],
        "DE": ["독일", "germany"],
        "SG": ["싱가포르", "singapore"],
        "MY": ["말레이시아", "malaysia"],
        "ID": ["인도네시아", "indonesia"],
        "IN": ["인도", "india"],
        "CN": ["중국", "china"],
        "AE": ["아랍에미리트", "uae", "dubai", "두바이"],
        "AU": ["호주", "australia"],
        "GB": ["영국", "uk", "united kingdom"],
        "CA": ["캐나다", "canada"],
    }

    result = df.copy()

    if country:
        country_upper = country.upper()
        aliases = COUNTRY_ALIASES.get(country_upper, [country.lower()])
        aliases_lower = [a.lower() for a in aliases]

        def match_country(nation_name: str) -> bool:
            if not isinstance(nation_name, str):
                return False
            n = nation_name.lower()
            return any(alias in n for alias in aliases_lower)

        result = result[result["nationName"].apply(match_country)]

    if keyword:
        kw = keyword.lower()
        result = result[result["buyName"].str.lower().str.contains(kw, na=False)]

    # 최신 등록순 정렬
    if "regDateStr" in result.columns:
        result = result.sort_values("regDateStr", ascending=False)

    records = []
    for _, row in result.head(limit).iterrows():
        records.append({
            "source": "NIPA_ICT_2025",
            "company_name": row.get("buyName", ""),
            "country": row.get("nationName", ""),
            "phone": row.get("phone", ""),
            "registered_date": row.get("regDateStr", ""),
            "detail_link": row.get("detailLink", ""),
            "buy_no": row.get("buyNo", ""),
            "email": "",   # NIPA 기본 제공 없음 (상세 링크에서 추가 수집 가능)
            "notes": "ICT/IT 분야 바이어 (NIPA 글로벌ICT포털)"
        })

    logger.info(f"[NIPA] 검색결과 country={country} keyword={keyword} → {len(records)}건")
    return records


def get_nipa_stats() -> dict:
    """NIPA 데이터 통계 정보"""
    df = fetch_nipa_buyers_all()
    if df.empty:
        return {"total": 0, "countries": {}}

    nation_counts = df["nationName"].value_counts().head(20).to_dict()
    return {
        "total": len(df),
        "countries_top20": nation_counts,
        "source": "NIPA_글로벌ICT포털_해외바이어정보",
        "last_updated": "2025-12",
        "fields": list(df.columns),
        "note": "ICT/IT 업종 특화, 이메일 없음(전화번호+상세링크 제공)"
    }
