"""Layer 3 — 수입 규모 검증 (Import Volume + MOQ Filter)
데이터: 세관 수입 금액/수량, HS코드 통계, UN Comtrade
로직:
  - 월 수입금액($) 범위: 사용자가 min/max 직접 입력
  - MOQ 필터: 바이어의 평균 주문 단위 ≥ 판매자 MOQ
  - Buying Power Score 산출 (0~100)
  - 셋 중 하나라도 미달이면 FAIL + 실패 사유 명시

목표: 구매력 있는 바이어 매칭률 85%+
"""
import os
import asyncio
import math
import httpx
from pydantic import BaseModel, Field
from typing import Optional


# ── 사용자 입력 필터 기준 ─────────────────────────────────────────────────
class Layer3Filter(BaseModel):
    """사용자가 직접 입력하는 Layer 3 필터 조건"""
    monthly_import_min_usd: float = Field(
        0, ge=0, description="월 수입금액 최솟값 ($) — 0이면 필터 미적용"
    )
    seller_moq_units: int = Field(
        0, ge=0, description="판매자 MOQ (개) — 0이면 MOQ 필터 미적용"
    )
    seller_unit_price_usd: float = Field(
        0, ge=0, description="판매자 단가 ($) — MOQ 금액 환산용"
    )


class BuyingPowerResult(BaseModel):
    company_name: str
    country: str
    hs_code: str

    # 수입 규모 수치
    monthly_import_usd: float           # 월 수입금액 (6개월 평균)
    annual_import_usd: float            # 연간 추정 수입금액
    avg_order_units: int                # 건당 평균 주문 수량 (추정)
    hs_market_share_pct: float          # HS코드 시장 점유율
    buying_power_score: float           # 0~100
    import_frequency: str               # "월간" | "분기" | "반기" | "연간"
    growth_trend: str                   # "증가" | "유지" | "감소"

    # 필터 결과
    monthly_range_pass: bool            # 월 금액 하한 통과
    moq_pass: bool                      # MOQ 필터 통과
    pass_layer3: bool                   # 전체 통과 (AND)

    # 판정 상세
    monthly_range_status: str           # 금액 하한 결과 메시지
    moq_status: str                     # MOQ 결과 메시지
    reason: str                         # 최종 사유


# ── UN Comtrade 스냅샷 ────────────────────────────────────────────────────
UN_COMTRADE_SNAPSHOT = {
    ("VN", "330499"): 85_000_000,
    ("VN", "870830"): 220_000_000,
    ("VN", "210690"): 45_000_000,
    ("TH", "330499"): 120_000_000,
    ("US", "330499"): 8_500_000_000,
}


async def fetch_un_comtrade(hs_code: str, country: str) -> Optional[float]:
    """UN Comtrade API v3 — HS코드별 국가 연간 수입 통계"""
    api_key = os.getenv("UN_COMTRADE_KEY", "")
    hs6 = hs_code[:6]

    if api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://comtradeapi.un.org/data/v1/get/C/A/HS",
                    params={
                        "reporterCode": _iso2_to_m49(country),
                        "cmdCode": hs6,
                        "flowCode": "M",
                        "period": "2024",
                        "subscription-key": api_key,
                    },
                )
                if resp.status_code == 200:
                    records = resp.json().get("data", [])
                    if records:
                        return float(records[0].get("primaryValue", 0))
        except Exception:
            pass

    return UN_COMTRADE_SNAPSHOT.get((country, hs6), None)


def _iso2_to_m49(iso2: str) -> str:
    m49 = {"VN": "704", "TH": "764", "US": "842", "DE": "276", "JP": "392", "CN": "156"}
    return m49.get(iso2, "0")


def _infer_frequency(shipment_count: int) -> str:
    """6개월 선적 횟수 → 빈도 라벨"""
    monthly_avg = shipment_count / 6
    if monthly_avg >= 1.0:
        return "월간"
    elif monthly_avg >= 0.5:
        return "분기"
    elif monthly_avg >= 0.17:
        return "반기"
    else:
        return "연간"


def _compute_buying_power(
    annual_import_usd: float,
    shipment_count: int,
    hs_market_share_pct: float,
) -> float:
    """Buying Power Score (0~100)"""
    # 규모 40점
    if annual_import_usd > 0:
        log_val = math.log10(max(annual_import_usd, 1))
        max_log = math.log10(2_000_000)
        size_score = min(log_val / max_log, 1.0) * 40
    else:
        size_score = 0

    # 점유율 35점
    share_score = min(hs_market_share_pct / 5.0, 1.0) * 35

    # 빈도 25점
    freq_map = {"월간": 25, "분기": 18, "반기": 12, "연간": 5}
    freq_score = freq_map.get(_infer_frequency(shipment_count), 5)

    return round(size_score + share_score + freq_score, 1)


