"""Layer 2 — 대금 지급 검증 (Credit & Payment Risk)
데이터: Coface, D&B, K-SURE, 무역사기 DB
로직:
  - 기업명 + 국가 → 신용등급 조회 (6단계: A/B/C/D/E/X)
  - PASS 기준: A·B·C 등급 (D·E·X만 차단)
  - C등급은 통과하되 결제조건 가이드 제공
  - 블랙리스트 · 제재국 즉시 차단

【적정 기준 근거 — 중소기업 수출 바이어 특성】
  A (3~5%)  : Very low risk  → T/T 60일 후결제 가능
  B (15~20%): Low risk       → T/T 30~60일
  C (40~45%): Medium risk    → 개도국 바이어 대다수 해당. K-SURE 단기수출보험 가입 가능
                               L/C at sight 또는 T/T 선금30%+잔금 권장
  ──────── PASS/FAIL 차단선 ────────────────────────────────────────
  D (25~30%): High risk      → K-SURE 인수 거절. 연체·채무불이행 이력. FAIL
  E  (5~8%): Very high risk  → FAIL
  X  (5~8%): 부도/제재/조회불가 → FAIL

목표: D·E·X 등급 사기·부실 바이어 사전 차단
"""
import os
import asyncio
import httpx
from typing import Optional
from pydantic import BaseModel
from enum import Enum


# ── 스키마 ────────────────────────────────────────────────────────────────
class CreditGrade(str, Enum):
    A = "A"        # Very low risk — T/T 후불 가능
    B = "B"        # Low risk — T/T 30~60일
    C = "C"        # Medium risk — L/C or T/T 선금30% 권장 (개도국 대다수)
    D = "D"        # High risk — K-SURE 인수 거절. FAIL
    E = "E"        # Very high risk — FAIL
    X = "X"        # 부도/제재/조회불가 — FAIL
    UNKNOWN = "UNKNOWN"


class CreditSource(str, Enum):
    COFACE = "Coface"
    DNB = "D&B"
    KSURE = "K-SURE"
    INTERNAL = "Internal DB"
    MOCK = "Mock (API 미연동)"


class PaymentRiskLevel(str, Enum):
    LOW = "LOW"              # A·B 등급
    MEDIUM = "MEDIUM"        # C 등급 (조건부 통과)
    HIGH = "HIGH"            # D 등급
    BLACKLIST = "BLACKLIST"  # E·X / 제재국 / 블랙리스트


# ── 등급별 결제 조건 가이드 ──────────────────────────────────────────────
PAYMENT_GUIDE = {
    CreditGrade.A: {
        "risk": PaymentRiskLevel.LOW,
        "pass": True,
        "label": "최우량",
        "payment_terms": "T/T 60일 후결제",
        "ksure_needed": False,
        "reason": "✅ A등급 (최우량) — T/T 60일 후결제 가능",
    },
    CreditGrade.B: {
        "risk": PaymentRiskLevel.LOW,
        "pass": True,
        "label": "우량",
        "payment_terms": "T/T 30~60일",
        "ksure_needed": False,
        "reason": "✅ B등급 (우량) — T/T 30~60일 가능",
    },
    CreditGrade.C: {
        "risk": PaymentRiskLevel.MEDIUM,
        "pass": True,                    # ← PASS (개도국 대다수 C등급)
        "label": "보통",
        "payment_terms": "L/C at sight 또는 T/T 선금30%+잔금",
        "ksure_needed": True,            # K-SURE 단기수출보험 권장
        "reason": "⚠️ C등급 (보통) — 통과. 결제조건 주의: L/C at sight 또는 T/T 선금30%+잔금 권장. K-SURE 단기수출보험 가입 권고",
    },
    CreditGrade.D: {
        "risk": PaymentRiskLevel.HIGH,
        "pass": False,                   # ← FAIL (K-SURE 인수 거절 등급)
        "label": "위험",
        "payment_terms": "거래 불가",
        "ksure_needed": False,
        "reason": "⛔ D등급 (위험) — 차단. K-SURE 인수 거절 등급. 연체·채무불이행 이력 가능성 높음",
    },
    CreditGrade.E: {
        "risk": PaymentRiskLevel.BLACKLIST,
        "pass": False,
        "label": "매우 위험",
        "payment_terms": "거래 불가",
        "ksure_needed": False,
        "reason": "🚫 E등급 (매우 위험) — 차단",
    },
    CreditGrade.X: {
        "risk": PaymentRiskLevel.BLACKLIST,
        "pass": False,
        "label": "부도/조회불가",
        "payment_terms": "거래 불가",
        "ksure_needed": False,
        "reason": "🚫 X등급 (부도/조회불가) — 차단",
    },
    CreditGrade.UNKNOWN: {
        "risk": PaymentRiskLevel.MEDIUM,
        "pass": True,                    # 조회 불가 ≠ 부도. 일단 통과 + 주의 표시
        "label": "조회 불가",
        "payment_terms": "L/C at sight 권장",
        "ksure_needed": True,
        "reason": "⚠️ 신용정보 조회 불가 — 통과. L/C at sight 권장. K-SURE 가입 후 거래 권고",
    },
}


