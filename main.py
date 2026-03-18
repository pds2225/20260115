"""VALUE-UP AI — FastAPI 메인 앱"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.router import router

app = FastAPI(
    title="VALUE-UP AI — 데이터 기반 바이어 검증 및 자동화 워크플로우",
    description="""
## HS코드 분석부터 맞춤형 컨택까지, 전 과정 자동화로 효율성 극대화

### 5단계 파이프라인
1. **Step 1: HS코드 분석** — 품목 분류 및 시장 매핑 (Volza ETL)
2. **Step 2: 거래 이력 필터링** — 최근 6개월 내 활성 바이어, 최소 5회 수입 실적
3. **Step 3: 바이어 검증** — 신용도·거래규모 검증 + 베트남 법인 실사 (ERC·Tax ID·법적상태)
4. **Step 4: 연락처 확보** — 의사결정권자 직접 연락처 (Hunter.io + Apollo.io)
5. **Step 5: 맞춤형 이메일 생성** — GPT-4o 기반 AI 개인화 컨택 + 현지 언어 자동 생성

### Key Differentiator
- 기존 방식: 수작업으로 2-3주 소요
- VALUE-UP AI: **전 과정 5분 이내 완료**
- 정확도: **95% 이상 검증된 연락처**
    """,
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["root"])
async def root():
    return {
        "message": "VALUE-UP AI Pipeline API",
        "docs": "/docs",
        "version": "1.0.0",
    }
