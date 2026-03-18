# VALUE-UP AI 4중 검증 바이어 매칭 플랫폼

> **AI·데이터 기반 수출 One-Stop 플랫폼 — 글로벌 바이어 4중 검증 + 아웃리치 이메일 자동화**
>
> 특허 출원 완료: 10-2026-0026207 (2026.02.10.)

---

## 🎯 한 줄 요약

HS코드 입력 → 10초 안에 검증된 해외 바이어 + 담당자 이메일 자동 확보

---

## ✅ 지금 당장 작동하는 것 (직접 확인 완료)

| 기능 | 상태 | 확인 근거 |
|------|------|-----------|
| Hunter.io 도메인 검색 | ✅ 작동 | wangfoodusa.com → 10명 이메일 즉시 확보 |
| Gmail SMTP 발송 | ✅ 작동 | ImportGenius·TradeInt·Panjiva 3개사 초안 실제 발송 |
| TradeImex 바이어 추출 | ✅ 작동 | 김치 수입업체 61개 → 상위 10개 확보 |
| KOTRA Open API | ✅ 작동 | HS 330499 기준 2,100건 실시간 수집 |
| 4중 파이프라인 E2E | ✅ 작동 | 루미에코스메틱/미국 테스트: 10→7개 통과, 15초 |

---

## ❌ 솔직한 GAP (현재 시뮬레이션 수준)

| 기능 | 현재 상태 | 실제 연동 조건 |
|------|-----------|---------------|
| Layer 2 신용검증 | CSV DB (Coface 수동) | `COFACE_API_KEY` 설정 시 전환 |
| Layer 3 세관 B/L | CSV Seed DB | `VOLZA_API_KEY` 설정 시 전환 |
| 담당자 DB | 패턴 추정 엔진 | `HUNTER_IO_API_KEY` 설정 시 실검증 |

---

## 🏗️ 아키텍처

```
POST /api/v1/pipeline/v2/run
        │
        ▼
FourLayerMatcher.run()
    ├── Step 1: HSCodeAnalyzer       → 세관 수입자 리스트 수집
    ├── Step 2: TradeHistoryFilter   → 활성 바이어 1차 추출
    │
    ├── [asyncio.gather 병렬 실행]
    │   ├── Layer 1: ActivityHistory    → 6개월 이내 거래 여부 (PASS/FAIL)
    │   ├── Layer 2: CreditVerifier     → 신용등급 A/B/C=PASS, D/E/X=FAIL
    │   ├── Layer 3: ImportVolume       → 월 수입금액 하한 + MOQ 필터
    │   └── Layer 4: DecisionMakerFinder → Hunter.io → Clay → 패턴 추정
    │
    ├── 4중 AND 필터                 → 4개 레이어 모두 PASS만 통과
    ├── FitScore™ 산출               → L1×40% + L2×30% + L3×20% + L4×10%
    └── Step 5: EmailGenerator       → 바이어별 맞춤 영업 이메일 생성
```

---

## 📁 프로젝트 구조

```
value_up_ai/
├── backend/
│   ├── api/
│   │   └── router.py              # FastAPI 라우터 (모든 엔드포인트)
│   ├── models/
│   │   └── schemas.py             # Pydantic 모델
│   └── services/
│       ├── four_layer_matcher.py  # 🎯 메인 오케스트레이터
│       ├── layer1_activity_history.py
│       ├── layer2_credit_verifier.py
│       ├── layer3_import_volume.py
│       ├── layer4_contact_finder.py  # Hunter.io 실연동 통합
│       │
│       ├── hunter_client.py       # ✅ Hunter.io API 실연동
│       ├── gmail_sender.py        # ✅ Gmail SMTP 실발송
│       ├── tradeimex_client.py    # ✅ TradeImex 바이어 추출
│       ├── matching_engine.py     # MOQ/인증 Hard Gate (Claude 레포)
│       ├── sanctions.py           # 제재국 필터 (ISO2/ISO3 양방향)
│       │
│       ├── hs_recommender.py      # 제품명 → HS코드 추천
│       ├── supported_countries.py # 지원 국가 목록
│       └── data_source_manager.py # 통합 데이터 소스 관리
│
├── data/
│   ├── buyer_db.csv               # 바이어 55개 (HS 6종 × 9개국)
│   ├── kotra_hs_country_recommend.csv  # KOTRA 2,100건
│   ├── country_credit_db.csv      # 23개국 신용등급
│   └── email_pattern_db.csv       # 이메일 패턴 12종
│
├── .env.example                   # 환경변수 설정 가이드
├── requirements.txt
└── main.py                        # FastAPI 앱 진입점
```

---

## 🚀 빠른 시작

### 1. 설치
```bash
git clone https://github.com/pds2225/20260115.git
cd 20260115
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일 편집 → Hunter.io 키, Gmail 앱 비밀번호 입력
```

### 3. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

### 4. API 문서
```
http://localhost:8000/docs
```

---

## 🔑 핵심 API 엔드포인트

| 엔드포인트 | 기능 |
|-----------|------|
| `POST /api/v1/pipeline/v2/run` | 🎯 4중 검증 파이프라인 메인 |
| `POST /api/v1/hunter/search` | ✅ Hunter.io 도메인 검색 |
| `POST /api/v1/gmail/send` | ✅ Gmail 이메일 발송 |
| `POST /api/v1/outreach/batch` | 🚀 바이어 전체 일괄 발송 |
| `GET  /api/v1/hs/recommend` | HS코드 추천 |
| `GET  /api/v1/countries` | 지원 국가 목록 |
| `GET  /api/v1/data-sources/status` | 데이터 소스 현황 |

---

## 📊 FitScore™ 산출 기준

```
FitScore = Layer1 × 40% + Layer2 × 30% + Layer3 × 20% + Layer4 × 10%

Layer 1 (활동 이력)  : 6개월 이내 거래 PASS/FAIL
Layer 2 (신용등급)   : A/B/C = PASS, D/E/X = FAIL (D·E·X 자동 차단)
Layer 3 (수입 규모)  : 월 수입금액 하한 + MOQ 충족 여부
Layer 4 (담당자)     : 이메일 3중 검증 (패턴 + DNS MX + SMTP)

FitGrade: S(90+) / A(80-89) / B(70-79) / C(60-69) / D(-60)
```

---

## 🔌 데이터 소스 연동 현황

| 소스 | 현재 방식 | 키 설정 시 |
|------|----------|------------|
| 바이어 DB | CSV Seed (55개) | Volza/ImportGenius 실시간 전환 |
| 국가 추천 | **KOTRA 실시간** | 이미 연동됨 |
| 이메일 | 패턴 추정 엔진 | Hunter.io 실검증 전환 |
| 신용등급 | CSV (23개국) | Coface API 전환 |

---

## 📌 출처 및 라이선스

- Claude 레포 통합: `matching_engine.py`, `sanctions.py`  
  출처: github.com/pds2225/20260115 (genspark_ai_developer 브랜치)
- VALUE-UP AI 4중 파이프라인: Skywork Agent 개발
- 특허: 10-2026-0026207 (2026.02.10.)
