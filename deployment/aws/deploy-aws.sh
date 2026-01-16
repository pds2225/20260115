#!/bin/bash

# HS Code Export Analyzer - AWS 배포 스크립트
# 사용법: ./deploy-aws.sh [environment]
# 예: ./deploy-aws.sh production

set -e

ENVIRONMENT=${1:-staging}
AWS_REGION=${AWS_REGION:-ap-northeast-2}
ECR_REPO_NAME="hs-code-analyzer"
ECS_CLUSTER_NAME="hs-code-cluster"
ECS_SERVICE_NAME="hs-code-service"

echo "======================================"
echo "HS Code Export Analyzer"
echo "AWS ECS 배포"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "======================================"
echo ""

# AWS CLI 확인
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI가 설치되어 있지 않습니다."
    echo "설치: https://aws.amazon.com/cli/"
    exit 1
fi

echo "✅ AWS CLI 확인됨"
echo ""

# AWS 인증 확인
echo "🔐 AWS 인증 확인 중..."
aws sts get-caller-identity || {
    echo "❌ AWS 인증 실패. aws configure를 실행하세요."
    exit 1
}
echo "✅ AWS 인증 성공"
echo ""

# ECR 로그인
echo "🔐 ECR 로그인 중..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com

# ECR 리포지토리 생성 (없으면)
echo "📦 ECR 리포지토리 확인 중..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || {
    echo "📦 ECR 리포지토리 생성 중..."
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true
}

# 이미지 빌드
echo "🔨 Docker 이미지 빌드 중..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$ENVIRONMENT"

docker build -t $ECR_REPO_NAME:$ENVIRONMENT -f ../../Dockerfile ../..
docker tag $ECR_REPO_NAME:$ENVIRONMENT $IMAGE_URI

# 이미지 푸시
echo "⬆️  Docker 이미지 푸시 중..."
docker push $IMAGE_URI

echo "✅ 이미지 푸시 완료: $IMAGE_URI"
echo ""

# ECS 클러스터 생성 (없으면)
echo "🎯 ECS 클러스터 확인 중..."
aws ecs describe-clusters --clusters $ECS_CLUSTER_NAME --region $AWS_REGION 2>/dev/null | grep -q "ACTIVE" || {
    echo "🎯 ECS 클러스터 생성 중..."
    aws ecs create-cluster --cluster-name $ECS_CLUSTER_NAME --region $AWS_REGION
}

# Task Definition 등록
echo "📝 Task Definition 등록 중..."
TASK_FAMILY="hs-code-task-$ENVIRONMENT"

aws ecs register-task-definition \
    --family $TASK_FAMILY \
    --network-mode awsvpc \
    --requires-compatibilities FARGATE \
    --cpu 512 \
    --memory 1024 \
    --execution-role-arn arn:aws:iam::$ACCOUNT_ID:role/ecsTaskExecutionRole \
    --container-definitions "[
        {
            \"name\": \"hs-code-api\",
            \"image\": \"$IMAGE_URI\",
            \"portMappings\": [
                {
                    \"containerPort\": 8000,
                    \"protocol\": \"tcp\"
                }
            ],
            \"environment\": [
                {\"name\": \"ENVIRONMENT\", \"value\": \"$ENVIRONMENT\"},
                {\"name\": \"REDIS_HOST\", \"value\": \"redis.$ENVIRONMENT.local\"},
                {\"name\": \"LOG_LEVEL\", \"value\": \"info\"}
            ],
            \"logConfiguration\": {
                \"logDriver\": \"awslogs\",
                \"options\": {
                    \"awslogs-group\": \"/ecs/hs-code-$ENVIRONMENT\",
                    \"awslogs-region\": \"$AWS_REGION\",
                    \"awslogs-stream-prefix\": \"ecs\"
                }
            }
        }
    ]" \
    --region $AWS_REGION

# 서비스 배포
echo "🚀 ECS 서비스 배포 중..."
aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION 2>/dev/null | grep -q "ACTIVE" && {
    echo "🔄 기존 서비스 업데이트 중..."
    aws ecs update-service \
        --cluster $ECS_CLUSTER_NAME \
        --service $ECS_SERVICE_NAME \
        --task-definition $TASK_FAMILY \
        --force-new-deployment \
        --region $AWS_REGION
} || {
    echo "✨ 새 서비스 생성 중..."
    aws ecs create-service \
        --cluster $ECS_CLUSTER_NAME \
        --service-name $ECS_SERVICE_NAME \
        --task-definition $TASK_FAMILY \
        --desired-count 2 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
        --region $AWS_REGION
}

echo ""
echo "======================================"
echo "✅ AWS 배포 완료!"
echo "======================================"
echo ""
echo "📊 배포 정보:"
echo "  - Image: $IMAGE_URI"
echo "  - Cluster: $ECS_CLUSTER_NAME"
echo "  - Service: $ECS_SERVICE_NAME"
echo ""
echo "🔍 서비스 상태 확인:"
echo "  aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION"
echo ""
echo "📝 로그 확인:"
echo "  aws logs tail /ecs/hs-code-$ENVIRONMENT --follow --region $AWS_REGION"
echo ""
