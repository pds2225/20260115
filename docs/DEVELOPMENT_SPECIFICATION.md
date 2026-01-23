# 글로벌 수출 인텔리전스 플랫폼 개발정의서

**문서 버전**: 1.0.0  
**작성일**: 2026-01-23  
**상태**: MVP 개발 완료

---

## 1. 프로젝트 개요

### 1.1 프로젝트 정보
| 항목 | 내용 |
|------|------|
| 프로젝트명 | 글로벌 수출 인텔리전스 플랫폼 |
| 목적 | 중소 수출기업의 해외시장 진출 지원 |
| 대상 사용자 | 해외시장 진출을 희망하는 중소 수출기업 |
| 개발 단계 | MVP (Minimum Viable Product) |

### 1.2 핵심 기능
1. **유망 수출국 추천** - ML 기반 수출 성공 예측
2. **성과 시뮬레이션** - 타겟 국가별 매출 예측
3. **바이어-셀러 매칭** - FitScore 기반 파트너 매칭

### 1.3 KOTRA Open API 연동 현황

| API명 | 엔드포인트 | 용도 | 연동 상태 |
|-------|-----------|------|----------|
| 수출유망추천정보 | `/B410001/export-recommend-info` | ML 기반 성공 예측 | ✅ 완료 |
| 국가정보 | `/B410001/kotra_nationalInformation/natnInfo/natnInfo` | 경제지표 | ✅ 완료 |
| 상품DB | `/B410001/cmmdtDb/cmmdtDb` | 트렌드 분석 | ✅ 완료 |
| 해외시장뉴스 | `/B410001/kotra_overseasMarketNews/ovseaMrktNews` | 리스크 분석 | ✅ 완료 |
| 무역사기사례 | `/B410001/cmmrcFraudCase/cmmrcFraudCase` | 사기 리스크 | ✅ 완료 |
| 기업성공사례 | `/B410001/compSucsCase/compSucsCase` | 참고 사례 | ✅ 완료 |

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Web UI    │  │  Mobile App │  │  3rd Party  │              │
│  │  (React)    │  │  (Future)   │  │   Systems   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              FastAPI Application                         │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │    │
│  │  │  /recommend │ │  /simulate  │ │   /match    │        │    │
│  │  │   Router    │ │   Router    │ │   Router    │        │    │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘        │    │
│  └─────────┼───────────────┼───────────────┼───────────────┘    │
└────────────┼───────────────┼───────────────┼────────────────────┘
             │               │               │
             ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐    │
│  │  Recommendation │ │   Simulation    │ │    Matching     │    │
│  │    Service      │ │    Service      │ │    Service      │    │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘    │
│           │                   │                   │              │
│           └───────────────────┼───────────────────┘              │
│                               ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 KOTRA API Client                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │   │
│  │  │ Export   │ │ Country  │ │ Product  │ │  News    │     │   │
│  │  │ Recommend│ │   Info   │ │    DB    │ │  Risk    │     │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │   │
│  │  ┌──────────┐ ┌──────────┐                               │   │
│  │  │  Fraud   │ │ Success  │                               │   │
│  │  │  Cases   │ │  Cases   │                               │   │
│  │  └──────────┘ └──────────┘                               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Data Sources                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              KOTRA Open API (data.go.kr)                 │    │
│  │  - 수출유망추천정보 (ML 예측)                              │    │
│  │  - 국가정보 (경제지표)                                     │    │
│  │  - 상품DB (트렌드)                                        │    │
│  │  - 해외시장뉴스 (리스크)                                   │    │
│  │  - 무역사기사례 (사기 리스크)                              │    │
│  │  - 기업성공사례 (참고)                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 기술 스택

| 구분 | 기술 | 버전 | 용도 |
|------|------|------|------|
| **Backend** | Python | 3.11+ | 런타임 |
| | FastAPI | 0.115.0 | 웹 프레임워크 |
| | Pydantic | 2.10.0 | 데이터 검증 |
| | httpx | 0.28.1 | 비동기 HTTP 클라이언트 |
| | uvicorn | 0.32.0 | ASGI 서버 |
| **DevOps** | Git | - | 버전 관리 |
| | GitHub | - | 코드 저장소 |
| **External** | KOTRA Open API | - | 데이터 소스 |

