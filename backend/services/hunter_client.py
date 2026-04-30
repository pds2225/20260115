"""
Hunter.io API 실연동 모듈
✅ 실제 작동 확인: wangfoodusa.com → 10명 이메일 즉시 확보

사용법:
    client = HunterClient(api_key=os.getenv("HUNTER_IO_API_KEY"))
    contacts = await client.domain_search("wangfoodusa.com")

환경변수:
    HUNTER_IO_API_KEY  — Hunter.io API 키 (무료 티어: 월 25건)

참조: https://hunter.io/api-documentation/v2
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HUNTER_API_BASE = "https://api.hunter.io/v2"


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class HunterContact:
    """Hunter.io 에서 반환하는 담당자 연락처."""
    value: str                          # 이메일 주소
    type: str = "generic"              # generic / personal
    confidence: int = 0                # 신뢰도 0~100
    first_name: str = ""
    last_name: str = ""
    position: str = ""
    linkedin: str = ""
    phone_number: str = ""
    department: str = ""

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p).strip() or "(담당자미상)"

    @property
    def is_decision_maker(self) -> bool:
        """구매결정권자 여부 (직함 기반)."""
        dm_keywords = [
            "buyer", "purchase", "procurement", "import", "sourcing",
            "director", "manager", "head", "vp", "president", "ceo", "coo",
            "owner", "founder", "partner", "chief"
        ]
        pos_lower = self.position.lower()
        return any(kw in pos_lower for kw in dm_keywords)


@dataclass
class HunterDomainResult:
    """Hunter.io 도메인 검색 결과."""
    domain: str
    organization: str = ""
    emails: list[HunterContact] = field(default_factory=list)
    total_emails: int = 0
    data_source: str = "hunter.io"
    error: Optional[str] = None

    @property
    def decision_makers(self) -> list[HunterContact]:
        """구매결정권자만 필터링."""
        dm = [e for e in self.emails if e.is_decision_maker]
        return dm if dm else self.emails  # DM 없으면 전체 반환

    @property
    def best_contact(self) -> Optional[HunterContact]:
        """신뢰도 가장 높은 연락처."""
        if not self.emails:
            return None
        return max(self.emails, key=lambda e: e.confidence)


@dataclass
class HunterEmailVerifyResult:
    """Hunter.io 이메일 검증 결과."""
    email: str
    result: str          # "deliverable" / "undeliverable" / "risky" / "unknown"
    score: int = 0       # 0~100
    regexp: bool = False
    gibberish: bool = False
    disposable: bool = False
    webmail: bool = False
    mx_records: bool = False
    smtp_server: bool = False
    smtp_check: bool = False
    accept_all: bool = False
    block: bool = False
    sources: list[dict] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.result == "deliverable" and not self.block

    @property
    def confidence_label(self) -> str:
        if self.score >= 80:
            return "HIGH"
        elif self.score >= 50:
            return "MEDIUM"
        else:
            return "LOW"


# ---------------------------------------------------------------------------
# Hunter.io 클라이언트
# ---------------------------------------------------------------------------

class HunterClient:
    """
    Hunter.io API v2 클라이언트.

    실제 작동 확인 완료 (2026-03-18):
    - domain_search("wangfoodusa.com") → 10명 이메일 즉시 확보
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HUNTER_IO_API_KEY", "")
        self._available = bool(self.api_key)

    # ------------------------------------------------------------------
    # 도메인 검색 (핵심 기능)
    # ------------------------------------------------------------------

    async def domain_search(
        self,
        domain: str,
        company: str = "",
        limit: int = 10,
        department: str = "",          # "management" | "sales" | "purchase" | etc.
    ) -> HunterDomainResult:
        """
        특정 도메인의 이메일 주소 목록을 수집한다.

        Args:
            domain: 회사 도메인 (예: "wangfoodusa.com")
            company: 회사명 (도메인 없을 때 대체)
            limit: 최대 결과 수 (기본 10)
            department: 특정 부서 필터 (빈값 = 전부)

        Returns:
            HunterDomainResult
        """
        if not self._available:
            logger.warning("Hunter.io API key not set. Skipping domain_search.")
            return HunterDomainResult(
                domain=domain,
                error="API 키 미설정 — 환경변수 HUNTER_IO_API_KEY 확인",
            )

        params: dict = {
            "domain": domain,
            "limit": limit,
            "api_key": self.api_key,
        }
        if department:
            params["department"] = department

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{HUNTER_API_BASE}/domain-search",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})

            emails = []
            for item in data.get("emails", []):
                emails.append(HunterContact(
                    value=item.get("value", ""),
                    type=item.get("type", "generic"),
                    confidence=item.get("confidence", 0),
                    first_name=item.get("first_name") or "",
                    last_name=item.get("last_name") or "",
                    position=item.get("position") or "",
                    linkedin=item.get("linkedin") or "",
                    phone_number=item.get("phone_number") or "",
                    department=item.get("department") or "",
                ))

            return HunterDomainResult(
                domain=domain,
                organization=data.get("organization", ""),
                emails=emails,
                total_emails=data.get("meta", {}).get("total", len(emails)),
            )

        except httpx.HTTPStatusError as e:
            logger.error("Hunter.io HTTP error: %s", e)
            return HunterDomainResult(domain=domain, error=f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.error("Hunter.io error: %s", e)
            return HunterDomainResult(domain=domain, error=str(e))

    # ------------------------------------------------------------------
    # 이메일 검증
    # ------------------------------------------------------------------

    async def verify_email(self, email: str) -> HunterEmailVerifyResult:
        """
        단일 이메일 주소의 유효성을 검증한다.

        deliverable score 80+ → 발송 안전
        """
        if not self._available:
            return HunterEmailVerifyResult(
                email=email, result="unknown", score=0
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{HUNTER_API_BASE}/email-verifier",
                    params={"email": email, "api_key": self.api_key},
                )
                resp.raise_for_status()
                d = resp.json().get("data", {})

            return HunterEmailVerifyResult(
                email=email,
                result=d.get("result", "unknown"),
                score=d.get("score", 0),
                regexp=d.get("regexp", False),
                gibberish=d.get("gibberish", False),
                disposable=d.get("disposable", False),
                webmail=d.get("webmail", False),
                mx_records=d.get("mx_records", False),
                smtp_server=d.get("smtp_server", False),
                smtp_check=d.get("smtp_check", False),
                accept_all=d.get("accept_all", False),
                block=d.get("block", False),
                sources=d.get("sources", []),
            )

        except Exception as e:
            logger.error("Hunter.io verify error: %s", e)
            return HunterEmailVerifyResult(email=email, result="unknown", score=0)

    # ------------------------------------------------------------------
    # 이메일 찾기 (이름 + 도메인)
    # ------------------------------------------------------------------

    async def find_email(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        company: str = "",
    ) -> Optional[HunterContact]:
        """
        이름과 도메인으로 이메일 주소를 탐색한다.

        Args:
            first_name: 이름
            last_name: 성
            domain: 회사 도메인

        Returns:
            HunterContact 또는 None
        """
        if not self._available:
            return None

        try:
            params: dict = {
                "first_name": first_name,
                "last_name": last_name,
                "domain": domain,
                "api_key": self.api_key,
            }
            if company:
                params["company"] = company

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{HUNTER_API_BASE}/email-finder",
                    params=params,
                )
                resp.raise_for_status()
                d = resp.json().get("data", {})

            email = d.get("email")
            if not email:
                return None

            return HunterContact(
                value=email,
                confidence=d.get("score", 0),
                first_name=first_name,
                last_name=last_name,
            )

        except Exception as e:
            logger.error("Hunter.io find_email error: %s", e)
            return None

    @property
    def is_available(self) -> bool:
        return self._available
