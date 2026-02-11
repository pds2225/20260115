"""
제재국/규제국 필터링 모듈.

SIMULATION_SPEC.md 2장 기반:
  - blocked: 거래 불가 (북한, 이란, 시리아, 쿠바)
  - restricted: 경고 + 감점 (러시아, 벨라루스, 미얀마, 베네수엘라)
  - normal: 정상 처리
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SanctionStatus(str, Enum):
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    NORMAL = "normal"


# ---------------------------------------------------------------------------
# 제재국/제한국 목록 (ISO3 코드)
# ---------------------------------------------------------------------------

BLOCKED_COUNTRIES: dict[str, str] = {
    "PRK": "North Korea",
    "IRN": "Iran",
    "SYR": "Syria",
    "CUB": "Cuba",
}

RESTRICTED_COUNTRIES: dict[str, str] = {
    "RUS": "Russia",
    "BLR": "Belarus",
    "MMR": "Myanmar",
    "VEN": "Venezuela",
}

# ISO2 → ISO3 매핑 (호환성용)
ISO2_TO_ISO3: dict[str, str] = {
    "KP": "PRK",
    "IR": "IRN",
    "SY": "SYR",
    "CU": "CUB",
    "RU": "RUS",
    "BY": "BLR",
    "MM": "MMR",
    "VE": "VEN",
}

# 제한국 점수 감점
RESTRICTED_PENALTY = -10.0


@dataclass
class ComplianceResult:
    """제재/규제 검사 결과."""

    country_iso3: str
    status: SanctionStatus
    warning: Optional[str] = None
    penalty: float = 0.0
    legal_notice: Optional[str] = None

    @property
    def is_blocked(self) -> bool:
        return self.status == SanctionStatus.BLOCKED

    @property
    def is_restricted(self) -> bool:
        return self.status == SanctionStatus.RESTRICTED

    def to_dict(self) -> dict:
        result = {
            "country_iso3": self.country_iso3,
            "status": self.status.value,
        }
        if self.warning:
            result["warning"] = self.warning
        if self.penalty != 0.0:
            result["penalty"] = self.penalty
        if self.legal_notice:
            result["legal_notice"] = self.legal_notice
        return result


def check_compliance(country_code: str) -> ComplianceResult:
    """
    국가 코드에 대한 제재/규제 검사를 수행한다.

    Args:
        country_code: ISO3 또는 ISO2 국가 코드 (예: "PRK", "KP")

    Returns:
        ComplianceResult
    """
    code = country_code.upper().strip()

    # ISO2 → ISO3 변환
    if len(code) == 2 and code in ISO2_TO_ISO3:
        code = ISO2_TO_ISO3[code]

    if code in BLOCKED_COUNTRIES:
        name = BLOCKED_COUNTRIES[code]
        return ComplianceResult(
            country_iso3=code,
            status=SanctionStatus.BLOCKED,
            warning=f"거래 불가: {name}({code})은(는) 수출 제재 대상국입니다.",
            legal_notice=(
                "해당 국가로의 수출은 대한민국 대외무역법 및 "
                "국제 제재 규정에 따라 금지됩니다."
            ),
        )

    if code in RESTRICTED_COUNTRIES:
        name = RESTRICTED_COUNTRIES[code]
        return ComplianceResult(
            country_iso3=code,
            status=SanctionStatus.RESTRICTED,
            warning=f"수출 허가 필요: {name}({code})은(는) 수출 제한국입니다.",
            penalty=RESTRICTED_PENALTY,
        )

    return ComplianceResult(
        country_iso3=code,
        status=SanctionStatus.NORMAL,
    )


def filter_blocked_countries(country_codes: list[str]) -> tuple[list[str], list[str]]:
    """
    국가 코드 목록에서 blocked 국가를 제거한다.

    Returns:
        (통과된 국가 목록, 차단된 국가 목록)
    """
    passed = []
    blocked = []
    for code in country_codes:
        result = check_compliance(code)
        if result.is_blocked:
            blocked.append(code)
        else:
            passed.append(code)
    return passed, blocked
