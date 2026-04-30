"""HS 코드 추천 엔진
제품명(한국어 or 영어) 입력 → HS 코드 후보 최대 5개 반환
각 후보: hs_code, 품목명(국문), 품목명(영문), 카테고리, DB 보유 국가 목록
"""
from typing import Optional
from pydantic import BaseModel


# ── 응답 스키마 ─────────────────────────────────────────────────────────────
class HSCodeCandidate(BaseModel):
    hs_code: str                  # 6자리 HS 코드
    name_ko: str                  # 품목명 (국문)
    name_en: str                  # 품목명 (영문)
    category: str                 # 대분류
    example_products: list[str]   # 해당 코드 해당 제품 예시
    supported_countries: list[str]  # 현재 DB 보유 국가


class HSCodeRecommendResponse(BaseModel):
    query: str
    candidates: list[HSCodeCandidate]
    note: str = ""


# ── HS 코드 마스터 DB ────────────────────────────────────────────────────────
# (현재 시스템에 Seed 데이터가 있는 코드 + 실제 세관 주요 코드 기준)
HS_MASTER: list[dict] = [
    # ── 화장품·퍼스널케어 (HS 33) ─────────────────────────────
    {
        "hs_code": "330499",
        "name_ko": "기타 기초화장품·스킨케어",
        "name_en": "Skin care preparations NES",
        "category": "화장품·퍼스널케어",
        "keywords": ["스킨케어", "기초화장품", "세럼", "앰플", "토너", "에센스", "로션", "크림",
                     "skincare", "serum", "ampoule", "toner", "lotion", "cream", "moisturizer"],
        "products": ["비타민C 세럼", "히알루론산 앰플", "수분크림", "토너"],
    },
    {
        "hs_code": "330410",
        "name_ko": "입술화장용 제품",
        "name_en": "Lip make-up preparations",
        "category": "색조화장품",
        "keywords": ["립스틱", "립글로스", "립밤", "입술", "lipstick", "lip gloss", "lip balm", "lip"],
        "products": ["립스틱", "립글로스", "틴트", "립밤"],
    },
    {
        "hs_code": "330420",
        "name_ko": "눈화장용 제품",
        "name_en": "Eye make-up preparations",
        "category": "색조화장품",
        "keywords": ["아이섀도", "마스카라", "아이라이너", "눈화장", "eye shadow", "mascara", "eyeliner"],
        "products": ["아이섀도", "마스카라", "아이라이너"],
    },
    {
        "hs_code": "330491",
        "name_ko": "파우더·메이크업 베이스",
        "name_en": "Powders, whether or not compressed",
        "category": "색조화장품",
        "keywords": ["파운데이션", "파우더", "쿠션", "비비크림", "foundation", "powder", "cushion", "bb cream"],
        "products": ["파운데이션", "쿠션 팩트", "파우더", "BB크림"],
    },
    {
        "hs_code": "330510",
        "name_ko": "샴푸",
        "name_en": "Shampoos",
        "category": "헤어케어",
        "keywords": ["샴푸", "shampoo", "헤어", "hair wash"],
        "products": ["두피 샴푸", "볼륨 샴푸", "손상 케어 샴푸"],
    },
    {
        "hs_code": "330590",
        "name_ko": "기타 헤어케어 제품",
        "name_en": "Hair preparations NES",
        "category": "헤어케어",
        "keywords": ["헤어에센스", "헤어오일", "트리트먼트", "헤어팩", "헤어세럼",
                     "hair essence", "hair oil", "hair treatment", "hair serum"],
        "products": ["헤어 에센스", "헤어 오일", "트리트먼트"],
    },
    {
        "hs_code": "330300",
        "name_ko": "향수·오드뚜왈렛",
        "name_en": "Perfumes and toilet waters",
        "category": "향수",
        "keywords": ["향수", "퍼퓸", "perfume", "fragrance", "오드뚜왈렛", "cologne"],
        "products": ["향수", "퍼퓸", "오드뚜왈렛"],
    },
    {
        "hs_code": "340111",
        "name_ko": "세안제·클렌저",
        "name_en": "Soap and cleansers for skin care",
        "category": "화장품·퍼스널케어",
        "keywords": ["클렌저", "폼클렌징", "세안제", "클렌징오일", "비누", "cleanser", "foam cleanser",
                     "cleansing oil", "facial wash", "soap"],
        "products": ["폼 클렌저", "클렌징 오일", "워터 클렌저"],
    },
    # ── 건강기능식품·식품 (HS 21) ────────────────────────────
    {
        "hs_code": "210690",
        "name_ko": "기타 식품조제품 (건강기능식품)",
        "name_en": "Food preparations NES (health supplements)",
        "category": "건강기능식품",
        "keywords": ["건강기능식품", "영양제", "비타민", "프로바이오틱스", "콜라겐", "홍삼",
                     "supplement", "vitamin", "probiotic", "collagen", "red ginseng", "nutraceutical"],
        "products": ["비타민C", "프로바이오틱스", "콜라겐 드링크", "홍삼 엑기스"],
    },
    {
        "hs_code": "210111",
        "name_ko": "커피 추출물·에센스",
        "name_en": "Extracts, essences and concentrates of coffee",
        "category": "식품",
        "keywords": ["커피", "coffee", "원두", "에스프레소", "카페인"],
        "products": ["인스턴트 커피", "커피 농축액"],
    },
    # ── 의약품·바이오 (HS 30) ───────────────────────────────
    {
        "hs_code": "300490",
        "name_ko": "기타 의약품",
        "name_en": "Medicaments NES",
        "category": "의약품",
        "keywords": ["의약품", "약", "제약", "medicine", "drug", "pharmaceutical"],
        "products": ["정제", "캡슐", "시럽"],
    },
    # ── 전자·IT (HS 85·84) ─────────────────────────────────
    {
        "hs_code": "851712",
        "name_ko": "스마트폰·무선통신기기",
        "name_en": "Telephones for cellular networks",
        "category": "전자기기",
        "keywords": ["스마트폰", "핸드폰", "휴대폰", "smartphone", "mobile phone", "cellphone"],
        "products": ["스마트폰", "피처폰"],
    },
    {
        "hs_code": "847130",
        "name_ko": "노트북·태블릿 컴퓨터",
        "name_en": "Portable computers",
        "category": "전자기기",
        "keywords": ["노트북", "태블릿", "laptop", "tablet", "notebook"],
        "products": ["노트북", "태블릿 PC"],
    },
    {
        "hs_code": "854231",
        "name_ko": "메모리 반도체",
        "name_en": "Electronic integrated circuits — memories",
        "category": "반도체",
        "keywords": ["반도체", "메모리", "DRAM", "NAND", "semiconductor", "memory chip"],
        "products": ["DRAM", "NAND 플래시", "SSD"],
    },
    # ── 자동차부품 (HS 87) ─────────────────────────────────
    {
        "hs_code": "870830",
        "name_ko": "자동차 브레이크·서보브레이크",
        "name_en": "Brakes and servo-brakes for vehicles",
        "category": "자동차부품",
        "keywords": ["자동차부품", "브레이크", "car parts", "auto parts", "brake"],
        "products": ["브레이크 패드", "브레이크 디스크"],
    },
    {
        "hs_code": "870899",
        "name_ko": "기타 자동차 부품",
        "name_en": "Other parts for motor vehicles",
        "category": "자동차부품",
        "keywords": ["자동차부품", "차부품", "auto parts", "car parts", "vehicle parts"],
        "products": ["범퍼", "미러", "시트", "엔진 부품"],
    },
    # ── 섬유·의류 (HS 61·62) ───────────────────────────────
    {
        "hs_code": "610910",
        "name_ko": "면 티셔츠·메리야스 상의",
        "name_en": "T-shirts, singlets of cotton, knitted",
        "category": "섬유·의류",
        "keywords": ["티셔츠", "t-shirt", "상의", "의류", "cotton shirt", "니트"],
        "products": ["티셔츠", "폴로셔츠", "탱크탑"],
    },
    # ── 농수산물 (HS 03·07·08) ─────────────────────────────
    {
        "hs_code": "030617",
        "name_ko": "냉동 새우",
        "name_en": "Frozen shrimps and prawns",
        "category": "수산물",
        "keywords": ["새우", "shrimp", "prawn", "seafood"],
        "products": ["냉동 새우", "건새우"],
    },
    # ── 기계·장비 (HS 84) ─────────────────────────────────
    {
        "hs_code": "841810",
        "name_ko": "냉장·냉동 복합기기",
        "name_en": "Combined refrigerator-freezers",
        "category": "가전·기계",
        "keywords": ["냉장고", "냉동고", "refrigerator", "freezer"],
        "products": ["냉장고", "냉동고"],
    },
]