### 2.3 디렉토리 구조

```
webapp/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 애플리케이션 진입점
│   │
│   ├── routers/                   # API 라우터 (Controller)
│   │   ├── __init__.py
│   │   ├── recommendation.py      # POST/GET /recommend
│   │   ├── simulation.py          # POST/GET /simulate
│   │   └── matching.py            # POST /match
│   │
│   ├── services/                  # 비즈니스 로직 (Service)
│   │   ├── __init__.py
│   │   ├── kotra_client.py        # KOTRA API 통합 클라이언트
│   │   ├── recommendation_service.py
│   │   ├── simulation_service.py
│   │   └── matching_service.py
│   │
│   ├── models/                    # 데이터 모델 (DTO/Schema)
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic 모델 정의
│   │
│   └── database/                  # 데이터 액세스 (Repository)
│       ├── __init__.py
│       └── database.py            # 인메모리 예제 데이터
│
├── docs/                          # 문서
│   └── DEVELOPMENT_SPECIFICATION.md
│
├── tests/                         # 테스트 (추후 추가)
│   └── __init__.py
│
├── .env.example                   # 환경변수 템플릿
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 3. API 명세

### 3.1 공통 사항

#### Base URL
```
# 개발 환경
http://localhost:8000

# 운영 환경 (예정)
https://export-intelligence.pages.dev
```

#### 공통 응답 코드
| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (파라미터 오류) |
| 422 | 유효성 검증 실패 |
| 500 | 서버 내부 오류 |

#### 공통 헤더
```http
Content-Type: application/json
Accept: application/json
```

---

### 3.2 국가 추천 API (`/recommend`)

#### 3.2.1 POST /recommend - 상세 국가 추천

**Request**
```json
{
  "hs_code": "330499",
  "current_export_countries": ["JP", "CN"],
  "export_scale": "medium",
  "goal": "new_market",
  "top_n": 5
}
```

**Request Parameters**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| hs_code | string | ✅ | HS 코드 (4-6자리) |
| current_export_countries | string[] | ❌ | 현재 수출국 (ISO 2-letter) |
| export_scale | string | ❌ | 수출 규모 (small/medium/large) |
| goal | string | ❌ | 수출 목표 (new_market/market_expansion/risk_diversification) |
| top_n | integer | ❌ | 추천 개수 (1-20, 기본값 5) |

**Response**
```json
{
  "hs_code": "330499",
  "goal": "new_market",
  "total_countries_analyzed": 50,
  "recommendations": [
    {
      "rank": 1,
      "country_code": "US",
      "country_name": "미국",
      "success_score": 4.2,
      "success_probability": 0.78,
      "gdp": 25462.7,
      "growth_rate": 2.1,
      "risk_grade": "A",
      "market_characteristics": "세계 최대 소비 시장...",
      "promising_products": ["화장품", "건강기능식품"],
      "recent_trends": [
        {"title": "K-뷰티 인기 상승", "date": "2026-01-20"}
      ],
      "success_cases": [
        {"company": "ABC화장품", "entry_type": "직접수출"}
      ],
      "score_breakdown": {
        "export_prediction": 33.6,
        "economic_indicators": 22.0,
        "risk_assessment": 18.0,
        "market_trends": 12.0
      }
    }
  ],
  "data_sources": ["KOTRA 수출유망추천정보", "KOTRA 국가정보"],
  "generated_at": "2026-01-23T07:30:00Z"
}
```

#### 3.2.2 GET /recommend/quick - 빠른 국가 추천

**Request**
```
GET /recommend/quick?hs_code=330499&goal=new_market&top_n=5&exclude_countries=JP,CN
```

**Query Parameters**
| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| hs_code | string | ✅ | HS 코드 |
| goal | string | ❌ | 수출 목표 |
| top_n | integer | ❌ | 추천 개수 |
| exclude_countries | string | ❌ | 제외 국가 (콤마 구분) |

---

### 3.3 시뮬레이션 API (`/simulate`)

#### 3.3.1 POST /simulate - 성과 시뮬레이션

**Request**
```json
{
  "hs_code": "330499",
  "target_country": "US",
  "price_per_unit": 10.0,
  "moq": 1000,
  "annual_capacity": 50000,
  "market_size_estimate": null,
  "include_news_risk": true
}
```

**Request Parameters**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| hs_code | string | ✅ | HS 코드 |
| target_country | string | ✅ | 타겟 국가 (ISO 2-letter) |
| price_per_unit | float | ✅ | 단가 (USD) |
| moq | integer | ✅ | 최소주문수량 |
| annual_capacity | integer | ✅ | 연간 생산능력 |
| market_size_estimate | float | ❌ | 시장 규모 추정 (USD millions) |
| include_news_risk | boolean | ❌ | 뉴스 리스크 분석 포함 여부 |

**Response**
```json
{
  "target_country": "US",
  "country_name": "미국",
  "hs_code": "330499",
  "estimated_revenue_min": 50000.0,
  "estimated_revenue_max": 250000.0,
  "success_probability": 0.65,
  "market_size": 5000000000.0,
  "market_share_min": 0.001,
  "market_share_max": 0.005,
  "news_risk_adjustment": {
    "risk_adjustment": 3.5,
    "negative_count": 2,
    "positive_count": 5,
    "total_analyzed": 50,
    "recent_news": [
      {"title": "K-뷰티 수요 증가", "sentiment": "positive"}
    ]
  },
  "economic_indicators": {
    "gdp": 25462.7,
    "growth_rate": 2.1,
    "inflation_rate": 3.2,
    "risk_grade": "A",
    "exchange_rate": 1320.5
  },
  "calculation_breakdown": {
    "base_probability": 0.30,
    "weights": {
      "export_ml": 0.40,
      "economic": 0.25,
      "news_sentiment": 0.20,
      "trends": 0.15
    },
    "components": {
      "export_ml": {"raw_score": 3.5, "contribution": 0.28},
      "economic": {"factor": 0.7, "contribution": 0.175},
      "news_sentiment": {"factor": 0.6, "contribution": 0.12},
      "trends": {"factor": 0.5, "contribution": 0.075}
    }
  },
  "data_sources": ["KOTRA 수출유망추천정보", "KOTRA 국가정보", "KOTRA 해외시장뉴스"],
  "generated_at": "2026-01-23T07:30:00Z"
}
```

#### 3.3.2 GET /simulate/quick - 빠른 시뮬레이션

**Request**
```
GET /simulate/quick?hs_code=330499&country=US&price=10&moq=1000&capacity=50000
```

---

### 3.4 매칭 API (`/match`)

#### 3.4.1 POST /match - 바이어-셀러 매칭

**Request**
```json
{
  "profile_type": "seller",
  "profile": {
    "hs_code": "330499",
    "country": "KR",
    "price_range": [5.0, 8.0],
    "moq": 1000,
    "certifications": ["FDA", "ISO"]
  },
  "top_n": 10,
  "include_risk_analysis": true
}
```

**Request Parameters**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| profile_type | string | ✅ | 프로필 타입 (seller/buyer) |
| profile | object | ✅ | 프로필 정보 |
| top_n | integer | ❌ | 매칭 개수 (1-50, 기본값 10) |
| include_risk_analysis | boolean | ❌ | 리스크 분석 포함 여부 |

**Profile Object**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| hs_code | string | ✅ | HS 코드 |
| country | string | ✅ | 국가 코드 |
| price_range | float[] | ✅ | 가격 범위 [min, max] USD |
| moq | integer | ✅ | MOQ |
| certifications | string[] | ❌ | 인증 목록 |

**Response**
```json
{
  "profile_type": "seller",
  "total_candidates": 50,
  "matches": [
    {
      "partner_id": "buyer_001",
      "partner_type": "buyer",
      "company_name": "US Beauty Imports Inc.",
      "country": "US",
      "country_name": "미국",
      "fit_score": 92.0,
      "score_breakdown": {
        "base": 50.0,
        "hs_code_match": 20.0,
        "price_compatible": 15.0,
        "moq_compatible": 10.0,
        "certification_match": 5.0,
        "fraud_risk_penalty": 0.0,
        "success_case_bonus": 5.0
      },
      "hs_code_match": true,
      "price_compatible": true,
      "moq_compatible": true,
      "certification_match": ["FDA"],
      "fraud_risk": {
        "risk_level": "SAFE",
        "case_count": 2,
        "score_penalty": 0,
        "fraud_types": {"서류위조": 1, "대금미지급": 1},
        "prevention_tips": ["거래 전 신용조회 필수"]
      },
      "success_cases": [
        {
          "company": "ABC코스메틱",
          "entry_type": "직접수출",
          "relevance_score": 85
        }
      ]
    }
  ],
  "countries_analyzed": ["US", "JP", "VN", "CN"],
  "high_risk_countries": [],
  "data_sources": ["KOTRA 무역사기사례", "KOTRA 기업성공사례"],
  "generated_at": "2026-01-23T07:30:00Z"
}
```

#### 3.4.2 POST /match/seller - 셀러용 바이어 매칭

```
POST /match/seller?hs_code=330499&country=KR&price_min=5&price_max=8&moq=1000&certifications=FDA,ISO
```

#### 3.4.3 POST /match/buyer - 바이어용 셀러 매칭

```
POST /match/buyer?hs_code=330499&country=US&budget_min=5&budget_max=10&moq=1000&required_certs=FDA
```

---

## 4. 데이터 모델

### 4.1 KOTRA API 데이터 매핑

#### 4.1.1 수출유망추천정보 API
| KOTRA 필드 | 내부 필드 | 타입 | 설명 |
|-----------|----------|------|------|
| HSCD | hs_code | string | HS 코드 (6자리) |
| NAT_NAME | country_name | string | 국가명 |
| EXPORTSCALE | export_scale | string | 수출규모 |
| EXP_BHRC_SCR | success_score | float | 수출성공예측점수 (0-5+) |
| UPDT_DT | updated_at | datetime | 업데이트 일시 |

#### 4.1.2 국가정보 API
| KOTRA 필드 | 내부 필드 | 타입 | 설명 |
|-----------|----------|------|------|
| natnNm | country_name | string | 국가명 |
| cptlNm | capital | string | 수도 |
| poplCnt | population | integer | 인구 |
| gdpcpList.gdpcp | gdp | float | GDP (억불) |
| ecnmyGrwrtList.ecnmyGrwrt | growth_rate | float | 경제성장률 (%) |
| inflRateList.inflRate | inflation_rate | float | 물가상승률 (%) |
| riskGrd | risk_grade | string | 리스크등급 (A-E) |
| mrktChrtrtCntnt | market_characteristics | string | 시장특성 |
| bhrcGoodsList | promising_goods | array | 유망상품 목록 |

#### 4.1.3 상품DB API
| KOTRA 필드 | 내부 필드 | 타입 | 설명 |
|-----------|----------|------|------|
| bbstxSn | article_id | string | 게시글 ID |
| natn | country | string | 국가명 |
| newsTitl | title | string | 제목 |
| cntntSumar | summary | string | 요약 |
| cmdltNmKorn | product_name_ko | string | 품목명(한글) |
| hsCdNm | hs_code_name | string | HS코드명 |
| othbcDt | published_date | string | 게시일 |

#### 4.1.4 해외시장뉴스 API
| KOTRA 필드 | 내부 필드 | 타입 | 설명 |
|-----------|----------|------|------|
| nttSn | news_id | string | 뉴스 ID |
| natNm | country_name | string | 국가명 |
| newsCdNm | category | string | 뉴스 카테고리 |
| title | title | string | 제목 |
| cntnt | content | string | 본문 |
| wrtDt | written_date | string | 작성일 |

#### 4.1.5 무역사기사례 API
| KOTRA 필드 | 내부 필드 | 타입 | 설명 |
|-----------|----------|------|------|
| nttSn | case_id | string | 사례 ID |
| natNm | country_name | string | 국가명 |
| title | title | string | 제목 |
| fraudTypNm | fraud_type | string | 사기 유형 |
| cntnt | content | string | 내용 |
| prvntMthd | prevention_method | string | 예방법 |

#### 4.1.6 기업성공사례 API
| KOTRA 필드 | 내부 필드 | 타입 | 설명 |
|-----------|----------|------|------|
| nttSn | case_id | string | 사례 ID |
| natNm | country_name | string | 국가명 |
| corpNm | company_name | string | 기업명 |
| indutyNm | industry | string | 업종 |
| entryTypNm | entry_type | string | 진출유형 |
| title | title | string | 제목 |

### 4.2 내부 데이터 모델

#### 4.2.1 SellerProfile
```python
class SellerProfile:
    id: str                    # 셀러 ID
    company_name: str          # 기업명
    hs_code: str               # HS 코드
    country: str               # 국가 (ISO 2-letter)
    price_range: List[float]   # 가격 범위 [min, max]
    moq: int                   # 최소주문수량
    certifications: List[str]  # 보유 인증
    export_experience_years: int  # 수출 경력
    languages: List[str]       # 지원 언어
