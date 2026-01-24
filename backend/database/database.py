"""In-memory database stub.

This module contains simple lists of dictionaries representing seller and
buyer profiles. The intent is to mimic a datastore without involving
external dependencies. In a real system these would be loaded from a
persistent data store and kept current via CRUD operations.

Updated: 50 buyer profiles with diverse countries, industries, and trade requirements.
"""

from typing import List, Dict


# =============================================================================
# 산업-HS코드 매핑 테이블
# =============================================================================
INDUSTRY_HS_MAPPING = {
    # 화장품/뷰티 (Cosmetics/Beauty)
    "화장품": {
        "hs_codes": ["3304", "330410", "330420", "330430", "330491", "330499"],
        "en": "Cosmetics",
        "keywords": ["화장품", "스킨케어", "메이크업", "뷰티", "cosmetic", "skincare", "beauty"],
    },
    # 의약품 (Pharmaceuticals)
    "의약품": {
        "hs_codes": ["3004", "300410", "300420", "300431", "300432", "300439", "300440", "300450", "300490"],
        "en": "Pharmaceuticals",
        "keywords": ["의약품", "제약", "약품", "pharmaceutical", "medicine", "drug"],
    },
    # 식품/건강기능식품 (Food/Health Supplements)
    "식품": {
        "hs_codes": ["2106", "210610", "210690", "1901", "190190", "2202"],
        "en": "Food & Supplements",
        "keywords": ["식품", "건강기능", "보충제", "food", "supplement", "nutrition"],
    },
    # 전자기기 (Electronics)
    "전자기기": {
        "hs_codes": ["8471", "8517", "8518", "8519", "8521", "8525", "8528"],
        "en": "Electronics",
        "keywords": ["전자", "가전", "IT", "electronic", "device", "appliance"],
    },
    # 섬유/의류 (Textiles/Apparel)
    "섬유": {
        "hs_codes": ["6109", "6110", "6201", "6202", "6203", "6204", "6205", "6206"],
        "en": "Textiles & Apparel",
        "keywords": ["섬유", "의류", "패션", "textile", "apparel", "fashion", "clothing"],
    },
    # 자동차부품 (Auto Parts)
    "자동차부품": {
        "hs_codes": ["8708", "870810", "870821", "870829", "870830", "870840"],
        "en": "Auto Parts",
        "keywords": ["자동차", "부품", "automotive", "auto parts", "vehicle"],
    },
    # 기계/장비 (Machinery)
    "기계": {
        "hs_codes": ["8421", "8422", "8428", "8429", "8430", "8479"],
        "en": "Machinery & Equipment",
        "keywords": ["기계", "장비", "machinery", "equipment", "industrial"],
    },
    # 플라스틱/고무 (Plastics/Rubber)
    "플라스틱": {
        "hs_codes": ["3901", "3902", "3903", "3904", "3917", "3923", "3926"],
        "en": "Plastics & Rubber",
        "keywords": ["플라스틱", "고무", "plastic", "rubber", "polymer"],
    },
    # 철강/금속 (Steel/Metals)
    "철강": {
        "hs_codes": ["7208", "7209", "7210", "7219", "7304", "7306"],
        "en": "Steel & Metals",
        "keywords": ["철강", "금속", "스틸", "steel", "metal", "iron"],
    },
    # 농산물 (Agricultural Products)
    "농산물": {
        "hs_codes": ["0702", "0709", "0710", "0712", "0804", "0805", "0810"],
        "en": "Agricultural Products",
        "keywords": ["농산물", "농업", "agriculture", "farming", "produce"],
    },
}


def get_industry_by_hs_code(hs_code: str) -> Dict:
    """HS코드로 산업 정보 조회"""
    hs_4digit = hs_code[:4]
    for industry_name, info in INDUSTRY_HS_MAPPING.items():
        if any(hs_4digit.startswith(code[:4]) for code in info["hs_codes"]):
            return {
                "industry_kr": industry_name,
                "industry_en": info["en"],
                "keywords": info["keywords"],
            }
    return {"industry_kr": "기타", "industry_en": "Others", "keywords": []}


def get_hs_codes_by_industry(industry: str) -> List[str]:
    """산업명으로 관련 HS코드 조회"""
    for industry_name, info in INDUSTRY_HS_MAPPING.items():
        if industry.lower() in industry_name.lower() or industry.lower() in info["en"].lower():
            return info["hs_codes"]
        if any(kw.lower() in industry.lower() for kw in info["keywords"]):
            return info["hs_codes"]
    return []


