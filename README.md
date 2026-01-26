# 글로벌 수출 인텔리전스 플랫폼

중소 수출기업을 위한 AI 기반 해외시장 진출 지원 플랫폼입니다.

## 프로젝트 개요

- **목표**: KOTRA Open API 6종을 활용한 수출 인텔리전스 서비스
- **대상**: 해외시장 진출을 희망하는 중소 수출기업
- **기술스택**: FastAPI + Python 3.11 + httpx

## 🔗 URLs

- **서버 API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **GitHub**: https://github.com/pds2225/20260115

## ✅ 완료된 기능

### 1. 국가 추천 API (`/recommend`)
HS코드 기반 유망 수출국 추천

**엔드포인트:**
- `POST /recommend` - 상세 국가 추천
- `GET /recommend/quick?hs_code=330499&top_n=5` - 빠른 추천

### 2. 성과 시뮬레이션 API (`/simulate`) ✨ 완료
타겟 국가별 예상 매출 시뮬레이션

**성공확률 공식 (확정):**
```
성공확률 = 0.30 (base) + weighted_sum × 0.65

가중치:
- ML 예측 (수출유망추천정보): 40%
- 경제지표 (국가정보): 25%
- 뉴스감성 (해외시장뉴스): 20%
- 트렌드 (상품DB): 15%
```

**실제 API 데이터 테스트 결과 (HS 330499 화장품):**
| 국가 | EXP_BHRC_SCR | 성공확률 |
|------|-------------|---------|
| 🇺🇸 US | 25.65 | 68.5% |
| 🇻🇳 VN | 19.13 | 70.6% |
| 🇨🇳 CN | 18.87 | 60.7% |
| 🇯🇵 JP | 18.78 | 63.8% |
| 🇩🇪 DE | 6.20 | 52.9% |

**시장규모 계산 (GDP 기반):**
```
시장규모 = GDP × 산업비중
예: 미국 화장품 = $25.46조 × 0.8% = $203.68B
```

**엔드포인트:**
- `POST /simulate` - 상세 시뮬레이션
- `GET /simulate/quick?hs_code=330499&country=US&price=10&moq=1000&capacity=50000`

### 3. 바이어-셀러 매칭 API (`/match`) ✨ 완료

**FitScore 계산 (0-100):**
- 기본: 50점
- HS코드 매칭: +20점
- 가격 호환: +15점
- MOQ 호환: +10점
- 인증 매칭: +5점/개 (최대 +15점)
- 무역사기 페널티: -25~0점 (유형별 차등)
- 성공사례 보너스: +5~15점

**무역사기 유형별 페널티:**
| 유형 | 페널티 | 평균피해(USD) |
|------|--------|--------------|
| 이메일해킹 | -20 | 150,000 |
| 금품사취 | -18 | 50,000 |
| 선적서류위조 | -15 | 30,000 |
| 품질사기 | -12 | 20,000 |
| 기업사칭 | -15 | 40,000 |
| 인증서위조 | -10 | 15,000 |
| 운송사기 | -12 | 25,000 |
| 기타 | -8 | 10,000 |

**Seed Data (확정):**
- 50개 바이어 프로필
- 10개국: US, CN, JP, VN, DE, SG, TH, ID, IN, AU, GB, FR, MY, PH, AE
- 5개 산업: 화장품, 의약품, 식품, 전자기기, 섬유

**엔드포인트:**
- `POST /match` - 상세 매칭
- `POST /match/seller` - 셀러용 바이어 매칭
- `POST /match/buyer` - 바이어용 셀러 매칭

## 📊 데이터 아키텍처

### KOTRA API 연동 (6종)

| API | 엔드포인트 | 데이터량 | 상태 |
|-----|-----------|---------|------|
| 수출유망추천정보 | /B410001/export-recommend-info/search | 890,596건 | ✅ 연동 |
| 국가정보 | /B410001/kotra_nationalInformation/natnInfo | 250개국 | ✅ 연동 |
| 상품DB | /B410001/cmmdtDb/cmmdtDb | 6,483건 | ✅ 연동 |
| 해외시장뉴스 | /B410001/kotra_overseasMarketNews/ovseaMrktNews | 93,924건 | ✅ 연동 |
| 무역사기사례 | /B410001/cmmrcFraudCase/cmmrcFraudCase | 542건 | ✅ 연동 |
| 기업성공사례 | /B410001/compSucsCase/compSucsCase | 275건 | ✅ 연동 |