```

#### 4.2.2 BuyerProfile
```python
class BuyerProfile:
    id: str                    # 바이어 ID
    company_name: str          # 기업명
    hs_code: str               # 관심 HS 코드
    country: str               # 국가
    price_range: List[float]   # 예산 범위 [min, max]
    moq: int                   # 희망 MOQ
    certifications: List[str]  # 필요 인증
    import_volume_annual: int  # 연간 수입량
    payment_terms: List[str]   # 결제 조건
```

---

## 5. 비즈니스 로직

### 5.1 국가 추천 알고리즘

#### 5.1.1 점수 계산 공식

```
총점 = 수출예측점수(40%) + 경제지표점수(25%) + 리스크점수(20%) + 트렌드점수(15%)
```

| 구성요소 | 가중치 | 계산 방식 | 최대 점수 |
|----------|--------|----------|----------|
| 수출예측점수 | 40% | (EXP_BHRC_SCR / 5) × 40 | 40점 |
| 경제지표점수 | 25% | GDP + 성장률 보너스 | 25점 |
| 리스크점수 | 20% | 리스크등급 기반 | 20점 |
| 트렌드점수 | 15% | 상품DB 기사 수 기반 | 15점 |

#### 5.1.2 경제지표 점수
```
기본: 15점
+ 성장률 > 3%: +5점
+ 성장률 > 1%: +2점
+ GDP > 1조불: +5점
+ GDP > 1000억불: +2점
```

#### 5.1.3 리스크등급 점수
| 등급 | 점수 |
|------|------|
| A/AA/AAA | 20점 |
| B/BB/BBB | 15점 |
| C/CC/CCC | 10점 |
| D/DD/DDD/E | 5점 |

### 5.2 시뮬레이션 알고리즘

#### 5.2.1 성공확률 계산

```
성공확률 = 기본확률(30%) + 가중합계 × 0.65

