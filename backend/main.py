"""Global Export Intelligence Platform - Main Application

FastAPI application integrating KOTRA Open APIs for:
- Country recommendation (/recommend)
- Export simulation (/simulate)
- Buyer-seller matching (/match)

KOTRA APIs integrated:
1. 수출유망추천정보 - ML-based export success prediction
2. 국가정보 - Country economic indicators
3. 상품DB - Product database and trends
4. 해외시장뉴스 - Overseas market news
5. 무역사기사례 - Trade fraud cases
6. 기업성공사례 - Company success cases
"""

import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Load .env file from project root
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import recommendation, simulation, matching
from .services.kotra_client import get_kotra_client
from .models.schemas import HealthResponse, APIInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Global Export Intelligence Platform...")
    
    # Validate KOTRA API key
    api_key = os.getenv("KOTRA_SERVICE_KEY", "")
    if api_key:
        logger.info("KOTRA API key configured")
    else:
        logger.warning(
            "KOTRA_SERVICE_KEY not set. "
            "API calls will fail. "
            "Set environment variable or use .env file."
        )
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    client = get_kotra_client()
    await client.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns
    -------
    FastAPI
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Global Export Intelligence Platform API",
        description="""
## 글로벌 수출 인텔리전스 플랫폼

중소 수출기업을 위한 AI 기반 해외시장 진출 지원 플랫폼입니다.

### 주요 기능

1. **국가 추천 (/recommend)** 
   - HS코드 기반 유망 수출국 추천
   - KOTRA ML 모델 기반 성공확률 예측
   - 경제지표/트렌드 종합 분석

2. **성과 시뮬레이션 (/simulate)**
   - 타겟 국가별 예상 매출 시뮬레이션
   - 뉴스 기반 리스크 분석
   - 시장 점유율 추정

3. **바이어-셀러 매칭 (/match)**
   - FitScore 기반 파트너 매칭
   - 무역사기 리스크 분석
   - 성공사례 참고 제공

### KOTRA Open API 연동

- 수출유망추천정보 (ML 기반 예측)
- 국가정보 (경제지표)
- 상품DB (트렌드)
- 해외시장뉴스 (리스크)
- 무역사기사례 (리스크)
- 기업성공사례 (참고)

### 환경 설정

`KOTRA_SERVICE_KEY` 환경변수에 공공데이터포털 인증키를 설정하세요.
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {
                "name": "recommendation",
                "description": "유망 수출국 추천 API"
            },
            {
                "name": "simulation", 
                "description": "수출 성과 시뮬레이션 API"
            },
            {
                "name": "matching",
                "description": "바이어-셀러 매칭 API"
            },
            {
                "name": "health",
                "description": "서비스 상태 확인"
            }
        ]
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(
        recommendation, 
        prefix="/recommend", 
        tags=["recommendation"]
    )
    app.include_router(
        simulation, 
        prefix="/simulate", 
        tags=["simulation"]
    )
    app.include_router(
        matching, 
        prefix="/match", 
        tags=["matching"]
    )

    @app.get("/", response_model=APIInfo, tags=["health"])
    async def root():
        """Root endpoint - API information."""
        return APIInfo(
            name="Global Export Intelligence Platform",
            version="1.0.0",
            description="AI-powered export market recommendation platform",
            endpoints=[
                {"path": "/recommend", "method": "POST", "description": "국가 추천"},
                {"path": "/recommend/quick", "method": "GET", "description": "빠른 국가 추천"},
                {"path": "/simulate", "method": "POST", "description": "성과 시뮬레이션"},
                {"path": "/simulate/quick", "method": "GET", "description": "빠른 시뮬레이션"},
                {"path": "/match", "method": "POST", "description": "바이어-셀러 매칭"},
                {"path": "/match/seller", "method": "POST", "description": "셀러용 바이어 매칭"},
                {"path": "/match/buyer", "method": "POST", "description": "바이어용 셀러 매칭"},
            ],
            kotra_apis_integrated=[
                "수출유망추천정보",
                "국가정보",
                "상품DB",
                "해외시장뉴스",
                "무역사기사례",
                "기업성공사례"
            ]
        )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """Health check endpoint."""
        api_key_status = "configured" if os.getenv("KOTRA_SERVICE_KEY") else "missing"
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            services={
                "kotra_api": api_key_status,
                "recommendation": "available",
                "simulation": "available",
                "matching": "available"
            }
        )

    return app


# Create app instance
app = create_app()


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