class CreditVerificationResult(BaseModel):
    company_name: str
    country: str
    credit_grade: CreditGrade
    credit_grade_label: str              # "최우량" | "우량" | "보통" | "위험" | "매우 위험" | "부도"
    credit_score: Optional[int]         # 0~100
    payment_risk: PaymentRiskLevel
    recommended_payment_terms: str      # 결제 조건 가이드
    ksure_insurance_recommended: bool   # K-SURE 가입 권장 여부
    is_blacklisted: bool
    bankruptcy_history: bool
    fraud_flag: bool
    ksure_eligible: bool                # K-SURE 가입 가능 여부 (국가 기준)
    source: CreditSource
    pass_layer2: bool                   # D·E·X → False
    reason: str


# ── 무역사기 블랙리스트 ───────────────────────────────────────────────────
FRAUD_BLACKLIST = {
    "Công ty CP Nhập Khẩu Sài Gòn": {"grade": CreditGrade.X, "reason": "KOTRA 무역사기 이력 등록"},
    "phantom": {"grade": CreditGrade.X, "reason": "유령 법인"},
    "ghost company": {"grade": CreditGrade.X, "reason": "실체 없는 법인"},
}

# 국가별 기본 리스크 프로필 (Coface Country Risk 2025 기준)
COUNTRY_RISK = {
    # 아시아 주요국
    "VN": {"country_grade": "B", "ksure": True},   # Coface B, K-SURE 가입 가능
    "TH": {"country_grade": "B", "ksure": True},
    "ID": {"country_grade": "C", "ksure": True},   # 인도네시아
    "PH": {"country_grade": "B", "ksure": True},
    "MY": {"country_grade": "A", "ksure": True},
    "SG": {"country_grade": "A", "ksure": True},
    "IN": {"country_grade": "C", "ksure": True},   # 인도
    "BD": {"country_grade": "C", "ksure": True},   # 방글라데시
    # 선진국
    "US": {"country_grade": "A", "ksure": True},
    "DE": {"country_grade": "A", "ksure": True},
    "JP": {"country_grade": "A", "ksure": True},
    "AU": {"country_grade": "A", "ksure": True},
    "GB": {"country_grade": "A", "ksure": True},
    # 중위험
    "CN": {"country_grade": "C", "ksure": True},
    "BR": {"country_grade": "C", "ksure": True},
    "MX": {"country_grade": "C", "ksure": True},
    "TR": {"country_grade": "C", "ksure": True},
    # 고위험 (K-SURE 인수 제한)
    "NG": {"country_grade": "D", "ksure": False},
    "PK": {"country_grade": "D", "ksure": True},   # 파키스탄 (주의)
    "EG": {"country_grade": "C", "ksure": True},
    # 제재국 (거래 금지)
    "IR": {"country_grade": "X", "ksure": False, "sanctioned": True},
    "KP": {"country_grade": "X", "ksure": False, "sanctioned": True},
    "RU": {"country_grade": "X", "ksure": False, "sanctioned": True},
    "BY": {"country_grade": "X", "ksure": False, "sanctioned": True},
    "SY": {"country_grade": "X", "ksure": False, "sanctioned": True},
}