가중합계 = 
  ML예측(0-1) × 0.40 +
  경제지표(0-1) × 0.25 +
  뉴스감성(0-1) × 0.20 +
  트렌드(0-1) × 0.15

최종 범위: 5% ~ 95%
```

#### 5.2.2 뉴스 리스크 분석

**부정 키워드**: 규제, 금지, 관세, 제재, 리콜, 분쟁, 위기
**긍정 키워드**: 성장, 수요증가, 호조, 확대, 개선, 투자

```
리스크조정 = ((긍정수 - 부정수) / 전체수) × 15
범위: -15 ~ +15
```

#### 5.2.3 매출 추정

```
시장점유율: 0.01% ~ 0.1%
매출_최소 = 시장규모 × 0.0001 × 성공확률
매출_최대 = 시장규모 × 0.001 × 성공확률

단, 생산능력 기반 상한:
매출_최소 = min(매출_최소, 단가 × 연간생산능력 × 0.3)
매출_최대 = min(매출_최대, 단가 × 연간생산능력 × 0.8)
```

### 5.3 FitScore 알고리즘

#### 5.3.1 점수 구성 (0-100점)

| 항목 | 점수 | 조건 |
|------|------|------|
| 기본 | +50 | 항상 |
| HS코드 매칭 | +20 | 4자리 일치 시 |
| 가격 호환 | +15 | 범위 중첩 시 |
| MOQ 호환 | +10 | 50% 이내 차이 |
| 인증 매칭 | +5/개 | 최대 15점 |
| 무역사기 리스크 | -15~0 | 국가별 사기건수 |
| 성공사례 보너스 | +5 | 관련 사례 존재 시 |

#### 5.3.2 사기 리스크 패널티

| 사기 건수 | 리스크 등급 | 패널티 |
|----------|------------|--------|
| 20건 이상 | HIGH | -15점 |
| 10건 이상 | MEDIUM | -7점 |
| 5건 이상 | LOW | -3점 |
| 5건 미만 | SAFE | 0점 |

---

## 6. 환경 설정

### 6.1 환경변수

| 변수명 | 필수 | 설명 | 예시 |
|--------|------|------|------|
| KOTRA_SERVICE_KEY | ✅ | KOTRA API 인증키 | `83b96790de...` |
| HOST | ❌ | 서버 호스트 | `0.0.0.0` |
| PORT | ❌ | 서버 포트 | `8000` |
| LOG_LEVEL | ❌ | 로깅 레벨 | `INFO` |

### 6.2 .env 파일 예시

```bash
# KOTRA API
KOTRA_SERVICE_KEY=83b96790de580e57527e049d59bfcb18ae34d2bfe646c11a5d2ee6b3d95e9b23

