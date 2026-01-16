#!/bin/bash

# HS Code Export Analyzer - GCP 배포 스크립트
# 사용법: ./deploy-gcp.sh [environment]
# 예: ./deploy-gcp.sh production

set -e

ENVIRONMENT=${1:-staging}
GCP_PROJECT_ID=${GCP_PROJECT_ID:-your-project-id}
GCP_REGION=${GCP_REGION:-asia-northeast3}
GCR_HOSTNAME="gcr.io"
IMAGE_NAME="hs-code-analyzer"
CLOUD_RUN_SERVICE="hs-code-api-$ENVIRONMENT"

echo "======================================"
echo "HS Code Export Analyzer"
echo "GCP Cloud Run 배포"
echo "Environment: $ENVIRONMENT"
echo "Project: $GCP_PROJECT_ID"
echo "Region: $GCP_REGION"
echo "======================================"
echo ""

# gcloud CLI 확인
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI가 설치되어 있지 않습니다."
    echo "설치: https://cloud.google.com/sdk/install"
    exit 1
fi

echo "✅ gcloud CLI 확인됨"
echo ""

# 프로젝트 설정
echo "🔧 GCP 프로젝트 설정 중..."
gcloud config set project $GCP_PROJECT_ID

# 인증 확인
echo "🔐 GCP 인증 확인 중..."
gcloud auth list || {
    echo "❌ GCP 인증 실패. gcloud auth login을 실행하세요."
    exit 1
}
echo "✅ GCP 인증 성공"
echo ""

# API 활성화
echo "🔌 필요한 API 활성화 중..."
gcloud services enable \
    containerregistry.googleapis.com \
    run.googleapis.com \
    redis.googleapis.com \
    cloudbuild.googleapis.com \
    --project=$GCP_PROJECT_ID

# Docker 이미지 빌드
echo "🔨 Docker 이미지 빌드 중..."
IMAGE_URI="$GCR_HOSTNAME/$GCP_PROJECT_ID/$IMAGE_NAME:$ENVIRONMENT"

docker build -t $IMAGE_NAME:$ENVIRONMENT -f ../../Dockerfile ../..
docker tag $IMAGE_NAME:$ENVIRONMENT $IMAGE_URI

# GCR 인증
echo "🔐 Container Registry 인증 중..."
gcloud auth configure-docker

# 이미지 푸시
echo "⬆️  Docker 이미지 푸시 중..."
docker push $IMAGE_URI

echo "✅ 이미지 푸시 완료: $IMAGE_URI"
echo ""

# Cloud Run 배포
echo "🚀 Cloud Run 배포 중..."
gcloud run deploy $CLOUD_RUN_SERVICE \
    --image $IMAGE_URI \
    --platform managed \
    --region $GCP_REGION \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 1 \
    --max-instances 10 \
    --port 8000 \
    --set-env-vars "ENVIRONMENT=$ENVIRONMENT,LOG_LEVEL=info" \
    --project $GCP_PROJECT_ID

# 서비스 URL 가져오기
SERVICE_URL=$(gcloud run services describe $CLOUD_RUN_SERVICE \
    --platform managed \
    --region $GCP_REGION \
    --format 'value(status.url)' \
    --project $GCP_PROJECT_ID)

echo ""
echo "======================================"
echo "✅ GCP 배포 완료!"
echo "======================================"
echo ""
echo "📊 배포 정보:"
echo "  - Image: $IMAGE_URI"
echo "  - Service: $CLOUD_RUN_SERVICE"
echo "  - URL: $SERVICE_URL"
echo ""
echo "🔍 서비스 상태 확인:"
echo "  gcloud run services describe $CLOUD_RUN_SERVICE --region $GCP_REGION"
echo ""
echo "📝 로그 확인:"
echo "  gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$CLOUD_RUN_SERVICE\" --limit 50"
echo ""
echo "🌐 API 테스트:"
echo "  curl $SERVICE_URL/health"
echo ""
