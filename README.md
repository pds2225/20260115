# 글로벌 수출 인텔리전스 플랫폼

중소 수출기업을 위한 AI 기반 해외시장 진출 지원 플랫폼입니다.

## 프로젝트 개요

- **목표**: KOTRA Open API 6종을 활용한 수출 인텔리전스 서비스
- **대상**: 해외시장 진출을 희망하는 중소 수출기업
- **기술스택**: FastAPI + Python 3.11 + httpx

## 주요 기능

### 1. 국가 추천 API (`/recommend`)
HS코드 기반 유망 수출국 추천

**KOTRA API 연동:**
- 수출유망추천정보 (ML 기반 예측, 40%)
- 국가정보 (경제지표, 25%)
- 상품DB (트렌드, 15%)
- 리스크등급 (20%)

**엔드포인트:**
- `POST /recommend` - 상세 국가 추천
- `GET /recommend/quick?hs_code=330499&top_n=5` - 빠른 추천

### 2. 성과 시뮬레이션 API (`/simulate`)
타겟 국가별 예상 매출 시뮬레이션

**KOTRA API 연동:**
- 수출유망추천정보 (성공확률)
- 국가정보 (경제지표)
- 해외시장뉴스 (리스크 보정)

**엔드포인트:**
- `POST /simulate` - 상세 시뮬레이션
- `GET /simulate/quick?hs_code=330499&country=US&price=10&moq=1000` - 빠른 시뮬레이션

### 3. 바이어-셀러 매칭 API (`/match`)
FitScore 기반 파트너 매칭

**KOTRA API 연동:**
- 무역사기사례 (리스크 평가)
- 기업성공사례 (참고 사례)

**FitScore 계산 (0-100):**
- 기본: 50점
- HS코드 매칭: +20점
- 가격 호환: +15점
- MOQ 호환: +10점
- 인증 매칭: +5점/개 (최대 +15점)
- 무역사기 리스크: -15~0점
- 성공사례 보너스: +5점

**엔드포인트:**
- `POST /match` - 상세 매칭
- `POST /match/seller` - 셀러용 바이어 매칭
- `POST /match/buyer` - 바이어용 셀러 매칭

## KOTRA API 스펙 요약

| API | 엔드포인트 | 주요 필드 |
|-----|-----------|----------|
| 수출유망추천정보 | /B410001/export-recommend-info | HSCD, NAT_NAME, EXP_BHRC_SCR |
| 국가정보 | /B410001/kotra_nationalInformation/natnInfo/natnInfo | natnNm, gdp, growth_rate, risk_grade |
| 상품DB | /B410001/cmmdtDb/cmmdtDb | natn, newsTitl, cmdltNmKorn, hsCdNm |
| 해외시장뉴스 | /B410001/kotra_overseasMarketNews/ovseaMrktNews | natNm, title, cntnt, wrtDt |
| 무역사기사례 | /B410001/cmmrcFraudCase/cmmrcFraudCase | natNm, title, fraudTypNm, prvntMthd |
| 기업성공사례 | /B410001/compSucsCase/compSucsCase | natNm, corpNm, indutyNm, entryTypNm |

## 설치 및 실행

### 1. 환경 설정
```bash
# 저장소 클론 후 디렉토리 이동
cd webapp

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# .env 파일에 KOTRA API 키 설정
KOTRA_SERVICE_KEY=your_api_key_here
```

### 3. 서버 실행
```bash
# 개발 모드
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 모드
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 4. API 테스트
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 프로젝트 구조

```
webapp/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI 앱 엔트리포인트
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── recommendation.py  # /recommend 라우터
│   │   ├── simulation.py      # /simulate 라우터
│   │   └── matching.py        # /match 라우터
│   ├── services/
│   │   ├── __init__.py
│   │   ├── kotra_client.py         # KOTRA API 클라이언트 (6종 통합)
│   │   ├── recommendation_service.py
│   │   ├── simulation_service.py
│   │   └── matching_service.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic 모델 정의
│   └── database/
│       ├── __init__.py
│       └── database.py        # 예제 데이터 (인메모리)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## API 사용 예시

### 국가 추천 요청
```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "hs_code": "330499",
    "current_export_countries": ["JP"],
    "goal": "new_market",
    "top_n": 5
  }'
```

### 시뮬레이션 요청
```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "hs_code": "330499",
    "target_country": "US",
    "price_per_unit": 10.0,
    "moq": 1000,
    "annual_capacity": 50000
  }'
```

### 매칭 요청
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{
    "profile_type": "seller",
    "profile": {
      "hs_code": "330499",
      "country": "KR",
      "price_range": [5.0, 8.0],
      "moq": 1000,
      "certifications": ["FDA", "ISO"]
    },
    "top_n": 10
  }'
```

## 배포 상태

- **플랫폼**: 로컬 개발 환경
- **상태**: 개발 중
- **API 키 필요**: KOTRA_SERVICE_KEY (공공데이터포털 발급)

## 다음 단계

1. [ ] API 키 발급 및 테스트 실행
2. [ ] Cloudflare Pages/Workers 배포
3. [ ] 프론트엔드 대시보드 개발
4. [ ] 실제 데이터 기반 튜닝

## 라이선스

공공데이터포털 이용약관에 따름

---

최종 업데이트: 2026-01-23