def _check_monthly_range(
    monthly_usd: float,
    f: Layer3Filter,
) -> tuple[bool, str]:
    """월 수입금액 최솟값 필터 (하한만)"""
    if f.monthly_import_min_usd <= 0:
        return True, f"✅ 금액 조건 없음 (월 ${monthly_usd:,.0f})"

    if monthly_usd < f.monthly_import_min_usd:
        return False, (
            f"⛔ 월 수입금액 ${monthly_usd:,.0f} "
            f"< 최솟값 ${f.monthly_import_min_usd:,.0f}"
        )

    return True, f"✅ 월 수입금액 ${monthly_usd:,.0f} (≥ ${f.monthly_import_min_usd:,.0f} 충족)"


def _check_moq(
    avg_order_units: int,
    avg_order_usd: float,
    f: Layer3Filter,
) -> tuple[bool, str]:
    """MOQ 필터: 바이어 평균 주문 단위 ≥ 판매자 MOQ"""
    if f.seller_moq_units <= 0:
        return True, "✅ MOQ 조건 없음"

    if f.seller_unit_price_usd > 0:
        # 단가로 수량 역산
        estimated_units = int(avg_order_usd / f.seller_unit_price_usd)
    else:
        estimated_units = avg_order_units

    if estimated_units >= f.seller_moq_units:
        return True, (
            f"✅ MOQ 충족 — 바이어 주문 약 {estimated_units:,}개 "
            f"≥ 판매자 MOQ {f.seller_moq_units:,}개"
        )
    else:
        return False, (
            f"⛔ MOQ 미충족 — 바이어 주문 약 {estimated_units:,}개 "
            f"< 판매자 MOQ {f.seller_moq_units:,}개"
        )


class ImportVolumeVerifier:
    """Layer 3: 수입 규모 + MOQ 검증 서비스"""

    async def verify(
        self,
        company_name: str,
        country: str,
        hs_code: str,
        trade_value_usd: float,         # 6개월 총 거래금액
        shipment_count: int,            # 6개월 선적 횟수
        layer3_filter: Optional[Layer3Filter] = None,
    ) -> BuyingPowerResult:
        f = layer3_filter or Layer3Filter()

        # 월 수입금액 (6개월 평균)
        monthly_usd = trade_value_usd / 6
        annual_usd = trade_value_usd * 2   # 6개월 × 2

        # 건당 평균 주문 금액 → 수량 추정
        avg_order_usd = trade_value_usd / max(shipment_count, 1)
        avg_order_units = (
            int(avg_order_usd / f.seller_unit_price_usd)
            if f.seller_unit_price_usd > 0
            else 0
        )

        # UN Comtrade 시장 점유율
        country_total = await fetch_un_comtrade(hs_code, country)
        if not country_total:
            country_total = max(annual_usd * 100, 1_000_000)
        market_share_pct = round((annual_usd / country_total) * 100, 3)

        # 성장 추세
        trend = "증가" if shipment_count >= 12 else "유지" if shipment_count >= 5 else "감소"

        # Buying Power Score
        buying_power = _compute_buying_power(annual_usd, shipment_count, market_share_pct)

        # ── 필터 판정 ──────────────────────────────────────────────────────
        monthly_pass, monthly_msg = _check_monthly_range(monthly_usd, f)
        moq_pass, moq_msg = _check_moq(avg_order_units, avg_order_usd, f)

        pass_l3 = monthly_pass and moq_pass

        # 최종 사유
        if pass_l3:
            if buying_power >= 70:
                reason = f"✅ Layer 3 통과 — 구매력 우수 (점수 {buying_power})"
            elif buying_power >= 40:
                reason = f"✅ Layer 3 통과 — 구매력 보통 (점수 {buying_power})"
            else:
                reason = f"✅ Layer 3 통과 — 구매력 낮음 (점수 {buying_power})"
        else:
            fails = []
            if not monthly_pass:
                fails.append(monthly_msg)
            if not moq_pass:
                fails.append(moq_msg)
            reason = " | ".join(fails)
        return BuyingPowerResult(
            company_name=company_name,
            country=country,
            hs_code=hs_code,
            monthly_import_usd=round(monthly_usd, 0),
            annual_import_usd=round(annual_usd, 0),
            avg_order_units=avg_order_units,
            hs_market_share_pct=market_share_pct,
            buying_power_score=buying_power,
            import_frequency=_infer_frequency(shipment_count),
            growth_trend=trend,
            monthly_range_pass=monthly_pass,
            moq_pass=moq_pass,
            pass_layer3=pass_l3,
            monthly_range_status=monthly_msg,
            moq_status=moq_msg,
            reason=reason,
        )

    async def verify_batch(
        self,
        buyers: list,
        layer3_filter: Optional[Layer3Filter] = None,
    ) -> list[BuyingPowerResult]:
        tasks = [
            self.verify(
                b.company_name,
                b.country,
                b.hs_codes[0] if b.hs_codes else "",
                b.total_trade_value_usd,
                b.shipment_count,
                layer3_filter,
            )
            for b in buyers
        ]
        return await asyncio.gather(*tasks)
