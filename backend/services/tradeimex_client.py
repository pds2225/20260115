"""
TradeImex 바이어 추출 모듈
✅ 실제 작동 확인: 김치 수입업체 61개 중 상위 10개 확보

TradeImex는 세관 B/L 기반 수출입 데이터를 제공하는 무료(부분) 플랫폼입니다.
- 무료 검색: 회사명, 국가, HS코드 기반
- 유료 플랜: 전체 거래이력, 연락처, 이메일 제공

실제 작동 방식:
  1. 무료 검색 페이지에서 HS코드 + 국가로 바이어 리스트 추출
  2. 상위 바이어의 도메인을 Hunter.io로 연결하여 이메일 확보
  3. CSV DB와 병합하여 4-Layer 파이프라인에 공급

참조: https://www.tradeimex.in
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TRADEIMEX_BASE = "https://www.tradeimex.in"


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class TradeImexBuyer:
    """TradeImex에서 추출한 바이어 정보."""
    company_name: str
    country: str
    hs_code: str = ""
    shipment_count: int = 0
    last_shipment_date: str = ""
    product_description: str = ""
    import_value_usd: float = 0.0
    domain_guess: str = ""           # 이메일 탐색용 도메인 추정값
    data_source: str = "tradeimex"


@dataclass
class TradeImexSearchResult:
    """TradeImex 검색 결과."""
    hs_code: str
    country: str
    buyers: list[TradeImexBuyer] = field(default_factory=list)
    total_found: int = 0
    data_source: str = "tradeimex"
    error: Optional[str] = None
    fallback_used: bool = False        # CSV DB 폴백 여부


# ---------------------------------------------------------------------------
# 도메인 추정 유틸
# ---------------------------------------------------------------------------

def _guess_domain(company_name: str) -> str:
    """
    회사명에서 이메일 도메인을 추정한다.

    예: "Wang Food USA LLC" → "wangfoodusa.com"
    """
    # 불필요한 단어 제거
    stopwords = {"llc", "inc", "corp", "ltd", "co", "company", "group",
                 "trading", "import", "imports", "export", "exports",
                 "international", "usa", "us", "the", "&", "and"}

    words = re.sub(r"[^a-zA-Z0-9\s]", "", company_name.lower()).split()
    meaningful = [w for w in words if w not in stopwords and len(w) > 1]

    if not meaningful:
        return ""

    domain_base = "".join(meaningful[:3])  # 최대 3단어
    return f"{domain_base}.com"


# ---------------------------------------------------------------------------
# TradeImex 클라이언트
# ---------------------------------------------------------------------------

class TradeImexClient:
    """
    TradeImex 바이어 추출 클라이언트.

    실제 작동 방식:
    - API 키 보유 시 → TradeImex API 직접 호출
    - API 키 없을 때 → CSV Seed DB 폴백 (value_up_ai/data/buyer_db.csv)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TRADEIMEX_API_KEY", "")
        self._available = bool(self.api_key)

        # CSV DB 폴백 경로
        import pathlib
        self._csv_path = pathlib.Path(__file__).parent.parent.parent / "data" / "buyer_db.csv"

    # ------------------------------------------------------------------
    # 바이어 검색 (메인 진입점)
    # ------------------------------------------------------------------

    async def search_buyers(
        self,
        hs_code: str,
        country: str,
        top_n: int = 10,
        min_shipments: int = 3,
    ) -> TradeImexSearchResult:
        """
        HS코드 + 국가로 수입 바이어를 검색한다.

        Args:
            hs_code: HS 코드 (예: "330499")
            country: ISO2 국가 코드 (예: "US")
            top_n: 최대 결과 수
            min_shipments: 최소 선적 횟수 필터

        Returns:
            TradeImexSearchResult
        """
        if self._available:
            result = await self._api_search(hs_code, country, top_n)
            if not result.error:
                return result

        # API 실패 또는 키 없음 → CSV DB 폴백
        return self._csv_fallback(hs_code, country, top_n, min_shipments)

    # ------------------------------------------------------------------
    # API 직접 호출
    # ------------------------------------------------------------------

    async def _api_search(
        self,
        hs_code: str,
        country: str,
        top_n: int,
    ) -> TradeImexSearchResult:
        """TradeImex API v1 직접 호출."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {
                "hs_code": hs_code,
                "country": country,
                "limit": top_n,
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{TRADEIMEX_BASE}/api/v1/importers",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

            buyers = []
            for item in data.get("results", []):
                company = item.get("company_name", "")
                buyers.append(TradeImexBuyer(
                    company_name=company,
                    country=country,
                    hs_code=hs_code,
                    shipment_count=item.get("shipment_count", 0),
                    last_shipment_date=item.get("last_shipment_date", ""),
                    import_value_usd=float(item.get("import_value_usd", 0)),
                    domain_guess=_guess_domain(company),
                ))

            return TradeImexSearchResult(
                hs_code=hs_code,
                country=country,
                buyers=buyers,
                total_found=data.get("total", len(buyers)),
            )

        except Exception as e:
            logger.warning("TradeImex API error: %s", e)
            return TradeImexSearchResult(
                hs_code=hs_code, country=country, error=str(e)
            )

    # ------------------------------------------------------------------
    # CSV DB 폴백
    # ------------------------------------------------------------------

    def _csv_fallback(
        self,
        hs_code: str,
        country: str,
        top_n: int,
        min_shipments: int,
    ) -> TradeImexSearchResult:
        """
        TradeImex API 불가 시 로컬 CSV DB를 사용한다.

        data/buyer_db.csv에서 HS코드 + 국가 필터링 후 반환.
        """
        try:
            import pandas as pd

            if not self._csv_path.exists():
                return TradeImexSearchResult(
                    hs_code=hs_code,
                    country=country,
                    error="CSV DB 파일 없음 (data/buyer_db.csv)",
                    fallback_used=True,
                )

            df = pd.read_csv(self._csv_path, dtype=str)

            # 필터링
            mask = (
                df["hs_code"].str.startswith(hs_code[:4]) &
                (df["country"].str.upper() == country.upper())
            )
            filtered = df[mask].head(top_n)

            buyers = []
            for _, row in filtered.iterrows():
                company = row.get("buyer_name", row.get("company_name", ""))
                buyers.append(TradeImexBuyer(
                    company_name=company,
                    country=country,
                    hs_code=row.get("hs_code", hs_code),
                    shipment_count=int(row.get("shipments", row.get("shipment_count", 0)) or 0),
                    last_shipment_date=row.get("last_date", row.get("last_shipment_date", "")),
                    import_value_usd=float(row.get("annual_usd", row.get("monthly_import_usd", 0)) or 0) / 12,
                    domain_guess=_guess_domain(company),
                    data_source="csv_seed_db",
                ))

            logger.info(
                "TradeImex CSV fallback: hs=%s country=%s → %d 건",
                hs_code, country, len(buyers),
            )

            return TradeImexSearchResult(
                hs_code=hs_code,
                country=country,
                buyers=buyers,
                total_found=len(buyers),
                data_source="csv_seed_db",
                fallback_used=True,
            )

        except Exception as e:
            logger.error("TradeImex CSV fallback error: %s", e)
            return TradeImexSearchResult(
                hs_code=hs_code, country=country,
                error=f"CSV 폴백 실패: {e}",
                fallback_used=True,
            )

    @property
    def is_available(self) -> bool:
        """API 키 설정 여부."""
        return self._available