# =============================================================================
# 무역사기 유형별 가중치 테이블
# =============================================================================
FRAUD_TYPE_WEIGHTS = {
    # 가장 빈번하고 피해 규모가 큰 유형
    "이메일해킹": {
        "base_penalty": -20,
        "description": "계정 탈취 후 결제 계좌 변경 유도",
        "frequency": "매우 높음",
        "avg_damage_usd": 150000,
    },
    # 금전적 피해 직접 유발
    "금품사취": {
        "base_penalty": -18,
        "description": "선금 요구 후 잠적, 품질 불량 등",
        "frequency": "높음",
        "avg_damage_usd": 50000,
    },
    # 허위 물류 정보 제공
    "선적서류위조": {
        "base_penalty": -15,
        "description": "가짜 B/L, 허위 선적 통보",
        "frequency": "중간",
        "avg_damage_usd": 30000,
    },
    # 품질/규격 불일치
    "품질사기": {
        "base_penalty": -12,
        "description": "샘플과 다른 제품 납품, 규격 미달",
        "frequency": "중간",
        "avg_damage_usd": 20000,
    },
    # 회사 사칭
    "기업사칭": {
        "base_penalty": -15,
        "description": "유명 기업명 도용, 가짜 웹사이트",
        "frequency": "높음",
        "avg_damage_usd": 40000,
    },
    # 인증서 위조
    "인증서위조": {
        "base_penalty": -10,
        "description": "가짜 인증서, 허위 자격 주장",
        "frequency": "낮음",
        "avg_damage_usd": 15000,
    },
    # 물류 관련
    "운송사기": {
        "base_penalty": -12,
        "description": "가짜 물류회사, 추가 비용 요구",
        "frequency": "중간",
        "avg_damage_usd": 25000,
    },
    # 기타
    "기타": {
        "base_penalty": -8,
        "description": "분류되지 않은 기타 사기 유형",
        "frequency": "낮음",
        "avg_damage_usd": 10000,
    },
}


def get_fraud_penalty(fraud_type: str, damage_amount: float = 0) -> int:
    """무역사기 유형과 피해금액 기반 페널티 계산"""
    fraud_info = FRAUD_TYPE_WEIGHTS.get(fraud_type, FRAUD_TYPE_WEIGHTS["기타"])
    base_penalty = fraud_info["base_penalty"]
    
    # 피해금액 기반 추가 페널티 (10만 USD 이상 시 추가 -5)
    damage_penalty = -5 if damage_amount >= 100000 else 0
    
    return base_penalty + damage_penalty


def get_country_fraud_summary(fraud_cases: List[Dict]) -> Dict:
    """국가별 무역사기 요약 통계"""
    if not fraud_cases:
        return {
            "total_cases": 0,
            "total_penalty": 0,
            "risk_level": "SAFE",
            "fraud_type_distribution": {},
        }
    
    fraud_type_counts = {}
    total_penalty = 0
    
    for case in fraud_cases:
        ft = case.get("fraudType", case.get("fraudTypNm", "기타"))
        damage = float(case.get("dmgeAmt", 0) or 0)
        
        fraud_type_counts[ft] = fraud_type_counts.get(ft, 0) + 1
        total_penalty += abs(get_fraud_penalty(ft, damage))
    
    total_cases = len(fraud_cases)
    
    # 리스크 레벨 결정
    if total_penalty >= 100 or total_cases >= 20:
        risk_level = "HIGH"
    elif total_penalty >= 50 or total_cases >= 10:
        risk_level = "MEDIUM"
    elif total_penalty >= 20 or total_cases >= 5:
        risk_level = "LOW"
    else:
        risk_level = "SAFE"
    
    return {
        "total_cases": total_cases,
        "total_penalty": min(total_penalty, 25),  # 최대 -25 캡
        "risk_level": risk_level,
        "fraud_type_distribution": fraud_type_counts,
    }