# HS 코드별 지원 국가 (Seed 데이터 보유 + COUNTRY_RISK DB 기준)
HS_SUPPORTED_COUNTRIES: dict[str, list[str]] = {
    "330499": ["VN", "TH", "US", "ID", "PH", "MY", "SG", "DE", "JP", "AU"],
    "870830": ["VN", "TH", "US"],
    "210690": ["VN", "TH", "US", "JP"],
    "330410": ["VN", "TH", "US", "MY", "SG"],
    "330420": ["VN", "TH", "US"],
    "330491": ["VN", "TH", "US"],
    "330510": ["VN", "TH"],
    "330590": ["VN", "TH"],
    "330300": ["US", "DE", "JP", "SG"],
    "340111": ["VN", "TH", "US"],
    "210690": ["VN", "TH", "US", "JP"],
    "300490": ["US", "DE", "JP"],
    "870899": ["VN", "TH", "US", "DE"],
    "DEFAULT": ["VN", "TH", "US"],   # 데이터 없는 코드 기본값
}


def _score_match(query: str, keywords: list[str]) -> int:
    """쿼리 토큰과 키워드 매칭 점수 계산"""
    q = query.lower().strip()
    score = 0
    # 전체 일치
    if q in [k.lower() for k in keywords]:
        score += 100
    # 부분 포함
    for kw in keywords:
        if kw.lower() in q or q in kw.lower():
            score += 20
    # 단어 단위 분할 매칭
    tokens = q.split()
    for token in tokens:
        if len(token) < 2:
            continue
        for kw in keywords:
            if token in kw.lower():
                score += 5
    return score


