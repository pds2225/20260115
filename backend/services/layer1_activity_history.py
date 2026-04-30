"""Layer 1 — 활동 이력 (Activity History)
데이터: 세관 B/L API, KOTRA, UN Comtrade
로직:
  - 6개월 이내 거래 1건이라도 있으면 PASS (점수화 없음)
  - 가장 최근 거래일(last_shipment_date) 표시
  - 허수 제거: 6개월 초과 거래만 있으면 FAIL
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel


class ActivityResult(BaseModel):
    company_name: str
    country: str
    hs_code: str

    # 거래 현황
    semi_annual_shipments: int         # 6개월 선적 횟수
    total_trade_value_usd: float
    avg_shipment_value_usd: float

    # 핵심: 가장 최근 거래일
    last_shipment_date: str            # 원본 날짜 문자열 (e.g. "2025-11-03")
    last_shipment_date_display: str    # 표시용 (e.g. "2025-11-03 (47일 전)")
    days_since_last_shipment: int      # 오늘 기준 경과일

    # 판정 — 6개월(180일) 이내 거래 여부
    has_recent_trade: bool             # True = 6개월 내 거래 있음
    pass_layer1: bool                  # has_recent_trade와 동일
    reason: str


def _parse_date(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    # 파싱 실패 → 아주 오래된 날짜로 처리 (FAIL)
    return datetime.now() - timedelta(days=999)


def _days_label(days: int) -> str:
    """경과일 → 읽기 쉬운 라벨"""
    if days == 0:
        return "오늘"
    elif days <= 7:
        return f"{days}일 전"
    elif days <= 30:
        weeks = days // 7
        return f"약 {weeks}주 전"
    elif days <= 365:
        months = days // 30
        return f"약 {months}개월 전"
    else:
        years = days // 365
        return f"약 {years}년 전"


LAYER1_WINDOW_DAYS = 180  # 6개월 기준


class ActivityHistoryAnalyzer:
    """Layer 1: 활동 이력 분석 서비스 (6개월 이내 거래 여부 판정)"""

    async def analyze(
        self,
        company_name: str,
        country: str,
        hs_code: str,
        shipment_count: int,
        trade_value_usd: float,
        last_shipment_date: str,
        data_period_months: int = 6,
    ) -> ActivityResult:
        last_date = _parse_date(last_shipment_date)
        days_since = (datetime.now() - last_date).days

        # ── 핵심 판정: 180일(6개월) 이내 거래가 1건이라도 있으면 PASS ──
        has_recent = days_since <= LAYER1_WINDOW_DAYS and shipment_count >= 1

        display = f"{last_shipment_date} ({_days_label(days_since)})"

        if has_recent:
            reason = f"✅ 최근 거래 확인 — {display} / 6개월 {shipment_count}건"
        else:
            reason = f"⛔ 최근 6개월 거래 없음 — 마지막 거래: {display}"

        return ActivityResult(
            company_name=company_name,
            country=country,
            hs_code=hs_code,
            semi_annual_shipments=shipment_count,
            total_trade_value_usd=trade_value_usd,
            avg_shipment_value_usd=round(trade_value_usd / max(shipment_count, 1), 0),
            last_shipment_date=last_shipment_date,
            last_shipment_date_display=display,
            days_since_last_shipment=days_since,
            has_recent_trade=has_recent,
            pass_layer1=has_recent,
            reason=reason,
        )

    async def analyze_batch(self, buyers: list) -> list[ActivityResult]:
        tasks = [
            self.analyze(
                b.company_name,
                b.country,
                b.hs_codes[0] if b.hs_codes else "",
                b.shipment_count,
                b.total_trade_value_usd,
                b.last_shipment_date,
            )
            for b in buyers
        ]
        return await asyncio.gather(*tasks)