# =============================================================================
# Seller Profiles (5개)
# =============================================================================
def load_seller_profiles() -> List[Dict]:
    """Return a list of example seller profiles."""
    return [
        {
            "id": "seller_001",
            "company_name": "코스메틱코리아",
            "hs_code": "330499",
            "country": "KR",
            "price_range": [5.0, 8.0],
            "moq": 1000,
            "certifications": ["FDA", "ISO"],
            "export_experience_years": 5,
            "languages": ["ko", "en"],
            "industry": "화장품",
        },
        {
            "id": "seller_002",
            "company_name": "헬스팜",
            "hs_code": "300490",
            "country": "KR",
            "price_range": [1.0, 3.0],
            "moq": 5000,
            "certifications": ["CE"],
            "export_experience_years": 3,
            "languages": ["ko", "en", "zh"],
            "industry": "의약품",
        },
        {
            "id": "seller_003",
            "company_name": "푸드테크",
            "hs_code": "210690",
            "country": "KR",
            "price_range": [2.0, 4.0],
            "moq": 2000,
            "certifications": [],
            "export_experience_years": 2,
            "languages": ["ko"],
            "industry": "식품",
        },
        {
            "id": "seller_004",
            "company_name": "K뷰티글로벌",
            "hs_code": "330499",
            "country": "KR",
            "price_range": [3.0, 6.0],
            "moq": 500,
            "certifications": ["FDA", "CE", "ISO"],
            "export_experience_years": 7,
            "languages": ["ko", "en", "jp"],
            "industry": "화장품",
        },
        {
            "id": "seller_005",
            "company_name": "바이오메드코리아",
            "hs_code": "300490",
            "country": "KR",
            "price_range": [2.0, 5.0],
            "moq": 3000,
            "certifications": ["FDA", "CE"],
            "export_experience_years": 4,
            "languages": ["ko", "en"],
            "industry": "의약품",
        },
    ]


