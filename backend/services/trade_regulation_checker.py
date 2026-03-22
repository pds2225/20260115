"""
KOTRA 수입규제 현황 기반 수출 규제 리스크 체커
데이터: 대한무역투자진흥공사_국별 대세계 수입규제 현황_20250603.csv (4,942건 → 정제 후 27,959건)

Layer 2 신용검증에 추가 레이어로 활용:
- HS코드 × 수출 대상국 조합으로 반덤핑/상계관세/세이프가드 규제 여부 확인
- 규제 있으면 WARN (FAIL은 아님) + 결제조건 강화 권고
"""

from __future__ import annotations

import os
import re
import functools
import pandas as pd
from typing import Optional

# ── DB 경로 ────────────────────────────────────────────────────────────────
_DB_PATH = os.path.join(
    os.path.dirname(__file__),     # backend/services/
    "..", "..",                     # → value_up_ai/
    "data", "trade_regulation_db.csv",
)
_DB_PATH = os.path.normpath(_DB_PATH)

# ── 국가코드 ↔ 국가명 매핑 (규제 DB의 규제시행국은 ISO 2자리 코드로 저장) ─────
# target_country 컬럼은 '한국', '중국' 등 텍스트이므로 KR 매핑 포함
_COUNTRY_NAME_TO_CODE: dict[str, str] = {
    "한국": "KR",
    "대한민국": "KR",
    "korea": "KR",
    "south korea": "KR",
    "중국": "CN",
    "china": "CN",
    "미국": "US",
    "united states": "US",
    "usa": "US",
    "일본": "JP",
    "japan": "JP",
    "대만": "TW",
    "taiwan": "TW",
    "인도": "IN",
    "india": "IN",
    "베트남": "VN",
    "vietnam": "VN",
    "유럽": "EU",
    "eu": "EU",
    "독일": "DE",
    "germany": "DE",
    "영국": "GB",
    "uk": "GB",
    "캐나다": "CA",
    "canada": "CA",
    "호주": "AU",
    "australia": "AU",
    "러시아": "RU",
    "russia": "RU",
    "브라질": "BR",
    "brazil": "BR",
    "멕시코": "MX",
    "mexico": "MX",
    "태국": "TH",
    "thailand": "TH",
    "인도네시아": "ID",
    "indonesia": "ID",
    "말레이시아": "MY",
    "malaysia": "MY",
    "터키": "TR",
    "turkey": "TR",
    "이집트": "EG",
    "egypt": "EG",
    "파키스탄": "PK",
    "pakistan": "PK",
    "아랍에미리트": "AE",
    "uae": "AE",
    "필리핀": "PH",
    "philippines": "PH",
    "싱가포르": "SG",
    "singapore": "SG",
    "방글라데시": "BD",
    "bangladesh": "BD",
    "나이지리아": "NG",
    "nigeria": "NG",
}

# 규제형태 단축명
_REG_TYPE_SHORT: dict[str, str] = {
    "반덤핑(규제중)": "반덤핑",
    "상계관세(규제중)": "상계관세",
    "세이프가드(규제중)": "세이프가드",
    "우회수출(반덤핑)(규제중)": "우회수출(반덤핑)",
    "우회수출(상계관세)(규제중)": "우회수출(상계관세)",
    "우회수출(세이프가드)(규제중)": "우회수출(세이프가드)",
    "우회수출(반덤핑/상계관세)(규제중)": "우회수출(반덤핑/상계관세)",
}


# ── 캐싱 로더 ─────────────────────────────────────────────────────────────
@functools.lru_cache(maxsize=1)
def load_regulation_db() -> pd.DataFrame:
    """
    trade_regulation_db.csv 로드 (프로세스 내 캐싱).
    컬럼: regulation_country, product_name, regulation_type,
          target_country, tariff_rate, hs_code_6
    """
    if not os.path.exists(_DB_PATH):
        raise FileNotFoundError(
            f"규제 DB 파일 없음: {_DB_PATH}\n"
            "data/trade_regulation_db.csv 를 먼저 생성하세요."
        )
    df = pd.read_csv(_DB_PATH, encoding="utf-8-sig", dtype=str)
    df = df.fillna("")

    # hs_code_6 숫자 정규화
    df["hs_code_6"] = df["hs_code_6"].str.strip()

    # regulation_type 앞뒤 공백 제거
    df["regulation_type"] = df["regulation_type"].str.strip()

    return df


def _normalize_hs(hs_code: str) -> str:
    """숫자만 추출 후 앞 6자리"""
    digits = re.sub(r"\D", "", str(hs_code))
    return digits[:6] if len(digits) >= 6 else digits


def _parse_tariff_rate(raw: str) -> str:
    """관세율 필드에서 대표 숫자값 추출 (첫 번째 퍼센트 값)"""
    if not raw:
        return ""
    # "ㅇ 판정결과 : 12 ~ 25%..." 형태에서 숫자 추출
    m = re.search(r"(\d[\d.,~\s%]+)", raw)
    if m:
        val = m.group(1).strip().rstrip(",").strip()
        return val[:50]  # 너무 길면 자름
    return raw[:50]


def _is_korean_target(target_country: str) -> bool:
    """target_country 필드에 한국/KR 포함 여부"""
    t = target_country.lower().strip()
    for kw in ["한국", "대한민국", "korea", "kr"]:
        if kw in t:
            return True
    return False


