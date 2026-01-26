"""Recommendation Cache Module

TTL 기반 캐시로 KOTRA API 장애 시 최근 정상 응답을 반환합니다.
- 캐시 키: hs_prefix + exporter_country
- TTL: 14일
- 저장: 추천 결과 top20 + explanation 요약
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Default TTL: 14 days
DEFAULT_TTL_DAYS = 14


class RecommendationCache:
    """TTL 기반 추천 결과 캐시."""

    def __init__(self, cache_dir: Optional[str] = None, ttl_days: int = DEFAULT_TTL_DAYS):
        """캐시 초기화.

        Args:
            cache_dir: 캐시 저장 디렉토리 (기본: ./cache)
            ttl_days: 캐시 유효 기간 (일)
        """
        self.cache_dir = Path(cache_dir or os.getenv("CACHE_DIR", "./cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _make_key(self, hs_code: str, exporter_country: str = "KR") -> str:
        """캐시 키 생성.

        Args:
            hs_code: HS 코드 (4-6자리)
            exporter_country: 수출국 코드

        Returns:
            캐시 키 (해시)
        """
        hs_prefix = hs_code[:4] if hs_code else "0000"
        key_str = f"{hs_prefix}:{exporter_country}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def _get_cache_path(self, key: str) -> Path:
        """캐시 파일 경로 반환."""
        return self.cache_dir / f"rec_{key}.json"

    def get(
        self,
        hs_code: str,
        exporter_country: str = "KR"
    ) -> Optional[Dict[str, Any]]:
        """캐시에서 추천 결과 조회.

        Args:
            hs_code: HS 코드
            exporter_country: 수출국 코드

        Returns:
            캐시된 추천 결과 또는 None (만료/없음)
        """
        key = self._make_key(hs_code, exporter_country)

        # 1. 메모리 캐시 확인
        if key in self._memory_cache:
            cached = self._memory_cache[key]
            if self._is_valid(cached):
                logger.info(f"Cache hit (memory): {key}")
                return cached
            else:
                del self._memory_cache[key]

        # 2. 파일 캐시 확인
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)

                if self._is_valid(cached):
                    # 메모리 캐시에 로드
                    self._memory_cache[key] = cached
                    logger.info(f"Cache hit (file): {key}")
                    return cached
                else:
                    # 만료된 캐시 삭제
                    cache_path.unlink()
                    logger.info(f"Cache expired: {key}")
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        return None

    def set(
        self,
        hs_code: str,
        exporter_country: str,
        recommendations: List[Dict[str, Any]],
        explanation: Dict[str, Any]
    ) -> None:
        """추천 결과 캐시 저장.

        Args:
            hs_code: HS 코드
            exporter_country: 수출국 코드
            recommendations: 추천 결과 목록 (최대 20개 저장)
            explanation: 설명 요약
        """
        key = self._make_key(hs_code, exporter_country)

        cache_data = {
            "hs_code": hs_code,
            "exporter_country": exporter_country,
            "recommendations": recommendations[:20],  # 최대 20개
            "explanation": explanation,
            "cached_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=self.ttl_days)).isoformat()
        }

        # 메모리 캐시 저장
        self._memory_cache[key] = cache_data

        # 파일 캐시 저장
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache saved: {key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def _is_valid(self, cached: Dict[str, Any]) -> bool:
        """캐시 유효성 확인.

        Args:
            cached: 캐시 데이터

        Returns:
            유효 여부
        """
        expires_at = cached.get("expires_at")
        if not expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(expires_at)
            return datetime.utcnow() < expiry
        except Exception:
            return False

    def clear(self) -> int:
        """모든 캐시 삭제.

        Returns:
            삭제된 캐시 수
        """
        self._memory_cache.clear()

        count = 0
        for cache_file in self.cache_dir.glob("rec_*.json"):
            try:
                cache_file.unlink()
                count += 1
            except Exception:
                pass

        logger.info(f"Cache cleared: {count} entries")
        return count

    def cleanup_expired(self) -> int:
        """만료된 캐시 정리.

        Returns:
            삭제된 캐시 수
        """
        count = 0

        # 메모리 캐시 정리
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if not self._is_valid(v)
        ]
        for key in expired_keys:
            del self._memory_cache[key]
            count += 1

        # 파일 캐시 정리
        for cache_file in self.cache_dir.glob("rec_*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)

                if not self._is_valid(cached):
                    cache_file.unlink()
                    count += 1
            except Exception:
                pass

        if count > 0:
            logger.info(f"Expired cache cleanup: {count} entries")

        return count


# 싱글톤 인스턴스
_cache_instance: Optional[RecommendationCache] = None


def get_recommendation_cache() -> RecommendationCache:
    """RecommendationCache 싱글톤 반환."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RecommendationCache()
    return _cache_instance
