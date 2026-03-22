#!/bin/bash
# VALUE-UP AI — GitHub Push 스크립트
# 사용법: ./push_to_github.sh YOUR_GITHUB_TOKEN

TOKEN=$1
if [ -z "$TOKEN" ]; then
    echo "❌ 사용법: ./push_to_github.sh YOUR_GITHUB_TOKEN"
    echo "   토큰 발급: https://github.com/settings/tokens → repo 권한 체크"
    exit 1
fi

cd "$(dirname "$0")"
git remote set-url origin https://${TOKEN}@github.com/pds2225/20260115.git
git push origin main --force
echo "✅ GitHub 업로드 완료!"
echo "   확인: https://github.com/pds2225/20260115"