### 내부 데이터 테이블

**1. 산업-HS코드 매핑 테이블 (10개 산업)**
```python
INDUSTRY_HS_MAPPING = {
    "화장품": ["3304", "330410", "330420", ...],
    "의약품": ["3004", "300410", "300420", ...],
    "식품": ["2106", "210610", "210690", ...],
    "전자기기": ["8471", "8517", "8518", ...],
    "섬유": ["6109", "6110", "6201", ...],
    "자동차부품": ["8708", "870810", ...],
    "기계": ["8421", "8422", "8428", ...],
    "플라스틱": ["3901", "3902", "3903", ...],
    "철강": ["7208", "7209", "7210", ...],
    "농산물": ["0702", "0709", "0710", ...],
}
```

**2. 국가별 시장 데이터 (12개국)**
```python
COUNTRY_MARKET_DATA = {
    "US": {"gdp": 25.46조, "화장품비중": 0.8%, "리스크": A},
    "CN": {"gdp": 17.96조, "화장품비중": 0.9%, "리스크": B},
    ...
}
```

## 설치 및 실행

### 1. 환경 설정
```bash
cd webapp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
# .env 파일 생성
KOTRA_SERVICE_KEY=83b96790de580e57527e049d59bfcb18ae34d2bfe646c11a5d2ee6b3d95e9b23
```