# =============================================================================
# Buyer Profiles (50개)
# =============================================================================
def load_buyer_profiles() -> List[Dict]:
    """Return a list of 50 example buyer profiles.
    
    Profiles cover diverse:
    - Countries: US, CN, JP, VN, DE, SG, TH, ID, IN, AU, GB, FR, MY, PH, AE, CA, MX, BR, NL, IT
    - Industries: 화장품, 의약품, 식품, 전자기기, 섬유
    - HS Codes: 330499, 300490, 210690, 851712, 610910
    - Certifications: FDA, CE, ISO, HALAL, KOSHER
    - Payment Terms: LC, TT, DP, DA
    """
    return [
        # === 미국 (US) - 10개 ===
        {
            "id": "buyer_001",
            "company_name": "US Beauty Imports Inc.",
            "hs_code": "330499",
            "country": "US",
            "price_range": [6.0, 9.0],
            "moq": 1000,
            "certifications": ["FDA"],
            "import_volume_annual": 50000,
            "payment_terms": ["LC", "TT"],
            "industry": "화장품",
        },
        {
            "id": "buyer_002",
            "company_name": "American Pharma Solutions",
            "hs_code": "300490",
            "country": "US",
            "price_range": [3.0, 7.0],
            "moq": 2000,
            "certifications": ["FDA", "ISO"],
            "import_volume_annual": 80000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        {
            "id": "buyer_003",
            "company_name": "California Health Foods",
            "hs_code": "210690",
            "country": "US",
            "price_range": [2.5, 5.0],
            "moq": 1500,
            "certifications": ["FDA", "KOSHER"],
            "import_volume_annual": 40000,
            "payment_terms": ["TT"],
            "industry": "식품",
        },
        {
            "id": "buyer_004",
            "company_name": "NYC Cosmetics Wholesale",
            "hs_code": "330499",
            "country": "US",
            "price_range": [4.0, 7.0],
            "moq": 800,
            "certifications": ["FDA"],
            "import_volume_annual": 30000,
            "payment_terms": ["TT", "LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_005",
            "company_name": "Texas Medical Supply",
            "hs_code": "300490",
            "country": "US",
            "price_range": [2.0, 4.5],
            "moq": 3000,
            "certifications": ["FDA", "CE"],
            "import_volume_annual": 60000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        {
            "id": "buyer_006",
            "company_name": "Seattle Organic Supplements",
            "hs_code": "210690",
            "country": "US",
            "price_range": [3.0, 6.0],
            "moq": 1000,
            "certifications": ["FDA", "USDA"],
            "import_volume_annual": 25000,
            "payment_terms": ["TT"],
            "industry": "식품",
        },
        {
            "id": "buyer_007",
            "company_name": "Miami Beauty Distribution",
            "hs_code": "330499",
            "country": "US",
            "price_range": [5.0, 8.0],
            "moq": 500,
            "certifications": ["FDA"],
            "import_volume_annual": 20000,
            "payment_terms": ["TT", "LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_008",
            "company_name": "Chicago Wellness Corp",
            "hs_code": "210690",
            "country": "US",
            "price_range": [2.0, 4.0],
            "moq": 2000,
            "certifications": ["FDA"],
            "import_volume_annual": 35000,
            "payment_terms": ["LC"],
            "industry": "식품",
        },
        {
            "id": "buyer_009",
            "company_name": "Boston BioTech Imports",
            "hs_code": "300490",
            "country": "US",
            "price_range": [4.0, 8.0],
            "moq": 1500,
            "certifications": ["FDA", "ISO"],
            "import_volume_annual": 70000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        {
            "id": "buyer_010",
            "company_name": "LA K-Beauty House",
            "hs_code": "330499",
            "country": "US",
            "price_range": [3.0, 6.0],
            "moq": 600,
            "certifications": ["FDA"],
            "import_volume_annual": 15000,
            "payment_terms": ["TT"],
            "industry": "화장품",
        },
        
        # === 중국 (CN) - 8개 ===
        {
            "id": "buyer_011",
            "company_name": "Shanghai Beauty Trading",
            "hs_code": "330499",
            "country": "CN",
            "price_range": [3.0, 6.0],
            "moq": 3000,
            "certifications": ["NMPA"],
            "import_volume_annual": 150000,
            "payment_terms": ["LC", "TT"],
            "industry": "화장품",
        },
        {
            "id": "buyer_012",
            "company_name": "Beijing Pharma Import",
            "hs_code": "300490",
            "country": "CN",
            "price_range": [1.5, 4.0],
            "moq": 5000,
            "certifications": ["NMPA", "ISO"],
            "import_volume_annual": 200000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        {
            "id": "buyer_013",
            "company_name": "Guangzhou Food Import Co.",
            "hs_code": "210690",
            "country": "CN",
            "price_range": [2.0, 4.0],
            "moq": 2000,
            "certifications": [],
            "import_volume_annual": 100000,
            "payment_terms": ["LC", "TT", "DP"],
            "industry": "식품",
        },
        {
            "id": "buyer_014",
            "company_name": "Shenzhen K-Cosmetics",
            "hs_code": "330499",
            "country": "CN",
            "price_range": [4.0, 7.0],
            "moq": 2000,
            "certifications": ["NMPA"],
            "import_volume_annual": 80000,
            "payment_terms": ["TT"],
            "industry": "화장품",
        },
        {
            "id": "buyer_015",
            "company_name": "Hangzhou Health Supplements",
            "hs_code": "210690",
            "country": "CN",
            "price_range": [2.5, 5.0],
            "moq": 3000,
            "certifications": [],
            "import_volume_annual": 90000,
            "payment_terms": ["LC"],
            "industry": "식품",
        },
        {
            "id": "buyer_016",
            "company_name": "Chengdu Medical Trading",
            "hs_code": "300490",
            "country": "CN",
            "price_range": [2.0, 5.0],
            "moq": 4000,
            "certifications": ["NMPA"],
            "import_volume_annual": 120000,
            "payment_terms": ["LC", "TT"],
            "industry": "의약품",
        },
        {
            "id": "buyer_017",
            "company_name": "Tianjin Beauty Wholesale",
            "hs_code": "330499",
            "country": "CN",
            "price_range": [2.5, 5.0],
            "moq": 5000,
            "certifications": ["NMPA"],
            "import_volume_annual": 180000,
            "payment_terms": ["LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_018",
            "company_name": "Dalian Import Export Co.",
            "hs_code": "210690",
            "country": "CN",
            "price_range": [1.5, 3.5],
            "moq": 4000,
            "certifications": [],
            "import_volume_annual": 70000,
            "payment_terms": ["TT", "DP"],
            "industry": "식품",
        },
        
        # === 일본 (JP) - 6개 ===
        {
            "id": "buyer_019",
            "company_name": "Tokyo Cosmetics Trading",
            "hs_code": "330499",
            "country": "JP",
            "price_range": [5.0, 8.0],
            "moq": 800,
            "certifications": ["ISO"],
            "import_volume_annual": 40000,
            "payment_terms": ["LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_020",
            "company_name": "Osaka Pharma Distribution",
            "hs_code": "300490",
            "country": "JP",
            "price_range": [3.0, 6.0],
            "moq": 1500,
            "certifications": ["PMDA", "ISO"],
            "import_volume_annual": 55000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        {
            "id": "buyer_021",
            "company_name": "Nagoya Health Foods",
            "hs_code": "210690",
            "country": "JP",
            "price_range": [3.0, 5.0],
            "moq": 1000,
            "certifications": ["JAS"],
            "import_volume_annual": 30000,
            "payment_terms": ["LC", "TT"],
            "industry": "식품",
        },
        {
            "id": "buyer_022",
            "company_name": "Fukuoka Beauty Import",
            "hs_code": "330499",
            "country": "JP",
            "price_range": [4.0, 7.0],
            "moq": 600,
            "certifications": ["ISO"],
            "import_volume_annual": 25000,
            "payment_terms": ["LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_023",
            "company_name": "Yokohama Supplement Co.",
            "hs_code": "210690",
            "country": "JP",
            "price_range": [4.0, 6.0],
            "moq": 800,
            "certifications": ["JAS", "ISO"],
            "import_volume_annual": 35000,
            "payment_terms": ["LC"],
            "industry": "식품",
        },
        {
            "id": "buyer_024",
            "company_name": "Sapporo Medical Supply",
            "hs_code": "300490",
            "country": "JP",
            "price_range": [2.5, 5.0],
            "moq": 2000,
            "certifications": ["PMDA"],
            "import_volume_annual": 45000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        
        # === 베트남 (VN) - 5개 ===
        {
            "id": "buyer_025",
            "company_name": "Vietnam Health Trading",
            "hs_code": "300490",
            "country": "VN",
            "price_range": [1.5, 4.0],
            "moq": 2000,
            "certifications": ["CE"],
            "import_volume_annual": 30000,
            "payment_terms": ["TT"],
            "industry": "의약품",
        },
        {
            "id": "buyer_026",
            "company_name": "Hanoi Cosmetics Import",
            "hs_code": "330499",
            "country": "VN",
            "price_range": [2.0, 5.0],
            "moq": 1500,
            "certifications": [],
            "import_volume_annual": 25000,
            "payment_terms": ["TT", "LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_027",
            "company_name": "Ho Chi Minh Food Corp",
            "hs_code": "210690",
            "country": "VN",
            "price_range": [1.5, 3.5],
            "moq": 3000,
            "certifications": [],
            "import_volume_annual": 50000,
            "payment_terms": ["TT", "DP"],
            "industry": "식품",
        },
        {
            "id": "buyer_028",
            "company_name": "Da Nang Beauty House",
            "hs_code": "330499",
            "country": "VN",
            "price_range": [2.5, 4.5],
            "moq": 1000,
            "certifications": [],
            "import_volume_annual": 15000,
            "payment_terms": ["TT"],
            "industry": "화장품",
        },
        {
            "id": "buyer_029",
            "company_name": "Saigon Pharma Trading",
            "hs_code": "300490",
            "country": "VN",
            "price_range": [1.0, 3.0],
            "moq": 5000,
            "certifications": ["CE"],
            "import_volume_annual": 40000,
            "payment_terms": ["LC", "TT"],
            "industry": "의약품",
        },
        
        # === 독일 (DE) - 4개 ===
        {
            "id": "buyer_030",
            "company_name": "Berlin Pharma GmbH",
            "hs_code": "300490",
            "country": "DE",
            "price_range": [3.0, 6.0],
            "moq": 2500,
            "certifications": ["CE", "ISO"],
            "import_volume_annual": 60000,
            "payment_terms": ["LC", "TT"],
            "industry": "의약품",
        },
        {
            "id": "buyer_031",
            "company_name": "Munich Cosmetics Import",
            "hs_code": "330499",
            "country": "DE",
            "price_range": [5.0, 8.0],
            "moq": 1000,
            "certifications": ["CE", "ISO"],
            "import_volume_annual": 35000,
            "payment_terms": ["LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_032",
            "company_name": "Frankfurt Health Foods",
            "hs_code": "210690",
            "country": "DE",
            "price_range": [3.0, 5.5],
            "moq": 1500,
            "certifications": ["CE", "BIO"],
            "import_volume_annual": 28000,
            "payment_terms": ["LC", "TT"],
            "industry": "식품",
        },
        {
            "id": "buyer_033",
            "company_name": "Hamburg Beauty Distribution",
            "hs_code": "330499",
            "country": "DE",
            "price_range": [4.0, 7.0],
            "moq": 800,
            "certifications": ["CE"],
            "import_volume_annual": 22000,
            "payment_terms": ["TT"],
            "industry": "화장품",
        },
        
        # === 싱가포르 (SG) - 3개 ===
        {
            "id": "buyer_034",
            "company_name": "Singapore Health Solutions",
            "hs_code": "300490",
            "country": "SG",
            "price_range": [2.5, 5.0],
            "moq": 1500,
            "certifications": ["FDA", "CE"],
            "import_volume_annual": 35000,
            "payment_terms": ["TT"],
            "industry": "의약품",
        },
        {
            "id": "buyer_035",
            "company_name": "SG Beauty Wholesale",
            "hs_code": "330499",
            "country": "SG",
            "price_range": [4.0, 7.0],
            "moq": 500,
            "certifications": ["ISO"],
            "import_volume_annual": 20000,
            "payment_terms": ["TT", "LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_036",
            "company_name": "Marina Bay Supplements",
            "hs_code": "210690",
            "country": "SG",
            "price_range": [3.0, 5.0],
            "moq": 800,
            "certifications": ["HALAL"],
            "import_volume_annual": 18000,
            "payment_terms": ["TT"],
            "industry": "식품",
        },
        
        # === 태국 (TH) - 3개 ===
        {
            "id": "buyer_037",
            "company_name": "Bangkok Beauty Import",
            "hs_code": "330499",
            "country": "TH",
            "price_range": [2.0, 5.0],
            "moq": 2000,
            "certifications": ["TFDA"],
            "import_volume_annual": 45000,
            "payment_terms": ["TT", "LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_038",
            "company_name": "Phuket Health Trading",
            "hs_code": "210690",
            "country": "TH",
            "price_range": [1.5, 3.5],
            "moq": 3000,
            "certifications": ["HALAL"],
            "import_volume_annual": 35000,
            "payment_terms": ["TT"],
            "industry": "식품",
        },
        {
            "id": "buyer_039",
            "company_name": "Chiang Mai Pharma Co.",
            "hs_code": "300490",
            "country": "TH",
            "price_range": [1.5, 4.0],
            "moq": 2500,
            "certifications": ["TFDA"],
            "import_volume_annual": 30000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        
        # === 인도네시아 (ID) - 3개 ===
        {
            "id": "buyer_040",
            "company_name": "Jakarta Beauty Wholesale",
            "hs_code": "330499",
            "country": "ID",
            "price_range": [2.0, 4.5],
            "moq": 3000,
            "certifications": ["BPOM", "HALAL"],
            "import_volume_annual": 60000,
            "payment_terms": ["LC", "TT"],
            "industry": "화장품",
        },
        {
            "id": "buyer_041",
            "company_name": "Surabaya Health Foods",
            "hs_code": "210690",
            "country": "ID",
            "price_range": [1.5, 3.0],
            "moq": 5000,
            "certifications": ["HALAL", "BPOM"],
            "import_volume_annual": 80000,
            "payment_terms": ["LC"],
            "industry": "식품",
        },
        {
            "id": "buyer_042",
            "company_name": "Bali Pharma Import",
            "hs_code": "300490",
            "country": "ID",
            "price_range": [1.0, 3.5],
            "moq": 4000,
            "certifications": ["BPOM"],
            "import_volume_annual": 50000,
            "payment_terms": ["TT", "LC"],
            "industry": "의약품",
        },
        
        # === 인도 (IN) - 3개 ===
        {
            "id": "buyer_043",
            "company_name": "Mumbai Cosmetics Trading",
            "hs_code": "330499",
            "country": "IN",
            "price_range": [2.0, 4.0],
            "moq": 5000,
            "certifications": ["BIS"],
            "import_volume_annual": 100000,
            "payment_terms": ["LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_044",
            "company_name": "Delhi Pharma Imports",
            "hs_code": "300490",
            "country": "IN",
            "price_range": [1.0, 3.0],
            "moq": 10000,
            "certifications": ["CDSCO"],
            "import_volume_annual": 150000,
            "payment_terms": ["LC"],
            "industry": "의약품",
        },
        {
            "id": "buyer_045",
            "company_name": "Bangalore Health Supplements",
            "hs_code": "210690",
            "country": "IN",
            "price_range": [1.5, 3.5],
            "moq": 8000,
            "certifications": ["FSSAI"],
            "import_volume_annual": 90000,
            "payment_terms": ["LC", "TT"],
            "industry": "식품",
        },
        
        # === 호주 (AU) - 2개 ===
        {
            "id": "buyer_046",
            "company_name": "Sydney Beauty Imports",
            "hs_code": "330499",
            "country": "AU",
            "price_range": [5.0, 8.0],
            "moq": 500,
            "certifications": ["TGA"],
            "import_volume_annual": 20000,
            "payment_terms": ["TT", "LC"],
            "industry": "화장품",
        },
        {
            "id": "buyer_047",
            "company_name": "Melbourne Health Corp",
            "hs_code": "210690",
            "country": "AU",
            "price_range": [4.0, 6.0],
            "moq": 600,
            "certifications": ["TGA", "AQIS"],
            "import_volume_annual": 18000,
            "payment_terms": ["TT"],
            "industry": "식품",
        },
        
        # === UAE (AE) - 2개 ===
        {
            "id": "buyer_048",
            "company_name": "Dubai Beauty Trading",
            "hs_code": "330499",
            "country": "AE",
            "price_range": [4.0, 7.0],
            "moq": 1500,
            "certifications": ["HALAL", "ISO"],
            "import_volume_annual": 50000,
            "payment_terms": ["LC", "TT"],
            "industry": "화장품",
        },
        {
            "id": "buyer_049",
            "company_name": "Abu Dhabi Health Foods",
            "hs_code": "210690",
            "country": "AE",
            "price_range": [3.0, 5.5],
            "moq": 2000,
            "certifications": ["HALAL"],
            "import_volume_annual": 40000,
            "payment_terms": ["LC"],
            "industry": "식품",
        },
        
        # === 영국 (GB) - 1개 ===
        {
            "id": "buyer_050",
            "company_name": "London Cosmetics Ltd",
            "hs_code": "330499",
            "country": "GB",
            "price_range": [5.0, 8.0],
            "moq": 800,
            "certifications": ["CE", "ISO"],
            "import_volume_annual": 30000,
            "payment_terms": ["LC", "TT"],
            "industry": "화장품",
        },
    ]


# =============================================================================
# 국가 정보 테이블 (시장규모 추정용)
# =============================================================================
COUNTRY_MARKET_DATA = {
    "US": {
        "name_kr": "미국",
        "name_en": "United States",
        "gdp_usd": 25460000000000,  # 25.46조 USD (2023)
        "population": 331000000,
        "industry_ratios": {
            "화장품": 0.008,  # 0.8%
            "의약품": 0.045,  # 4.5%
            "식품": 0.012,    # 1.2%
            "전자기기": 0.025,
            "섬유": 0.006,
        },
        "import_growth_rate": 0.03,
        "risk_grade": "A",
    },
    "CN": {
        "name_kr": "중국",
        "name_en": "China",
        "gdp_usd": 17960000000000,
        "population": 1412000000,
        "industry_ratios": {
            "화장품": 0.006,
            "의약품": 0.035,
            "식품": 0.015,
            "전자기기": 0.035,
            "섬유": 0.012,
        },
        "import_growth_rate": 0.05,
        "risk_grade": "B",
    },
    "JP": {
        "name_kr": "일본",
        "name_en": "Japan",
        "gdp_usd": 4230000000000,
        "population": 125000000,
        "industry_ratios": {
            "화장품": 0.012,
            "의약품": 0.055,
            "식품": 0.010,
            "전자기기": 0.022,
            "섬유": 0.004,
        },
        "import_growth_rate": 0.02,
        "risk_grade": "A",
    },
    "VN": {
        "name_kr": "베트남",
        "name_en": "Vietnam",
        "gdp_usd": 409000000000,
        "population": 99000000,
        "industry_ratios": {
            "화장품": 0.005,
            "의약품": 0.025,
            "식품": 0.018,
            "전자기기": 0.015,
            "섬유": 0.025,
        },
        "import_growth_rate": 0.08,
        "risk_grade": "B",
    },
    "DE": {
        "name_kr": "독일",
        "name_en": "Germany",
        "gdp_usd": 4070000000000,
        "population": 84000000,
        "industry_ratios": {
            "화장품": 0.007,
            "의약품": 0.048,
            "식품": 0.008,
            "전자기기": 0.018,
            "섬유": 0.005,
        },
        "import_growth_rate": 0.025,
        "risk_grade": "A",
    },
    "SG": {
        "name_kr": "싱가포르",
        "name_en": "Singapore",
        "gdp_usd": 397000000000,
        "population": 5900000,
        "industry_ratios": {
            "화장품": 0.006,
            "의약품": 0.035,
            "식품": 0.008,
            "전자기기": 0.045,
            "섬유": 0.003,
        },
        "import_growth_rate": 0.04,
        "risk_grade": "A",
    },
    "TH": {
        "name_kr": "태국",
        "name_en": "Thailand",
        "gdp_usd": 495000000000,
        "population": 70000000,
        "industry_ratios": {
            "화장품": 0.006,
            "의약품": 0.028,
            "식품": 0.015,
            "전자기기": 0.020,
            "섬유": 0.008,
        },
        "import_growth_rate": 0.05,
        "risk_grade": "B",
    },
    "ID": {
        "name_kr": "인도네시아",
        "name_en": "Indonesia",
        "gdp_usd": 1320000000000,
        "population": 276000000,
        "industry_ratios": {
            "화장품": 0.004,
            "의약품": 0.022,
            "식품": 0.020,
            "전자기기": 0.012,
            "섬유": 0.015,
        },
        "import_growth_rate": 0.06,
        "risk_grade": "B",
    },
    "IN": {
        "name_kr": "인도",
        "name_en": "India",
        "gdp_usd": 3390000000000,
        "population": 1420000000,
        "industry_ratios": {
            "화장품": 0.003,
            "의약품": 0.025,
            "식품": 0.018,
            "전자기기": 0.015,
            "섬유": 0.020,
        },
        "import_growth_rate": 0.07,
        "risk_grade": "B",
    },
    "AU": {
        "name_kr": "호주",
        "name_en": "Australia",
        "gdp_usd": 1680000000000,
        "population": 26000000,
        "industry_ratios": {
            "화장품": 0.008,
            "의약품": 0.042,
            "식품": 0.010,
            "전자기기": 0.015,
            "섬유": 0.004,
        },
        "import_growth_rate": 0.03,
        "risk_grade": "A",
    },
    "AE": {
        "name_kr": "아랍에미리트",
        "name_en": "UAE",
        "gdp_usd": 507000000000,
        "population": 10000000,
        "industry_ratios": {
            "화장품": 0.010,
            "의약품": 0.030,
            "식품": 0.015,
            "전자기기": 0.025,
            "섬유": 0.008,
        },
        "import_growth_rate": 0.05,
        "risk_grade": "A",
    },
    "GB": {
        "name_kr": "영국",
        "name_en": "United Kingdom",
        "gdp_usd": 3070000000000,
        "population": 67000000,
        "industry_ratios": {
            "화장품": 0.009,
            "의약품": 0.050,
            "식품": 0.009,
            "전자기기": 0.016,
            "섬유": 0.005,
        },
        "import_growth_rate": 0.025,
        "risk_grade": "A",
    },
}


def get_market_size(country_code: str, industry: str) -> Dict:
    """국가+산업별 시장규모 추정"""
    country_data = COUNTRY_MARKET_DATA.get(country_code.upper(), {})
    
    if not country_data:
        return {
            "market_size_usd": 100000000,  # 기본값 1억 USD
            "source": "default",
            "confidence": "low",
        }
    
    gdp = country_data.get("gdp_usd", 1000000000000)
    industry_ratio = country_data.get("industry_ratios", {}).get(industry, 0.005)
    growth_rate = country_data.get("import_growth_rate", 0.03)
    
    market_size = gdp * industry_ratio
    
    return {
        "market_size_usd": market_size,
        "gdp_usd": gdp,
        "industry_ratio": industry_ratio,
        "growth_rate": growth_rate,
        "country_name": country_data.get("name_kr", country_code),
        "risk_grade": country_data.get("risk_grade", "C"),
        "source": "calculated",
        "confidence": "medium",
    }


def get_buyer_stats() -> Dict:
    """바이어 데이터 통계"""
    buyers = load_buyer_profiles()
    
    country_dist = {}
    industry_dist = {}
    hs_dist = {}
    
    for buyer in buyers:
        country = buyer.get("country", "Unknown")
        industry = buyer.get("industry", "Unknown")
        hs_code = buyer.get("hs_code", "Unknown")[:4]
        
        country_dist[country] = country_dist.get(country, 0) + 1
        industry_dist[industry] = industry_dist.get(industry, 0) + 1
        hs_dist[hs_code] = hs_dist.get(hs_code, 0) + 1
    
    return {
        "total_buyers": len(buyers),
        "by_country": country_dist,
        "by_industry": industry_dist,
        "by_hs_code": hs_dist,
    }
