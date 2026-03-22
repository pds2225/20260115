"""
한국무역보험공사(K-SURE) 바이어 검색 API 클라이언트
EndPoint: https://apis.data.go.kr/B552696/buyer/getBuyerList
활용기간: 2026-02-02 ~ 2028-02-02

데이터: 국가별 바이어 정보 (바이어명, 업종명, 품목명, 대상자번호)
조회조건: 국가코드 + (업종코드 OR 품목명 OR 바이어명) 중 1개 이상 필수

K-SURE 국가코드 (자체 체계):
  아시아: VN=176, TH=180, US=450, JP=140, CN=121, SG=171, MY=151, ID=136,
           IN=135, PH=165, AU=?, DE=325, GB=360, FR=?, CA=410
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

KSURE_BASE_URL = "https://apis.data.go.kr/B552696/buyer/getBuyerList"

# K-SURE 자체 국가코드 맵 (ISO2 → K-SURE ctryCd)
KSURE_COUNTRY_CODE = {
    "AF": "110",   # 아프가니스탄
    "BD": "115",   # 방글라데시
    "TW": "120",   # 대만
    "GU": "125",   # 괌
    "HK": "130",   # 홍콩
    "IN": "135",   # 인도
    "ID": "136",   # 인도네시아
    "JP": "140",   # 일본
    "LA": "145",   # 라오스
    "MO": "150",   # 마카오
    "MY": "151",   # 말레이시아
    "MV": "152",   # 몰디브
    "MN": "154",   # 몽골
    "NP": "155",   # 네팔
    "MM": "117",   # 미얀마
    "BN": "118",   # 브루나이
    "CN": "121",   # 중국
    "PK": "160",   # 파키스탄
    "PH": "165",   # 필리핀
    "SG": "171",   # 싱가포르
    "LK": "175",   # 스리랑카
    "VN": "176",   # 베트남
    "TH": "180",   # 태국
    "KH": "181",   # 캄보디아
    "IR": "220",   # 이란
    "BH": "210",   # 바레인
    "JO": "230",   # 요르단
    "KW": "235",   # 쿠웨이트
    "LB": "240",   # 레바논
    "OM": "245",   # 오만
    "QA": "250",   # 카타르
    "SA": "255",   # 사우디아라비아
    "BE": "315",   # 벨기에
    "FI": "320",   # 핀란드
    "DE": "325",   # 독일
    "IS": "330",   # 아이슬란드
    "LU": "340",   # 룩셈부르크
    "MT": "345",   # 몰타
    "NO": "350",   # 노르웨이
    "ES": "355",   # 스페인
    "GB": "360",   # 영국
    "CA": "410",   # 캐나다
    "US": "450",   # 미국
    "BO": "510",   # 볼리비아
    "DO": "520",   # 도미니카공화국
    "EC": "525",   # 에콰도르
    "GT": "530",   # 과테말라
    "MX": "550",   # 멕시코
    "PE": "560",   # 페루
    "KE": "630",   # 케냐
    "MA": "645",   # 모로코
}

# HS코드 → 화장품/뷰티 prodNm 키워드 맵
HS_TO_PRODKEYWORDS = {
    "330499": ["cosmetic", "skincare", "beauty", "serum", "cream", "lotion"],
    "330410": ["lipstick", "lip gloss", "beauty"],
    "330420": ["eye makeup", "mascara", "beauty"],
    "330491": ["powder", "cosmetic", "beauty"],
    "330510": ["shampoo", "hair care"],
    "330590": ["hair", "conditioner"],
    "330300": ["perfume", "fragrance"],
    "210690": ["health supplement", "food"],
    "870830": ["auto parts", "vehicle"],
    "default": ["trade", "import", "wholesale"],
}


def _get_api_key() -> str:
    return os.getenv("K_SURE_API_KEY") or os.getenv(
        "PUBLIC_DATA_API_KEY",
        "83b96790de580e57527e049d59bfcb18ae34d2bfe646c11a5d2ee6b3d95e9b23"
    )


def _get_keywords_for_hs(hs_code: str) -> list[str]:
    """HS코드에 맞는 검색 키워드 반환"""
    hs6 = str(hs_code).replace("-", "").replace(".", "")[:6]
    return HS_TO_PRODKEYWORDS.get(hs6, HS_TO_PRODKEYWORDS["default"])


def search_ksure_buyers(
    country_iso2: str,
    hs_code: str = "330499",
    prod_nm: Optional[str] = None,
    buyer_nm: Optional[str] = None,
    num_of_rows: int = 100,
    page_no: int = 1,
) -> dict:
    """
    K-SURE 바이어검색 API 호출

    Args:
        country_iso2: ISO2 국가코드 (예: US, VN, TH)
        hs_code: HS 코드 (6자리)
        prod_nm: 품목명 키워드 (None이면 HS코드로 자동 선택)
        buyer_nm: 바이어명 검색어
        num_of_rows: 페이지당 결과 수 (최대 100)
        page_no: 페이지 번호

    Returns:
        {
          "ok": bool,
          "total_count": int,
          "country": str,
          "buyers": [{"buyer_name", "industry", "product", "buyer_id", "country", "source"}]
        }
    """
    ctry_cd = KSURE_COUNTRY_CODE.get(country_iso2.upper())
    if not ctry_cd:
        return {"ok": False, "error": f"K-SURE 미지원 국가코드: {country_iso2}", "buyers": []}

    # 검색 키워드 결정
    if prod_nm is None:
        keywords = _get_keywords_for_hs(hs_code)
        prod_nm = keywords[0]  # 첫 번째 키워드 사용

    params = {
        "serviceKey": _get_api_key(),
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "ctryCd": ctry_cd,
        "prodNm": prod_nm,
        "_type": "json",
    }
    if buyer_nm:
        params["buyerNm"] = buyer_nm

    try:
        r = requests.get(KSURE_BASE_URL, params=params, timeout=10)
        d = r.json()
        header = d.get("response", {}).get("header", {})
        body = d.get("response", {}).get("body")

        if header.get("resultCode") != 0 or not body:
            return {
                "ok": False,
                "error": f"code={header.get('resultCode')} {header.get('resultMsg','')}",
                "buyers": [],
            }

        total = body.get("totalCount", 0)
        raw_items = body.get("items", {}).get("item", [])
        if isinstance(raw_items, dict):
            raw_items = [raw_items]

        buyers = []
        for it in raw_items:
            buyers.append({
                "buyer_name": it.get("buyerNm", "").strip(),
                "industry": it.get("industryNm", "").strip(),
                "product": it.get("prodNm", "").strip()[:80],
                "buyer_id": it.get("trgtpsnNo", ""),
                "country": it.get("ctryNm", ""),
                "country_iso2": country_iso2.upper(),
                "source": "KSURE_바이어검색_API",
            })

        logger.info(f"[K-SURE] {country_iso2}/{prod_nm} → {total}건 (page {page_no})")
        return {"ok": True, "total_count": total, "country": country_iso2, "buyers": buyers}

    except Exception as e:
        logger.error(f"[K-SURE] API 오류: {e}")
        return {"ok": False, "error": str(e), "buyers": []}


def search_ksure_multi_keyword(
    country_iso2: str,
    hs_code: str = "330499",
    max_buyers: int = 50,
) -> list[dict]:
    """
    HS코드 기반 여러 키워드로 K-SURE 검색 후 병합 (중복 제거)
    Layer 1/4의 바이어 소스로 활용
    """
    keywords = _get_keywords_for_hs(hs_code)
    seen_ids = set()
    all_buyers = []

    for kw in keywords:
        result = search_ksure_buyers(country_iso2, hs_code, prod_nm=kw, num_of_rows=50)
        if result.get("ok"):
            for b in result["buyers"]:
                bid = b.get("buyer_id") or b.get("buyer_name", "").lower()
                if bid not in seen_ids:
                    seen_ids.add(bid)
                    all_buyers.append(b)
                if len(all_buyers) >= max_buyers:
                    break
        if len(all_buyers) >= max_buyers:
            break
        time.sleep(0.15)

    logger.info(f"[K-SURE] multi-keyword {country_iso2}/{hs_code} → {len(all_buyers)}건")
    return all_buyers[:max_buyers]


def get_ksure_supported_countries() -> dict:
    """K-SURE API 지원 국가 코드 맵 반환"""
    return {
        iso: {"ksure_code": code, "available": True}
        for iso, code in KSURE_COUNTRY_CODE.items()
    }
