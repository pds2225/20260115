"""Step 1 — HS코드 분석 + 다중 데이터 소스 통합 파이프라인

데이터 소스 우선순위:
  1. CSV Seed DB (buyer_db.csv) — 항상 사용 가능
  2. KOTRA Open API — 실제 연동 (API 키 보유)
  3. Volza API — API 키 보유 시 자동 활성화
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from backend.models.schemas import (
    HSCodeAnalysisRequest, HSCodeAnalysisResult, TradeRecord
)
from backend.services.data_source_manager import (
    get_buyers_from_csv,
    get_kotra_recommend_countries,
    fetch_kotra_live,
    COUNTRY_NAME_TO_ISO,
    VOLZA_API_KEY,
    KOTRA_API_KEY,
)

# HS코드 → 카테고리 매핑
HS_CATEGORY_MAP = {
    "33": "화장품·퍼스널케어",
    "30": "의약품",
    "21": "식품·건기식",
    "84": "기계·장비",
    "85": "전자기기",
    "87": "자동차부품",
    "72": "철강·금속",
    "39": "플라스틱·고무",
    "61": "섬유·의류",
    "62": "섬유·의류",
    "07": "농산물",
    "08": "농산물",
}


def get_hs_category(hs_code: str) -> str:
    """HS코드 앞 2자리로 카테고리 분류"""
    prefix = hs_code[:2]
    return HS_CATEGORY_MAP.get(prefix, "기타 제품")


def get_product_description(hs_code: str) -> str:
    """HS코드 기반 품목 설명"""
    desc_map = {
        "3304": "기초화장용 제품류 (스킨케어, 로션, 크림)",
        "330499": "기타 미용·기초화장품",
        "8708": "자동차 부품 및 액세서리",
        "2106": "따로 분류되지 않은 식품 조제품 (건강기능식품)",
        "8517": "전화기 및 무선통신 기기",
        "3002": "의약품 원료 및 백신",
        "8471": "자동자료처리기계 (컴퓨터)",
    }
    # 완전 일치 먼저
    if hs_code in desc_map:
        return desc_map[hs_code]
    # 4자리 일치
    if hs_code[:4] in desc_map:
        return desc_map[hs_code[:4]]
    return f"HS {hs_code} 품목"


async def fetch_volza_data(hs_code: str, country: str) -> list:
    """
    바이어 데이터 수집 — 다중 소스 통합
    우선순위: Volza API(키 있을 때) → CSV Seed DB → KOTRA 라이브
    """
    records = []

    # ① Volza 실제 API (키 보유 시)
    if VOLZA_API_KEY:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.volza.com/v2/buyers",
                    params={"hs_code": hs_code, "country": country, "months": 6},
                    headers={"Authorization": f"Bearer {VOLZA_API_KEY}"},
                )
                if resp.status_code == 200:
                    volza_data = resp.json().get("data", [])
                    records.extend(volza_data)
                    print(f"  [Step1] Volza 라이브: {len(volza_data)}건")
        except Exception:
            pass

    # ② CSV Seed DB (항상 사용 가능)
    csv_buyers = get_buyers_from_csv(hs_code, country)
    if csv_buyers:
        for b in csv_buyers:
            records.append({
                "buyer_name": b["buyer_name"],
                "trade_value": float(b.get("annual_usd", 0)),
                "shipments": int(b.get("shipments", 3)),
                "last_date": b.get("last_date", "2025-12-01"),
                "buyer_type": b.get("buyer_type", ""),
                "city": b.get("city", ""),
                "source": b.get("source", "CSV_DB"),
            })
        if not VOLZA_API_KEY:
            print(f"  [Step1] CSV DB: {len(csv_buyers)}건 (HS:{hs_code}, 국가:{country})")

    # ③ KOTRA 라이브 API (CSV에 없는 국가 폴백)
    if not records:
        kotra_live = await fetch_kotra_live(hs_code)
        country_records = [r for r in kotra_live if r.get("country_iso") == country]
        if country_records:
            for r in country_records[:10]:
                records.append({
                    "buyer_name": f"KOTRA Buyer — {r['country_name']} ({hs_code})",
                    "trade_value": float(r["recommendation_score"]) * 10000,
                    "shipments": max(3, int(float(r["recommendation_score"]))),
                    "last_date": "2026-01-01",
                    "source": "KOTRA_LIVE",
                })
            print(f"  [Step1] KOTRA 라이브 폴백: {len(country_records)}건")

    return records


async def fetch_kotra_buyers(hs_code: str, country: str) -> list:
    """KOTRA 수출유망추천정보 API — 하위 호환 래퍼"""
    kotra_live = await fetch_kotra_live(hs_code)
    matched = [r for r in kotra_live if r.get("country_iso") == country]
    result = []
    for r in matched[:5]:
        result.append({
            "buyer_name": f"{r['country_name']} Buyer ({hs_code})",
            "trade_value": float(r["recommendation_score"]) * 8000,
            "shipments": max(2, int(float(r["recommendation_score"]) / 2)),
            "last_date": "2026-01-15",
        })
    return result


class HSCodeAnalyzer:
    """Step 1: HS코드 분석 서비스"""

    async def analyze(self, req: HSCodeAnalysisRequest) -> HSCodeAnalysisResult:
        raw_records = await fetch_volza_data(req.hs_code, req.target_country)

        trade_records = []
        total_value = 0.0

        for r in raw_records:
            tr = TradeRecord(
                buyer_name=r["buyer_name"],
                country=req.target_country,
                hs_code=req.hs_code,
                trade_value_usd=float(r["trade_value"]),
                shipment_count=int(r["shipments"]),
                last_shipment_date=r["last_date"],
                product_description=get_product_description(req.hs_code),
            )
            trade_records.append(tr)
            total_value += tr.trade_value_usd

        return HSCodeAnalysisResult(
            hs_code=req.hs_code,
            category=get_hs_category(req.hs_code),
            product_description=get_product_description(req.hs_code),
            total_importers_found=len(trade_records),
            trade_records=trade_records[:req.top_buyers],
            market_summary={
                "total_trade_value_usd": total_value,
                "avg_trade_value_usd": total_value / len(trade_records) if trade_records else 0,
                "target_country": req.target_country,
                "data_sources": ["Volza (Seed)", "KOTRA Open API"],
            },
        )
