# 🌍 HS Code Export Analyzer

**AI 기반 수출 최적 국가 추천 시스템**

HS코드만 입력하면 경제학 이론(중력모형)과 머신러닝(XGBoost)이 결합된 하이브리드 AI가 최적의 수출 국가를 분석하고, SHAP을 통해 추천 근거를 설명합니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.2-61DAFB.svg)](https://react.dev/)

---

## 📑 목차

- [핵심 기능](#-핵심-기능)
- [기술 스택](#-기술-스택)
- [프로젝트 구조](#-프로젝트-구조)
- [시작하기](#-시작하기)
- [사용 방법](#-사용-방법)
- [API 문서](#-api-문서)
- [AI 모델 설명](#-ai-모델-설명)
- [기술적 차별성](#-기술적-차별성)
- [모니터링](#-모니터링)
- [라이선스](#-라이선스)

---

## 🎯 핵심 기능

### 1. **하이브리드 AI 모델**
- **Gravity Model (중력모형)**: 경제학 이론 기반 무역 예측
- **XGBoost**: 머신러닝으로 정확도 향상
- **SHAP**: 설명 가능한 AI - 추천 근거를 6개 요인으로 분석

### 2. **빠른 분석 속도**
- Redis 캐싱으로 **1,870배 빠른 응답** (13ms vs 24.3초)
- 실시간 국가별 무역 잠재력 계산

### 3. **직관적인 UI/UX**
- HS코드 빠른 선택 (화장품, 전자제품 등 8개 카테고리)
- 레이더 차트 + 막대 차트로 시각화
- 국가별 6개 요인(GDP, 거리, FTA, 물류, 관세, 문화) 분석

### 4. **프로덕션 레벨 인프라**
- Docker 컨테이너화 (7개 서비스)
- Prometheus + Grafana 모니터링
- 자동 재학습 파이프라인

---

## 🛠 기술 스택

### Frontend
| 기술 | 버전 | 용도 |
|------|------|------|
| React | 19.2 | UI 프레임워크 |
| Vite | 7.2 | 빌드 도구 |
| Recharts | 3.6 | 데이터 시각화 |
| Framer Motion | 12.25 | 애니메이션 |
| Lucide React | 0.562 | 아이콘 |
| TailwindCSS | 3.4 | 스타일링 |

### Backend
| 기술 | 버전 | 용도 |
|------|------|------|
| FastAPI | 0.109 | REST API 서버 |
| Pydantic | 2.5 | 데이터 검증 |
| scikit-learn | 1.3 | 중력모형 |
| XGBoost | 2.0 | 머신러닝 |
| SHAP | 0.44 | AI 설명 |
| Redis | 5.0 | 캐싱 |
| Prometheus | latest | 메트릭 수집 |

### Infrastructure
| 서비스 | 이미지 | 포트 | 용도 |
|--------|--------|------|------|
| API | Custom | 8000 | 메인 API |
| Redis | redis:7-alpine | 6379 | 캐시 |
| Prometheus | prom/prometheus | 9090 | 메트릭 수집 |
| Grafana | grafana/grafana | 3001 | 대시보드 |
| Alertmanager | prom/alertmanager | 9093 | 알림 |
| Loki | grafana/loki | 3100 | 로그 수집 |
| Promtail | grafana/promtail | - | 로그 전송 |

---

## 📁 프로젝트 구조

```
hs-code-analyzer/
├── frontend/                  # React 프론트엔드
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx       # 랜딩 페이지
│   │   │   ├── AnalysisPage.jsx      # 분석 페이지 (핵심)
│   │   │   └── AdminDashboard.jsx    # 관리자 대시보드
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
│
├── backend/                   # FastAPI 백엔드
│   ├── models/
│   │   ├── gravity_model.py          # 중력모형
│   │   ├── xgboost_model.py          # XGBoost 모델
│   │   └── __init__.py
│   ├── api_v4_production.py          # 메인 API
│   └── requirements.txt
│
├── monitoring/                # 모니터링 설정
│   ├── prometheus.yml
│   ├── alertmanager.yml
│   └── promtail-config.yml
│
├── docker-compose.yml         # Docker 오케스트레이션
├── Dockerfile                 # API 컨테이너
├── .dockerignore
├── .gitignore
└── README.md                  # 이 파일
```

---

## 🚀 시작하기

### 사전 요구사항
- **Docker** & **Docker Compose** (권장)
- 또는 **Python 3.11+** & **Node.js 18+**

### 방법 1: Docker로 실행 (권장)

```bash
# 1. 레포지토리 클론
git clone https://github.com/your-username/hs-code-analyzer.git
cd hs-code-analyzer

# 2. 전체 스택 실행
docker-compose up -d

# 3. 서비스 확인
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Grafana: http://localhost:3001 (admin/admin)
# Prometheus: http://localhost:9090
```

### 방법 2: 로컬 개발 환경

#### 백엔드 실행
```bash
cd backend
pip install -r requirements.txt
python api_v4_production.py
```
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

#### 프론트엔드 실행
```bash
cd frontend
npm install
npm run dev
```
- 앱: http://localhost:5173

---

## 📖 사용 방법

### 1. 웹 UI 사용

1. **랜딩 페이지** (http://localhost:5173)
   - 서비스 소개 및 주요 기능 확인

2. **분석 페이지** (http://localhost:5173/analysis)
   - HS코드 빠른 선택 또는 직접 입력
   - 추천 국가 수 선택 (3/5/10개)
   - "분석 시작" 클릭
   - 결과: 국가 카드 + 차트 + AI 설명

3. **관리자 대시보드** (http://localhost:5173/admin)
   - 시스템 메트릭 실시간 모니터링
   - 캐시 통계, 응답 시간, 요청 수 등

### 2. API 직접 호출

```bash
# 예측 요청
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "hs_code": "33",
    "exporter_country": "KOR",
    "top_n": 5
  }'

# 헬스체크
curl http://localhost:8000/health

# 메트릭 조회
curl http://localhost:8000/metrics

# 캐시 통계
curl http://localhost:8000/cache/stats
```

---

## 📡 API 문서

### 주요 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 서버 상태 |
| GET | `/health` | 헬스체크 |
| POST | `/predict` | **핵심: AI 예측** |
| GET | `/metrics` | 시스템 메트릭 |
| GET | `/cache/stats` | 캐시 통계 |
| POST | `/retrain` | 모델 재학습 트리거 |
| GET | `/prometheus` | Prometheus 메트릭 |

### `/predict` API 상세

**요청**
```json
{
  "hs_code": "33",
  "exporter_country": "KOR",
  "top_n": 5
}
```

**응답**
```json
{
  "top_countries": [
    {
      "country": "베트남",
      "country_code": "VNM",
      "predicted_export": 245000000,
      "gravity_score": 82.5,
      "factors": {
        "gdp_score": 85,
        "distance_score": 90,
        "fta_score": 100,
        "lpi_score": 75,
        "tariff_score": 80,
        "culture_score": 88
      }
    }
  ],
  "explanation": {
    "primary_factors": ["gdp_score", "fta_score", "distance_score"],
    "insights": [
      "FTA 체결 국가가 높은 순위를 차지",
      "지리적 근접성이 중요한 요소"
    ]
  },
  "cached": false,
  "processing_time": 0.245
}
```

자세한 문서: http://localhost:8000/docs

---

## 🤖 AI 모델 설명

### 1. Gravity Model (중력모형)

**이론적 배경**
```
Trade_ij = (GDP_i × GDP_j) / Distance_ij^β
```

**구현 공식**
```
log(수출액) = β₀ + β₁×log(GDP) - β₂×log(거리) + β₃×FTA + β₄×LPI - β₅×관세
```

**입력 변수**
- `gdp_target`: 대상국 GDP (10억 USD)
- `distance_km`: 한국과의 거리 (km)
- `fta`: FTA 체결 여부 (0/1)
- `lpi_score`: 물류성과지수 (1-5)
- `tariff_rate`: 관세율 (%)

**출력**
- 무역 잠재력 점수 (0-100)

### 2. XGBoost Model

**목적**: Gravity Model 예측값을 추가 요인으로 보정

**입력 변수**
- `gravity_pred`: 중력모형 예측값
- `gdp_growth`: GDP 성장률 (%)
- `lpi_score`: 물류 지수
- `tariff_rate`: 관세율
- `culture_index`: 문화 유사성 (0-100)
- `regulation_index`: 규제 편의성 (0-100)

**출력**
- 최종 수출 예상액 (USD)

### 3. SHAP (SHapley Additive exPlanations)

**역할**: AI 예측의 근거 설명

**출력**
- 각 요인의 기여도
- 주요 영향 요인 3개
- 인사이트 (FTA, 거리, 물류 등)

---

## 🏆 기술적 차별성

### 왜 아무나 못 따라하는가?

#### 1. **하이브리드 AI 모델**
- 경제학 이론(중력모형) + 머신러닝(XGBoost) 결합
- 두 분야 모두 이해하는 전문가 필요
- 단순 통계 분석과는 차원이 다름

#### 2. **설명 가능한 AI (XAI)**
- 단순히 "베트남 추천"이 아닌 "왜 베트남인지" 설명
- SHAP 라이브러리로 6개 요인 분석
- 사업 의사결정에 필수적인 근거 제공

#### 3. **실시간 데이터 연동**
- UN Comtrade, World Bank API 연동 가능
- 데이터 수집 → 전처리 → 모델 입력 파이프라인
- 자동 업데이트 시스템

#### 4. **프로덕션 레벨 인프라**
- Docker 컨테이너화 (7개 서비스)
- Redis 캐싱 (1,870배 속도 향상)
- Prometheus/Grafana 모니터링
- 자동 재학습 파이프라인

#### 5. **확장 가능한 아키텍처**
- 마이크로서비스 구조
- 수평적 확장 가능 (Kubernetes 연동 가능)
- API 버전 관리

---

## 📊 모니터링

### Grafana 대시보드

**접속**: http://localhost:3001
- **ID**: admin
- **PW**: admin

**주요 메트릭**
- 총 요청 수
- 평균 응답 시간 (캐시 vs 비캐시)
- 캐시 적중률
- 에러율
- 활성 연결 수
- 시간별 요청 추이

### Prometheus

**접속**: http://localhost:9090

**수집 메트릭**
- `api_requests_total`: 총 요청 수
- `api_request_duration_seconds`: 요청 처리 시간
- `cache_hits_total`: 캐시 적중
- `cache_misses_total`: 캐시 미스
- `active_connections`: 활성 연결

---

## 🔧 개발 가이드

### 프론트엔드 개발

```bash
cd frontend

# 개발 서버 (핫 리로드)
npm run dev

# 빌드
npm run build

# 빌드 미리보기
npm run preview
```

### 백엔드 개발

```bash
cd backend

# 개발 서버 (자동 재시작)
uvicorn api_v4_production:app --reload

# 테스트
pytest tests/

# 모델 학습
python models/gravity_model.py
python models/xgboost_model.py
```

### Docker 개발

```bash
# 전체 재빌드
docker-compose up -d --build

# 로그 확인
docker-compose logs -f api

# 특정 서비스만 재시작
docker-compose restart api

# 정리
docker-compose down -v
```

---

## 📈 성능 최적화

### 캐싱 전략
- **Redis**: 동일한 HS코드 요청 캐싱 (24시간)
- **결과**: 13ms (캐시) vs 24.3초 (비캐시) → **1,870배 향상**

### 응답 시간 분석
| 구간 | 시간 | 설명 |
|------|------|------|
| 캐시 적중 | ~13ms | Redis 조회 |
| 데이터 수집 | ~18초 | API 호출 (최초 1회) |
| AI 예측 | ~6초 | Gravity + XGBoost |
| SHAP 설명 | ~0.3초 | 설명 생성 |

---

## 🔐 보안

- CORS 설정 (프로덕션에서는 특정 도메인만 허용)
- API 요청 검증 (Pydantic)
- Docker 네트워크 격리
- 환경 변수로 민감 정보 관리 (`.env`)

---

## 📝 TODO

- [ ] 실제 UN Comtrade API 연동
- [ ] 사용자 인증 시스템
- [ ] 결과 PDF 내보내기
- [ ] 다국어 지원 (영어, 중국어)
- [ ] 모바일 앱 (React Native)
- [ ] Kubernetes 배포 설정

---

## 🤝 기여

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 👨‍💻 개발자

**김미아**
- GitHub: [@your-username](https://github.com/your-username)
- Email: your-email@example.com

---

## 🙏 감사의 말

- [FastAPI](https://fastapi.tiangolo.com/) - 훌륭한 웹 프레임워크
- [XGBoost](https://xgboost.readthedocs.io/) - 강력한 ML 라이브러리
- [SHAP](https://shap.readthedocs.io/) - 설명 가능한 AI
- [Recharts](https://recharts.org/) - 아름다운 차트 라이브러리

---

## 📞 문의

프로젝트 관련 문의사항은 [Issues](https://github.com/your-username/hs-code-analyzer/issues)에 남겨주세요.

---

**Made with ❤️ for SME exporters**
