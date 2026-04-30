"""지원 국가 목록 정의
현재 DB(Seed + COUNTRY_RISK) 기준 사용 가능한 국가와 데이터 현황
"""
from pydantic import BaseModel


class CountryInfo(BaseModel):
    code: str           # ISO 2자리 코드
    name_ko: str        # 국가명 (국문)
    name_en: str        # 국가명 (영문)
    region: str         # 지역
    data_quality: str   # "Full" | "Partial" | "Limited"
    hs_codes_available: list[str]   # 이 나라에서 조회 가능한 HS 코드 목록
    notes: str          # 비고 (결제리스크, 특이사항 등)


class SupportedCountriesResponse(BaseModel):
    total: int
    countries: list[CountryInfo]
    last_updated: str


# ── 지원 국가 마스터 ─────────────────────────────────────────────────────────
SUPPORTED_COUNTRIES: list[CountryInfo] = [
    # ─── 아시아 ────────────────────────────────────────────────────────
    CountryInfo(
        code="VN", name_ko="베트남", name_en="Vietnam",
        region="동남아시아",
        data_quality="Full",
        hs_codes_available=["330499", "870830", "210690", "330410", "330420", "330491", "330510", "330590", "340111"],
        notes="화장품·자동차부품 Seed 데이터 풍부. K-SURE 가입 가능. 신용등급 B",
    ),
    CountryInfo(
        code="TH", name_ko="태국", name_en="Thailand",
        region="동남아시아",
        data_quality="Full",
        hs_codes_available=["330499", "210690", "330410", "330420", "330510", "330590"],
        notes="화장품·건기식 Seed 데이터 보유. K-SURE 가입 가능. 신용등급 B",
    ),
    CountryInfo(
        code="US", name_ko="미국", name_en="United States",
        region="북미",
        data_quality="Full",
        hs_codes_available=["330499", "210690", "330410", "330420", "330491", "330300", "300490", "870899"],
        notes="최대 수입국. 신용등급 A. T/T 후불 가능. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="JP", name_ko="일본", name_en="Japan",
        region="동아시아",
        data_quality="Partial",
        hs_codes_available=["330499", "210690", "330300"],
        notes="고품질 시장. 신용등급 A. 통관 기준 엄격. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="DE", name_ko="독일", name_en="Germany",
        region="유럽",
        data_quality="Partial",
        hs_codes_available=["330499", "330300", "300490", "870899"],
        notes="유럽 거점. 신용등급 A. CE·CPNP 인증 필요. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="AU", name_ko="호주", name_en="Australia",
        region="오세아니아",
        data_quality="Partial",
        hs_codes_available=["330499"],
        notes="K-뷰티 성장 시장. 신용등급 A. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="MY", name_ko="말레이시아", name_en="Malaysia",
        region="동남아시아",
        data_quality="Partial",
        hs_codes_available=["330499", "330410"],
        notes="Halal 시장 접근 유리. 신용등급 A. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="SG", name_ko="싱가포르", name_en="Singapore",
        region="동남아시아",
        data_quality="Partial",
        hs_codes_available=["330499", "330300"],
        notes="동남아 유통 허브. 신용등급 A. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="ID", name_ko="인도네시아", name_en="Indonesia",
        region="동남아시아",
        data_quality="Partial",
        hs_codes_available=["330499"],
        notes="세계 4위 인구. 신용등급 C. Halal 인증 필요. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="PH", name_ko="필리핀", name_en="Philippines",
        region="동남아시아",
        data_quality="Partial",
        hs_codes_available=["330499"],
        notes="K-뷰티 인기 높음. 신용등급 B. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="IN", name_ko="인도", name_en="India",
        region="남아시아",
        data_quality="Limited",
        hs_codes_available=["330499", "210690"],
        notes="고성장 시장. 신용등급 C. 통관 복잡. K-SURE 가입 가능",
    ),
    CountryInfo(
        code="CN", name_ko="중국", name_en="China",
        region="동아시아",
        data_quality="Limited",
        hs_codes_available=["330499"],
        notes="NMPA 등록 필수. 신용등급 C. K-SURE 가입 가능 (주의)",
    ),
]

# 제재국 — 시스템에서 자동 차단 (선택 불가)
SANCTIONED_COUNTRIES = ["IR", "KP", "RU", "BY", "SY"]


def get_supported_countries() -> SupportedCountriesResponse:
    return SupportedCountriesResponse(
        total=len(SUPPORTED_COUNTRIES),
        countries=SUPPORTED_COUNTRIES,
        last_updated="2026-03-18",
    )


def get_country_by_hs(hs_code: str) -> list[CountryInfo]:
    """특정 HS 코드 조회 가능 국가만 필터링"""
    return [c for c in SUPPORTED_COUNTRIES if hs_code in c.hs_codes_available]
