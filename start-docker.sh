#!/bin/bash

# HS Code Export Analyzer - Docker 실행 스크립트
# 사용법: ./start-docker.sh

set -e

echo "======================================"
echo "HS Code Export Analyzer"
echo "Docker 전체 스택 실행"
echo "======================================"
echo ""

# Docker 확인
if ! command -v docker &> /dev/null; then
    echo "❌ Docker가 설치되어 있지 않습니다."
    echo "Docker 설치: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose가 설치되어 있지 않습니다."
    echo "Docker Compose 설치: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker 및 Docker Compose 설치 확인됨"
echo ""

# 기존 컨테이너 정리 (선택)
read -p "기존 컨테이너를 정리하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 기존 컨테이너 정리 중..."
    docker-compose down -v
fi

# 이미지 빌드
echo "🔨 Docker 이미지 빌드 중..."
docker-compose build --no-cache

# 컨테이너 시작
echo "🚀 컨테이너 시작 중..."
docker-compose up -d

# 상태 확인
echo ""
echo "⏳ 서비스 시작 대기 중 (30초)..."
sleep 30

echo ""
echo "📊 컨테이너 상태:"
docker-compose ps

echo ""
echo "======================================"
echo "✅ 전체 스택이 성공적으로 시작되었습니다!"
echo "======================================"
echo ""
echo "📡 접속 가능한 서비스:"
echo "  - API:              http://localhost:8000"
echo "  - API Docs:         http://localhost:8000/docs"
echo "  - Prometheus:       http://localhost:9090"
echo "  - Grafana:          http://localhost:3001 (admin/admin)"
echo "  - Alertmanager:     http://localhost:9093"
echo ""
echo "📝 로그 확인:"
echo "  docker-compose logs -f api"
echo ""
echo "🛑 중지:"
echo "  docker-compose down"
echo ""
echo "🔄 재시작:"
echo "  docker-compose restart"
echo ""
