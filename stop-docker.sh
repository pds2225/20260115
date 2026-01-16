#!/bin/bash

# HS Code Export Analyzer - Docker 중지 스크립트
# 사용법: ./stop-docker.sh

set -e

echo "======================================"
echo "HS Code Export Analyzer"
echo "Docker 전체 스택 중지"
echo "======================================"
echo ""

# 옵션 선택
echo "중지 옵션을 선택하세요:"
echo "  1) 컨테이너만 중지 (데이터 유지)"
echo "  2) 컨테이너 + 볼륨 삭제 (완전 정리)"
echo ""
read -p "선택 (1 또는 2): " -n 1 -r
echo ""
echo ""

if [[ $REPLY == "2" ]]; then
    echo "🗑️  컨테이너 및 볼륨 완전 삭제 중..."
    docker-compose down -v
    echo "✅ 모든 데이터가 삭제되었습니다."
else
    echo "🛑 컨테이너 중지 중..."
    docker-compose down
    echo "✅ 컨테이너가 중지되었습니다. (데이터는 유지됨)"
fi

echo ""
echo "📊 남은 컨테이너:"
docker ps -a | grep "hs-code" || echo "  (없음)"

echo ""
echo "💾 남은 볼륨:"
docker volume ls | grep "20260115" || echo "  (없음)"

echo ""
echo "======================================"
echo "✅ 중지 완료!"
echo "======================================"
echo ""
echo "🔄 다시 시작하려면:"
echo "  ./start-docker.sh"
echo ""
