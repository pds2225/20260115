#!/bin/bash

# HS Code Export Analyzer - 통합 배포 스크립트
# 사용법: ./deploy.sh

set -e

echo "======================================"
echo "HS Code Export Analyzer"
echo "통합 배포 스크립트"
echo "======================================"
echo ""
echo "배포할 클라우드 플랫폼을 선택하세요:"
echo "  1) AWS (ECS + Fargate)"
echo "  2) GCP (Cloud Run)"
echo "  3) Azure (Container Apps)"
echo "  4) 로컬 Docker"
echo "  5) 종료"
echo ""

read -p "선택 (1-5): " -n 1 -r
echo ""
echo ""

case $REPLY in
    1)
        echo "🚀 AWS 배포 시작..."
        cd deployment/aws
        ./deploy-aws.sh ${1:-staging}
        ;;
    2)
        echo "🚀 GCP 배포 시작..."
        cd deployment/gcp
        ./deploy-gcp.sh ${1:-staging}
        ;;
    3)
        echo "🚀 Azure 배포 시작..."
        cd deployment/azure
        ./deploy-azure.sh ${1:-staging}
        ;;
    4)
        echo "🐳 로컬 Docker 실행..."
        ./start-docker.sh
        ;;
    5)
        echo "👋 종료합니다."
        exit 0
        ;;
    *)
        echo "❌ 잘못된 선택입니다."
        exit 1
        ;;
esac

echo ""
echo "======================================"
echo "✅ 완료!"
echo "======================================"
