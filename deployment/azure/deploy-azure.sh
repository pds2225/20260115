#!/bin/bash

# HS Code Export Analyzer - Azure 배포 스크립트
# 사용법: ./deploy-azure.sh [environment]
# 예: ./deploy-azure.sh production

set -e

ENVIRONMENT=${1:-staging}
AZURE_RESOURCE_GROUP="hs-code-$ENVIRONMENT-rg"
AZURE_LOCATION=${AZURE_LOCATION:-koreacentral}
ACR_NAME="hscodeacr$ENVIRONMENT"
APP_NAME="hs-code-api-$ENVIRONMENT"
PLAN_NAME="hs-code-plan-$ENVIRONMENT"

echo "======================================"
echo "HS Code Export Analyzer"
echo "Azure Container Apps 배포"
echo "Environment: $ENVIRONMENT"
echo "Location: $AZURE_LOCATION"
echo "======================================"
echo ""

# Azure CLI 확인
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI가 설치되어 있지 않습니다."
    echo "설치: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

echo "✅ Azure CLI 확인됨"
echo ""

# 인증 확인
echo "🔐 Azure 인증 확인 중..."
az account show || {
    echo "❌ Azure 인증 실패. az login을 실행하세요."
    exit 1
}
echo "✅ Azure 인증 성공"
echo ""

# 리소스 그룹 생성
echo "📦 리소스 그룹 생성 중..."
az group create \
    --name $AZURE_RESOURCE_GROUP \
    --location $AZURE_LOCATION

# Container Registry 생성
echo "📦 Container Registry 생성 중..."
az acr create \
    --resource-group $AZURE_RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Basic \
    --admin-enabled true

# ACR 로그인
echo "🔐 ACR 로그인 중..."
az acr login --name $ACR_NAME

# 이미지 빌드 및 푸시
echo "🔨 Docker 이미지 빌드 및 푸시 중..."
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
IMAGE_URI="$ACR_LOGIN_SERVER/hs-code-analyzer:$ENVIRONMENT"

az acr build \
    --registry $ACR_NAME \
    --image "hs-code-analyzer:$ENVIRONMENT" \
    --file ../../Dockerfile \
    ../..

echo "✅ 이미지 빌드 완료: $IMAGE_URI"
echo ""

# Redis Cache 생성
echo "💾 Redis Cache 생성 중..."
REDIS_NAME="hs-code-redis-$ENVIRONMENT"
az redis create \
    --resource-group $AZURE_RESOURCE_GROUP \
    --name $REDIS_NAME \
    --location $AZURE_LOCATION \
    --sku Basic \
    --vm-size c0 \
    --enable-non-ssl-port

# Redis 연결 정보 가져오기
REDIS_HOST=$(az redis show --name $REDIS_NAME --resource-group $AZURE_RESOURCE_GROUP --query hostName --output tsv)
REDIS_KEY=$(az redis list-keys --name $REDIS_NAME --resource-group $AZURE_RESOURCE_GROUP --query primaryKey --output tsv)

echo "✅ Redis 생성 완료"
echo ""

# App Service Plan 생성
echo "📋 App Service Plan 생성 중..."
az appservice plan create \
    --name $PLAN_NAME \
    --resource-group $AZURE_RESOURCE_GROUP \
    --location $AZURE_LOCATION \
    --is-linux \
    --sku B1

# Web App 생성
echo "🌐 Web App 생성 중..."
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

az webapp create \
    --resource-group $AZURE_RESOURCE_GROUP \
    --plan $PLAN_NAME \
    --name $APP_NAME \
    --deployment-container-image-name $IMAGE_URI

# Container Registry 설정
az webapp config container set \
    --name $APP_NAME \
    --resource-group $AZURE_RESOURCE_GROUP \
    --docker-custom-image-name $IMAGE_URI \
    --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
    --docker-registry-server-user $ACR_USERNAME \
    --docker-registry-server-password $ACR_PASSWORD

# 환경 변수 설정
echo "⚙️  환경 변수 설정 중..."
az webapp config appsettings set \
    --name $APP_NAME \
    --resource-group $AZURE_RESOURCE_GROUP \
    --settings \
        ENVIRONMENT=$ENVIRONMENT \
        REDIS_HOST=$REDIS_HOST \
        REDIS_PASSWORD=$REDIS_KEY \
        REDIS_PORT=6379 \
        LOG_LEVEL=info \
        WEBSITES_PORT=8000

# Application Insights 생성 (모니터링)
echo "📊 Application Insights 생성 중..."
INSIGHTS_NAME="hs-code-insights-$ENVIRONMENT"
az monitor app-insights component create \
    --app $INSIGHTS_NAME \
    --location $AZURE_LOCATION \
    --resource-group $AZURE_RESOURCE_GROUP \
    --application-type web

INSTRUMENTATION_KEY=$(az monitor app-insights component show \
    --app $INSIGHTS_NAME \
    --resource-group $AZURE_RESOURCE_GROUP \
    --query instrumentationKey \
    --output tsv)

az webapp config appsettings set \
    --name $APP_NAME \
    --resource-group $AZURE_RESOURCE_GROUP \
    --settings \
        APPINSIGHTS_INSTRUMENTATIONKEY=$INSTRUMENTATION_KEY

# 웹앱 시작
echo "🚀 웹앱 시작 중..."
az webapp start \
    --name $APP_NAME \
    --resource-group $AZURE_RESOURCE_GROUP

# URL 가져오기
APP_URL="https://$(az webapp show --name $APP_NAME --resource-group $AZURE_RESOURCE_GROUP --query defaultHostName --output tsv)"

echo ""
echo "======================================"
echo "✅ Azure 배포 완료!"
echo "======================================"
echo ""
echo "📊 배포 정보:"
echo "  - Resource Group: $AZURE_RESOURCE_GROUP"
echo "  - App Name: $APP_NAME"
echo "  - URL: $APP_URL"
echo "  - Redis: $REDIS_HOST"
echo ""
echo "🔍 상태 확인:"
echo "  az webapp show --name $APP_NAME --resource-group $AZURE_RESOURCE_GROUP"
echo ""
echo "📝 로그 확인:"
echo "  az webapp log tail --name $APP_NAME --resource-group $AZURE_RESOURCE_GROUP"
echo ""
echo "🌐 API 테스트:"
echo "  curl $APP_URL/health"
echo ""