### 3. 서버 실행
```bash
export KOTRA_SERVICE_KEY=your_api_key
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## API 사용 예시

### 시뮬레이션 요청 (Quick)
```bash
curl "http://localhost:8000/simulate/quick?hs_code=330499&country=US&price=10&moq=1000&capacity=50000"
```

**응답 예시:**
```json
{
  "target_country": "US",
  "hs_code": "330499",
  "success_probability": 0.685,
  "market_size": 203680000000,
  "estimated_revenue_min": 150000,
  "estimated_revenue_max": 400000,
  "calculation_breakdown": {
    "components": {
      "export_ml": {
        "raw_score": 25.65,
        "normalized": 0.855,
        "contribution": 0.342
      }
    }
  }
}
```

### 매칭 요청
```bash
curl -X POST "http://localhost:8000/match/seller?hs_code=330499&country=KR&price_min=5&price_max=8&moq=1000&certifications=FDA,ISO&top_n=5"
```

## 프로젝트 구조

```
webapp/
├── backend/
│   ├── main.py                    # FastAPI 엔트리포인트
│   ├── routers/
│   │   ├── recommendation.py      # /recommend 라우터
│   │   ├── simulation.py          # /simulate 라우터
│   │   └── matching.py            # /match 라우터
│   ├── services/
│   │   ├── kotra_client.py        # KOTRA API 통합 클라이언트
│   │   ├── recommendation_service.py  # 추천 로직
│   │   ├── simulation_service.py  # 시뮬레이션 로직
│   │   └── matching_service.py    # 매칭 로직
│   ├── models/
│   │   └── schemas.py             # Pydantic 모델
│   ├── utils/                     # 유틸리티 모듈 (NEW)
│   │   ├── cache.py               # TTL 캐시
│   │   ├── compliance.py          # 수출제한국 검사
│   │   ├── confidence.py          # 신뢰도 계산
│   │   └── missing_data.py        # 결측치 처리
│   └── database/
│       └── database.py            # 시드데이터 + 헬퍼 함수
├── config/                        # 설정 파일 (NEW)
│   └── export_blocklist.json      # 수출제한국 목록
├── tests/                         # 테스트 (NEW)
│   ├── test_recommendation.py     # 추천 테스트 (8개)
│   ├── test_matching.py           # 매칭 테스트 (10개)
│   └── test_simulation.py         # 시뮬레이션 테스트 (11개)
├── requirements.txt
├── .env
└── README.md
```

## 🆕 2026-01-26 주요 개선사항

### 1. Fallback 시스템 고도화
- 기존: KOTRA API 장애 시 고정 5개국(US, JP, CN, DE, VN) 반환
- 개선: 14일 TTL 캐시 + 25개국 풀 기반 대체 스코어링
- `backend/utils/cache.py`: TTLCache 구현

### 2. MOQ (최소주문수량) 고도화
- **Hard Gate**: buyer_moq > seller_capacity → 즉시 reject
- **Soft Score**: 0~1 점수화 (`1 - abs(diff) / max(buyer, seller)`)
- **MOV**: 최소 주문 금액(USD) 검증
- 매칭 응답에 `moq_gate_passed`, `moq_score`, `order_value_usd` 필드 추가

### 3. 인증 매칭 개선
- **required_certs**: 필수 인증 (미충족 시 탈락)
- **preferred_certs**: 선호 인증 (충족 시 가점)
- 매칭 응답에 `missing_required_certs`, `matched_preferred_certs` 필드 추가

### 4. 성공사례 보너스 개선
- 기존: 성공사례 존재 여부만 확인
- 개선: 근거 강도(Evidence Strength) 기반 점수화
```
bonus = 10 × country_match × hs_similarity × recency
- country_match: 국가 일치 시 1.0, 불일치 시 0
- hs_similarity: 4자리 일치 1.0, 2자리 일치 0.5, 불일치 0.2
- recency: 1년 이내 1.0, 2년 0.8, 3년 0.5, 그 외 0.3
```

### 5. 수출제한국 관리 (Export Blocklist)
- **hard_block**: KP, SY, IR, CU → 완전 제외 (success_probability=0)
- **restricted**: RU, BY, VE, MM, AF → 경고 + 점수 페널티
- `config/export_blocklist.json`: 블랙리스트 설정 파일
- `backend/utils/compliance.py`: ComplianceChecker 구현

### 6. 결측치 처리 + 신뢰도 계산
- **No Zero Fill**: 0 대신 지역 평균/LOCF 사용
- **신뢰도 (0-1)**: 데이터 완전성, 소스 다양성, fallback 사용 여부 기반
- `backend/utils/missing_data.py`: MissingDataHandler 구현
- `backend/utils/confidence.py`: ConfidenceCalculator 구현

### 7. Explanation 필드 표준화
모든 API 응답에 일관된 `explanation` 필드 포함:
```json
{
  "explanation": {
    "kotra_status": "ok",
    "fallback_used": false,
    "confidence": 0.85,
    "data_coverage": {
      "missing_rate": 0.1,
      "missing_fields": ["growth_rate"],
      "imputation_methods": {"growth_rate": "region_avg"}
    },
    "warning": null,
    "interpretation": "높은 신뢰도"
  },
  "compliance": {
    "compliance_status": "ok",
    "reason": null,
    "score_penalty": 0,
    "warning": null
  }
}
```

## 📊 테스트 결과

```
pytest tests/ -v
========================= 29 passed in 0.83s =========================
```

| 테스트 모듈 | 테스트 수 | 상태 |
|------------|----------|------|
| test_recommendation.py | 8 | ✅ 통과 |
| test_matching.py | 10 | ✅ 통과 |
| test_simulation.py | 11 | ✅ 통과 |

## ⏳ 미완료 기능

1. [ ] 번역 채팅 API - API 선택 (Google/DeepL/Papago) 필요
2. [ ] 프론트엔드 대시보드 개발
3. [ ] Cloudflare Pages 배포

## 다음 권장 단계

1. 번역 API 선정 및 비용 분석
2. 프론트엔드 MVP 개발 (React + TailwindCSS)
3. 배포 환경 구성 (Cloudflare Pages/Workers)

## 라이선스

공공데이터포털 이용약관에 따름

---

**최종 업데이트**: 2026-01-26
**주요 개선**: Fallback 시스템, MOQ 고도화, 인증 매칭, 성공사례 보너스, 수출제한국 관리, 신뢰도 계산