def _country_matches(target_field: str, country_code: str) -> bool:
    """
    target_country 텍스트 필드(예: '한국, 중국')에서
    해당 country_code 포함 여부 확인.
    """
    if not target_field or not country_code:
        return False
    t_lower = target_field.lower()
    # 코드 → 이름 역매핑
    code_upper = country_code.upper()
    matching_names = [
        name for name, code in _COUNTRY_NAME_TO_CODE.items()
        if code == code_upper
    ]
    for name in matching_names:
        if name.lower() in t_lower:
            return True
    # ISO 코드 직접 매치 (target_country에 코드가 들어있는 경우)
    if code_upper.lower() in t_lower:
        return True
    return False


# ── 핵심 함수 ─────────────────────────────────────────────────────────────

def check_trade_regulation(
    hs_code: str,
    target_country: str,
    origin_country: str = "KR",
) -> dict:
    """
    HS코드 × 수출 대상국(규제시행국) 조합으로 규제 여부 조회.

    Parameters
    ----------
    hs_code        : 조회할 HS코드 (6자리 또는 더 길어도 앞 6자리 사용)
    target_country : 수출 대상국 ISO 2자리 코드 (예: "US", "CN")
    origin_country : 원산지/수출국 코드 (기본 "KR")
                     규제대상국 필터에 활용.

    Returns
    -------
    dict:
        has_regulation  : bool
        regulations     : list of {"type", "tariff_rate", "status", "product_name"}
        risk_level      : "HIGH" | "MEDIUM" | "LOW" | "NONE"
        recommendation  : 결제조건 강화 권고 문자열
        note            : 상세 설명
    """
    if not hs_code:
        return _empty_result()

    hs6 = _normalize_hs(hs_code)
    if len(hs6) < 6:
        return _empty_result()

    db = load_regulation_db()

    # ① HS코드 + 규제시행국(= 수출 대상국) 필터
    mask_hs = db["hs_code_6"] == hs6
    mask_country = db["regulation_country"].str.upper() == target_country.upper()
    df_match = db[mask_hs & mask_country]

    if df_match.empty:
        # 규제시행국 필터 없이 HS코드만으로 전 세계 규제 확인
        df_hs_only = db[mask_hs]
        if df_hs_only.empty:
            return _empty_result()
        else:
            # 해당 HS코드가 다른 나라에서 규제 중이지만 target_country는 아님
            # → LOW 경고만
            countries = df_hs_only["regulation_country"].unique().tolist()
            return {
                "has_regulation": False,
                "regulations": [],
                "risk_level": "NONE",
                "recommendation": "",
                "note": (
                    f"HS {hs6}은 {target_country} 규제 없음 "
                    f"(타국 규제 존재: {', '.join(countries[:5])})"
                ),
            }

    # ② origin_country 필터: target_country 컬럼에 KR 포함 행 우선
    df_kr = df_match[df_match["target_country"].apply(
        lambda x: _country_matches(x, origin_country)
    )]
    df_relevant = df_kr if not df_kr.empty else df_match

    # ③ 규제 목록 구성
    regulations = []
    seen = set()
    for _, row in df_relevant.iterrows():
        reg_type_raw = row["regulation_type"].strip()
        reg_type = _REG_TYPE_SHORT.get(reg_type_raw, reg_type_raw)
        tariff = _parse_tariff_rate(row["tariff_rate"])
        product = row["product_name"][:60] if row["product_name"] else ""
        key = (reg_type, tariff)
        if key not in seen:
            seen.add(key)
            regulations.append({
                "type": reg_type,
                "tariff_rate": tariff,
                "status": "규제중",
                "product_name": product,
            })

    # ④ 리스크 레벨 결정
    types_present = {r["type"] for r in regulations}
    if any(t in types_present for t in ["반덤핑", "상계관세", "우회수출(반덤핑)", "우회수출(상계관세)", "우회수출(반덤핑/상계관세)"]):
        risk_level = "HIGH" if len(regulations) >= 2 else "MEDIUM"
    elif "세이프가드" in types_present or "우회수출(세이프가드)" in types_present:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # ⑤ 권고 문자열
    recommendation = _build_recommendation(risk_level)

    # ⑥ 노트 생성
    first = regulations[0] if regulations else {}
    product_short = first.get("product_name", "")[:40]
    tariff_short = first.get("tariff_rate", "")
    note = (
        f"{target_country}의 {origin_country}산 HS{hs6}"
        f" {first.get('type','')} 규제"
        + (f" (관세율 {tariff_short})" if tariff_short else "")
        + (f" — {product_short}" if product_short else "")
    )

    return {
        "has_regulation": True,
        "regulations": regulations,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "note": note,
    }


def get_regulated_countries(hs_code: str) -> list[str]:
    """
    특정 HS코드(6자리)를 규제하고 있는 국가(규제시행국) 목록 반환.
    """
    if not hs_code:
        return []
    hs6 = _normalize_hs(hs_code)
    if len(hs6) < 6:
        return []
    db = load_regulation_db()
    countries = (
        db[db["hs_code_6"] == hs6]["regulation_country"]
        .unique()
        .tolist()
    )
    return sorted(countries)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────

def _empty_result() -> dict:
    return {
        "has_regulation": False,
        "regulations": [],
        "risk_level": "NONE",
        "recommendation": "",
        "note": "",
    }


def _build_recommendation(risk_level: str) -> str:
    if risk_level == "HIGH":
        return (
            "⚠️ 고위험 수출규제 감지 — L/C at sight 또는 T/T 선금 100% 권장. "
            "K-SURE 수출보험 가입 필수 검토."
        )
    elif risk_level == "MEDIUM":
        return (
            "⚠️ 수출규제 감지 — T/T 선금 50% 이상 또는 L/C 권장. "
            "K-SURE 단기수출보험 가입 검토."
        )
    elif risk_level == "LOW":
        return "⚠️ 경미한 수출규제 감지 — 거래 진행 가능하나 관세 부담 확인 권장."
    return ""