# 기업명 키워드 → 신뢰도 보정
COMPANY_TRUST_KEYWORDS = {
    "high": ["JSC", "Corp", "Group", "International", "Holdings", "Co., Ltd", "Joint Stock"],
    "medium": ["TNHH", "Trading", "Import", "Distribution", "Co.", "LLC", "Ltd"],
    "low": ["Individual", "Personal", "Small", "Micro"],
}


def _estimate_credit_from_activity(
    company_name: str,
    trade_value_usd: float,
    shipment_count: int,
    country: str,
) -> tuple[CreditGrade, int]:
    """
    활동 데이터 기반 신용등급 추정 (Coface API 미연동 시)

    개도국 중소 바이어 현실 반영:
    - 실거래 중인 바이어 대부분 C 이상
    - 거래량·선적 빈도가 높을수록 B·A
    - 극단적으로 소규모이거나 의심스러울 때만 D
    """
    # 거래 규모 기반 기본 점수
    if trade_value_usd >= 500_000:
        base = 85      # A 범위
    elif trade_value_usd >= 200_000:
        base = 72      # B 범위
    elif trade_value_usd >= 80_000:
        base = 60      # C 상단
    elif trade_value_usd >= 30_000:
        base = 52      # C 중단 (개도국 중소 바이어 핵심 구간)
    elif trade_value_usd >= 10_000:
        base = 44      # C 하단
    else:
        base = 32      # D 범위 (거래 거의 없음)

    # 선적 빈도 보정
    freq_bonus = min(shipment_count * 1.5, 18)
    score = min(int(base + freq_bonus), 100)

    # 기업명 키워드 보정
    name_lower = company_name.lower()
    if any(k.lower() in name_lower for k in COMPANY_TRUST_KEYWORDS["high"]):
        score = min(score + 8, 100)
    elif any(k.lower() in name_lower for k in COMPANY_TRUST_KEYWORDS["low"]):
        score = max(score - 12, 0)

    # 국가 리스크 반영 (고위험국 -10점)
    country_info = COUNTRY_RISK.get(country, {})
    if country_info.get("country_grade") in ("D", "X"):
        score = max(score - 15, 0)
    elif country_info.get("country_grade") == "C":
        score = max(score - 5, 0)

    # 등급 결정
    # ※ 개도국 활성 바이어 현실: C가 가장 많고, B가 그 다음
    if score >= 78:
        grade = CreditGrade.A
    elif score >= 62:
        grade = CreditGrade.B
    elif score >= 42:
        grade = CreditGrade.C     # ← 실거래 중인 개도국 중소 바이어 대다수
    elif score >= 28:
        grade = CreditGrade.D
    else:
        grade = CreditGrade.E

    return grade, score


async def fetch_coface_credit(company: str, country: str) -> Optional[dict]:
    """Coface API 신용등급 조회"""
    api_key = os.getenv("COFACE_API_KEY", "")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://api.coface.com/v2/monitorings",
                json={"name": company, "country": country, "activityCode": ""},
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "grade": data.get("debtorRisk", {}).get("rate", "C"),
                    "score": data.get("debtorRisk", {}).get("score", 50),
                    "bankruptcy": data.get("events", {}).get("hasBankruptcy", False),
                }
    except Exception:
        pass
    return None


async def fetch_ksure_eligibility(country: str) -> bool:
    """K-SURE 무역보험 가입 가능 여부 (국가 프로필 기반)"""
    return COUNTRY_RISK.get(country, {}).get("ksure", True)


