"""Step 2 — 거래 이력 필터링
최근 6개월 내 활성 바이어, 최소 5회 수입 실적 기준으로 선별
Activity Score = 거래빈도(40%) + 거래규모(35%) + 연락처 신뢰도(25%)
"""
from datetime import datetime, timedelta
from backend.models.schemas import (
    TradeFilterRequest, TradeFilterResult, ActiveBuyer, HSCodeAnalysisResult
)


def parse_date(date_str: str) -> datetime:
    """다양한 날짜 포맷 파싱"""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.min


def compute_activity_score(
    shipment_count: int,
    trade_value_usd: float,
    last_shipment_date: str,
    months_back: int = 6,
    min_shipments: int = 5,
) -> float:
    """
    Activity Score (0~100)
    - 거래빈도 40%: shipment_count / (min_shipments * 3) × 40
    - 거래규모 35%: log scale (0~500k USD)
    - 최신성 25%: 마지막 선적일이 최근일수록 높음
    """
    import math

    # 거래빈도 점수 (40점 만점)
    freq_score = min(shipment_count / (min_shipments * 3), 1.0) * 40

    # 거래규모 점수 (35점 만점) — log 스케일
    if trade_value_usd > 0:
        log_val = math.log10(max(trade_value_usd, 1))
        max_log = math.log10(500000)
        size_score = min(log_val / max_log, 1.0) * 35
    else:
        size_score = 0

    # 최신성 점수 (25점 만점)
    cutoff = datetime.now() - timedelta(days=months_back * 30)
    last_date = parse_date(last_shipment_date)
    if last_date == datetime.min:
        recency_score = 0
    else:
        days_since = (datetime.now() - last_date).days
        max_days = months_back * 30
        recency_score = max(0, (1 - days_since / max_days)) * 25

    return round(freq_score + size_score + recency_score, 1)


class TradeHistoryFilter:
    """Step 2: 거래 이력 필터링 서비스"""

    def filter(
        self,
        req: TradeFilterRequest,
        analysis_result: HSCodeAnalysisResult,
    ) -> TradeFilterResult:
        cutoff_date = datetime.now() - timedelta(days=req.months_back * 30)
        all_records = analysis_result.trade_records
        active_buyers = []

        for record in all_records:
            # Hard Filter 1: 최소 수입 횟수
            if record.shipment_count < req.min_shipments:
                continue

            # Hard Filter 2: 최근 N개월 내 활동
            last_date = parse_date(record.last_shipment_date)
            if last_date != datetime.min and last_date < cutoff_date:
                continue

            # Hard Filter 3: 최소 거래금액
            if record.trade_value_usd < req.min_trade_value_usd:
                continue

            activity_score = compute_activity_score(
                record.shipment_count,
                record.trade_value_usd,
                record.last_shipment_date,
                req.months_back,
                req.min_shipments,
            )

            active_buyers.append(
                ActiveBuyer(
                    company_name=record.buyer_name,
                    country=record.country,
                    shipment_count=record.shipment_count,
                    total_trade_value_usd=record.trade_value_usd,
                    last_shipment_date=record.last_shipment_date,
                    average_order_value_usd=round(
                        record.trade_value_usd / max(record.shipment_count, 1), 0
                    ),
                    activity_score=activity_score,
                    hs_codes=[record.hs_code],
                )
            )

        # Activity Score 내림차순 정렬
        active_buyers.sort(key=lambda b: b.activity_score, reverse=True)

        return TradeFilterResult(
            total_screened=len(all_records),
            active_buyers_count=len(active_buyers),
            active_buyers=active_buyers,
            filter_criteria={
                "min_shipments": req.min_shipments,
                "months_back": req.months_back,
                "min_trade_value_usd": req.min_trade_value_usd,
                "cutoff_date": cutoff_date.strftime("%Y-%m-%d"),
            },
        )
