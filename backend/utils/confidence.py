"""Confidence Calculator Module

결과의 신뢰도를 0-1 사이 값으로 계산합니다.
- 필수 피처 결측률 기반 (예: missing 30% → 0.7)
- 데이터 소스 다양성
- fallback 사용 여부
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceBreakdown:
    """신뢰도 구성 요소."""
    base_score: float
    data_completeness: float
    source_diversity: float
    fallback_penalty: float
    total: float


class ConfidenceCalculator:
    """결과 신뢰도 계산기."""

    # 가중치
    WEIGHTS = {
        "data_completeness": 0.50,  # 데이터 완전성
        "source_diversity": 0.30,   # 소스 다양성
        "fallback_penalty": 0.20    # fallback 패널티
    }

    # 기본 점수
    BASE_SCORE = 0.5

    # 필수 필드 정의
    REQUIRED_FIELDS = {
        "recommendation": [
            "success_score", "country_code", "country_name",
            "gdp", "growth_rate", "risk_grade"
        ],
        "simulation": [
            "market_size", "success_probability", "gdp",
            "growth_rate", "news_risk"
        ],
        "matching": [
            "fit_score", "hs_code", "country",
            "price_range", "moq"
        ]
    }

    # 데이터 소스 목록
    DATA_SOURCES = [
        "KOTRA 수출유망추천정보",
        "KOTRA 국가정보",
        "KOTRA 상품DB",
        "KOTRA 해외시장뉴스",
        "KOTRA 무역사기사례",
        "KOTRA 기업성공사례"
    ]

    def __init__(self):
        """계산기 초기화."""
        pass

    def calculate(
        self,
        context: str,
        missing_fields: List[str],
        data_sources_used: List[str],
        fallback_used: bool = False,
        kotra_status: str = "ok"
    ) -> tuple[float, Dict[str, Any]]:
        """신뢰도 계산.

        Args:
            context: 컨텍스트 (recommendation, simulation, matching)
            missing_fields: 결측 필드 목록
            data_sources_used: 사용된 데이터 소스
            fallback_used: fallback 사용 여부
            kotra_status: KOTRA API 상태 ("ok" 또는 "unavailable")

        Returns:
            (신뢰도 점수 0-1, 상세 breakdown)
        """
        required = self.REQUIRED_FIELDS.get(context, [])

        # 1. 데이터 완전성 (결측률 기반)
        if required:
            missing_count = sum(1 for f in missing_fields if f in required)
            completeness = 1.0 - (missing_count / len(required))
        else:
            completeness = 1.0

        # 2. 소스 다양성
        if data_sources_used:
            source_count = len([s for s in data_sources_used if s in self.DATA_SOURCES])
            diversity = min(1.0, source_count / 4)  # 4개 이상이면 100%
        else:
            diversity = 0.2  # 최소값

        # 3. Fallback 패널티
        fallback_score = 1.0
        if fallback_used:
            fallback_score = 0.5  # fallback 사용 시 50% 감점
        if kotra_status == "unavailable":
            fallback_score *= 0.7  # API 장애 시 추가 30% 감점

        # 가중 합계
        weighted_sum = (
            completeness * self.WEIGHTS["data_completeness"] +
            diversity * self.WEIGHTS["source_diversity"] +
            fallback_score * self.WEIGHTS["fallback_penalty"]
        )

        # 최종 신뢰도 (0.1 ~ 1.0)
        confidence = max(0.1, min(1.0, weighted_sum))

        breakdown = {
            "confidence": round(confidence, 3),
            "data_completeness": round(completeness, 3),
            "source_diversity": round(diversity, 3),
            "fallback_penalty": round(1.0 - fallback_score, 3),
            "missing_fields": missing_fields,
            "data_sources_count": len(data_sources_used),
            "fallback_used": fallback_used,
            "kotra_status": kotra_status,
            "interpretation": self._interpret_confidence(confidence)
        }

        return confidence, breakdown

    def calculate_from_missing_rate(
        self,
        missing_rate: float,
        fallback_used: bool = False,
        kotra_status: str = "ok"
    ) -> float:
        """결측률 기반 간단 계산.

        Args:
            missing_rate: 결측률 (0-1)
            fallback_used: fallback 사용 여부
            kotra_status: KOTRA API 상태

        Returns:
            신뢰도 (0-1)
        """
        # 기본: 1 - 결측률
        base = 1.0 - missing_rate

        # fallback 패널티
        if fallback_used:
            base *= 0.7

        # API 장애 패널티
        if kotra_status == "unavailable":
            base *= 0.8

        return max(0.1, min(1.0, base))

    def _interpret_confidence(self, confidence: float) -> str:
        """신뢰도 해석.

        Args:
            confidence: 신뢰도 점수

        Returns:
            해석 문자열
        """
        if confidence >= 0.9:
            return "매우 높음 - 신뢰할 수 있는 결과"
        elif confidence >= 0.7:
            return "높음 - 참고 가능한 결과"
        elif confidence >= 0.5:
            return "보통 - 일부 데이터 부족"
        elif confidence >= 0.3:
            return "낮음 - 추가 검토 필요"
        else:
            return "매우 낮음 - 주의 필요, 근거 빈약"

    def get_confidence_warning(self, confidence: float) -> Optional[str]:
        """낮은 신뢰도 경고 메시지.

        Args:
            confidence: 신뢰도 점수

        Returns:
            경고 메시지 또는 None
        """
        if confidence < 0.3:
            return "경고: 데이터 부족으로 결과의 신뢰도가 매우 낮습니다. 추가 검토가 필요합니다."
        elif confidence < 0.5:
            return "주의: 일부 핵심 데이터가 누락되어 결과 신뢰도가 제한적입니다."
        return None