# Server
HOST=0.0.0.0
PORT=8000

# Logging
LOG_LEVEL=INFO
```

---

## 7. 테스트 시나리오

### 7.1 국가 추천 테스트

```bash
# 화장품(330499) 신시장 추천
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"hs_code": "330499", "goal": "new_market", "top_n": 5}'

# 기대 결과: 미국, 중국, 베트남 등 상위 5개국 추천
```

### 7.2 시뮬레이션 테스트

```bash
# 미국 시장 매출 시뮬레이션
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"hs_code": "330499", "target_country": "US", "price_per_unit": 10, "moq": 1000, "annual_capacity": 50000}'

# 기대 결과: 예상 매출 범위, 성공확률, 뉴스 리스크 분석
```

### 7.3 매칭 테스트

```bash
# 셀러가 바이어 찾기
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"profile_type": "seller", "profile": {"hs_code": "330499", "country": "KR", "price_range": [5, 8], "moq": 1000, "certifications": ["FDA"]}, "top_n": 5}'

# 기대 결과: FitScore 순 바이어 목록, 사기 리스크 분석
```

---

## 8. 배포 계획

### 8.1 개발 환경 (현재)

```bash
# 로컬 실행
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 8.2 운영 환경 (예정)

| 항목 | 계획 |
|------|------|
| 플랫폼 | Cloudflare Pages / Workers |
| 도메인 | export-intelligence.pages.dev |
| CI/CD | GitHub Actions |
| 모니터링 | Cloudflare Analytics |

---

## 9. 향후 개발 계획

### 9.1 Phase 2 (예정)

- [ ] 프론트엔드 대시보드 개발 (React)
- [ ] 사용자 인증/인가 시스템
- [ ] 데이터베이스 연동 (Cloudflare D1)
- [ ] API Rate Limiting

### 9.2 Phase 3 (예정)

- [ ] AI 챗봇 통합
- [ ] 계약서 자동 생성
- [ ] 번역 기능
- [ ] 알림 시스템

---

## 10. 참고 자료

### 10.1 KOTRA API 문서

- [공공데이터포털](https://www.data.go.kr)
- [KOTRA 해외경제정보드림](https://dream.kotra.or.kr)

### 10.2 기술 문서

- [FastAPI 공식 문서](https://fastapi.tiangolo.com)
- [Pydantic V2 문서](https://docs.pydantic.dev)
- [httpx 문서](https://www.python-httpx.org)

---

**문서 끝**