def _check_fraud_blacklist(company: str) -> Optional[dict]:
    if company in FRAUD_BLACKLIST:
        return FRAUD_BLACKLIST[company]
    company_lower = company.lower()
    for key, val in FRAUD_BLACKLIST.items():
        if key.lower() in company_lower:
            return val
    return None


class CreditVerifier:
    """
    Layer 2: 대금 지급 검증
    PASS 기준: A·B·C 등급 (D·E·X만 차단)
    """

    async def verify(
        self,
        company_name: str,
        country: str,
        trade_value_usd: float = 0,
        shipment_count: int = 0,
    ) -> CreditVerificationResult:

        # ① 블랙리스트 즉시 차단
        fraud = _check_fraud_blacklist(company_name)
        if fraud:
            g = fraud["grade"]
            guide = PAYMENT_GUIDE[g]
            return CreditVerificationResult(
                company_name=company_name,
                country=country,
                credit_grade=g,
                credit_grade_label=guide["label"],
                credit_score=0,
                payment_risk=PaymentRiskLevel.BLACKLIST,
                recommended_payment_terms="거래 불가",
                ksure_insurance_recommended=False,
                is_blacklisted=True,
                bankruptcy_history=True,
                fraud_flag=True,
                ksure_eligible=False,
                source=CreditSource.INTERNAL,
                pass_layer2=False,
                reason=f"🚫 무역사기 블랙리스트: {fraud['reason']}",
            )

        # ② 제재국 즉시 차단
        country_info = COUNTRY_RISK.get(country, {})
        if country_info.get("sanctioned"):
            return CreditVerificationResult(
                company_name=company_name,
                country=country,
                credit_grade=CreditGrade.X,
                credit_grade_label="제재국",
                credit_score=0,
                payment_risk=PaymentRiskLevel.BLACKLIST,
                recommended_payment_terms="거래 불가",
                ksure_insurance_recommended=False,
                is_blacklisted=True,
                bankruptcy_history=False,
                fraud_flag=False,
                ksure_eligible=False,
                source=CreditSource.INTERNAL,
                pass_layer2=False,
                reason="🚫 OFAC/UN 제재국 — 거래 법적 금지",
            )

        # ③ Coface API 시도 → 실패 시 활동 데이터 추정
        coface_data = await fetch_coface_credit(company_name, country)
        bankruptcy = False

        if coface_data:
            try:
                grade = CreditGrade(coface_data["grade"])
            except ValueError:
                grade = CreditGrade.C
            score = coface_data.get("score", 50)
            bankruptcy = coface_data.get("bankruptcy", False)
            source = CreditSource.COFACE
        else:
            grade, score = _estimate_credit_from_activity(
                company_name, trade_value_usd, shipment_count, country
            )
            source = CreditSource.MOCK

        # 부도 이력 → 강제 X
        if bankruptcy:
            grade = CreditGrade.X

        # ④ 등급별 가이드 적용
        guide = PAYMENT_GUIDE.get(grade, PAYMENT_GUIDE[CreditGrade.UNKNOWN])
        ksure_eligible = await fetch_ksure_eligibility(country)

        return CreditVerificationResult(
            company_name=company_name,
            country=country,
            credit_grade=grade,
            credit_grade_label=guide["label"],
            credit_score=score,
            payment_risk=guide["risk"],
            recommended_payment_terms=guide["payment_terms"],
            ksure_insurance_recommended=guide["ksure_needed"],
            is_blacklisted=False,
            bankruptcy_history=bankruptcy,
            fraud_flag=False,
            ksure_eligible=ksure_eligible,
            source=source,
            pass_layer2=guide["pass"],
            reason=guide["reason"],
        )

    async def verify_batch(self, buyers: list) -> list[CreditVerificationResult]:
        tasks = [
            self.verify(
                b.company_name,
                b.country,
                b.total_trade_value_usd,
                b.shipment_count,
            )
            for b in buyers
        ]
        return await asyncio.gather(*tasks)