class HSCodeRecommender:
    """제품명 → HS 코드 추천 서비스"""

    def recommend(
        self,
        product_query: str,
        top_k: int = 5,
    ) -> HSCodeRecommendResponse:
        """
        제품명(한국어·영어·혼합) 입력 → HS 코드 후보 반환
        """
        if not product_query.strip():
            return HSCodeRecommendResponse(
                query=product_query,
                candidates=[],
                note="제품명을 입력해 주세요.",
            )

        scored = []
        for item in HS_MASTER:
            score = _score_match(product_query, item["keywords"])
            if score > 0:
                scored.append((score, item))

        # 점수 내림차순 정렬
        scored.sort(key=lambda x: -x[0])
        top = scored[:top_k]

        candidates = []
        for _, item in top:
            supported = HS_SUPPORTED_COUNTRIES.get(
                item["hs_code"],
                HS_SUPPORTED_COUNTRIES["DEFAULT"],
            )
            candidates.append(HSCodeCandidate(
                hs_code=item["hs_code"],
                name_ko=item["name_ko"],
                name_en=item["name_en"],
                category=item["category"],
                example_products=item["products"],
                supported_countries=supported,
            ))

        note = ""
        if not candidates:
            note = "일치하는 HS 코드가 없습니다. 더 구체적인 제품명을 입력하거나 HS 코드를 직접 입력해 주세요."

        return HSCodeRecommendResponse(
            query=product_query,
            candidates=candidates,
            note=note,
        )
