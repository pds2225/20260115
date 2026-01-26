"""Missing Data Handler Module

결측치 처리 표준화:
- 수치형: LOCF(최근값) 또는 지역/그룹 평균 대체
- 범주형: UNKNOWN 처리 + 보수 점수
- 리스트/텍스트: 빈 리스트 유지 + 최소 점수
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MissingFieldInfo:
    """결측 필드 정보."""
    field_name: str
    original_value: Any
    imputed_value: Any
    imputation_method: str
    is_critical: bool = False


class MissingDataHandler:
    """결측치 처리 핸들러."""

    # 지역별 기본값 (그룹 평균)
    REGION_DEFAULTS = {
        "asia": {
            "gdp": 1500.0,  # 10억 USD
            "growth_rate": 4.0,
            "inflation_rate": 3.0,
            "risk_grade": "B"
        },
        "europe": {
            "gdp": 2000.0,
            "growth_rate": 1.5,
            "inflation_rate": 2.5,
            "risk_grade": "A"
        },
        "americas": {
            "gdp": 3000.0,
            "growth_rate": 2.5,
            "inflation_rate": 3.5,
            "risk_grade": "B"
        },
        "middle_east": {
            "gdp": 500.0,
            "growth_rate": 3.0,
            "inflation_rate": 4.0,
            "risk_grade": "B"
        },
        "africa": {
            "gdp": 200.0,
            "growth_rate": 3.5,
            "inflation_rate": 6.0,
            "risk_grade": "C"
        },
        "default": {
            "gdp": 1000.0,
            "growth_rate": 2.5,
            "inflation_rate": 3.0,
            "risk_grade": "C"
        }
    }

    # 국가 → 지역 매핑
    COUNTRY_REGION_MAP = {
        # Asia
        "JP": "asia", "CN": "asia", "KR": "asia", "VN": "asia",
        "TH": "asia", "ID": "asia", "MY": "asia", "SG": "asia",
        "PH": "asia", "IN": "asia", "TW": "asia", "HK": "asia",
        # Europe
        "DE": "europe", "GB": "europe", "FR": "europe", "IT": "europe",
        "NL": "europe", "ES": "europe", "PL": "europe", "BE": "europe",
        # Americas
        "US": "americas", "CA": "americas", "MX": "americas", "BR": "americas",
        "AR": "americas", "CL": "americas", "CO": "americas",
        # Middle East
        "AE": "middle_east", "SA": "middle_east", "QA": "middle_east",
        "KW": "middle_east", "BH": "middle_east", "OM": "middle_east",
        # Africa
        "ZA": "africa", "EG": "africa", "NG": "africa", "KE": "africa",
    }

    # 필수 필드 목록 (confidence 계산에 사용)
    CRITICAL_FIELDS = {
        "recommendation": ["success_score", "country_code", "country_name"],
        "simulation": ["market_size", "success_probability", "gdp"],
        "matching": ["fit_score", "hs_code", "country"]
    }

    def __init__(self):
        """핸들러 초기화."""
        self._missing_log: List[MissingFieldInfo] = []

    def get_region(self, country_code: str) -> str:
        """국가 코드로 지역 반환.

        Args:
            country_code: ISO 2자리 국가 코드

        Returns:
            지역 코드 (asia, europe, americas, middle_east, africa, default)
        """
        return self.COUNTRY_REGION_MAP.get(country_code.upper(), "default")

    def impute_numeric(
        self,
        value: Optional[float],
        field_name: str,
        country_code: Optional[str] = None,
        fallback: float = 0.0
    ) -> tuple[float, str]:
        """수치형 결측치 대체.

        전략:
        1. 값이 있으면 그대로 반환
        2. 국가 코드 있으면 지역 평균 사용
        3. 그 외 fallback 사용

        Args:
            value: 원본 값 (None 가능)
            field_name: 필드명 (gdp, growth_rate 등)
            country_code: 국가 코드 (지역 기반 대체용)
            fallback: 최종 기본값

        Returns:
            (대체된 값, 대체 방법)
        """
        if value is not None and value != 0:
            return value, "original"

        # 지역 기반 대체
        if country_code:
            region = self.get_region(country_code)
            region_defaults = self.REGION_DEFAULTS.get(region, self.REGION_DEFAULTS["default"])
            if field_name in region_defaults:
                imputed = region_defaults[field_name]
                self._log_missing(field_name, value, imputed, f"region_avg:{region}", True)
                return imputed, f"region_avg:{region}"

        # 기본값 사용
        self._log_missing(field_name, value, fallback, "fallback", True)
        return fallback, "fallback"

    def impute_categorical(
        self,
        value: Optional[str],
        field_name: str,
        country_code: Optional[str] = None,
        fallback: str = "UNKNOWN"
    ) -> tuple[str, str]:
        """범주형 결측치 대체.

        Args:
            value: 원본 값
            field_name: 필드명
            country_code: 국가 코드
            fallback: 기본값

        Returns:
            (대체된 값, 대체 방법)
        """
        if value and value.strip():
            return value, "original"

        # 지역 기반 대체 (risk_grade 등)
        if country_code:
            region = self.get_region(country_code)
            region_defaults = self.REGION_DEFAULTS.get(region, self.REGION_DEFAULTS["default"])
            if field_name in region_defaults:
                imputed = region_defaults[field_name]
                self._log_missing(field_name, value, imputed, f"region_default:{region}", False)
                return imputed, f"region_default:{region}"

        self._log_missing(field_name, value, fallback, "unknown", False)
        return fallback, "unknown"

    def impute_list(
        self,
        value: Optional[List],
        field_name: str
    ) -> tuple[List, str]:
        """리스트 결측치 대체.

        Args:
            value: 원본 리스트
            field_name: 필드명

        Returns:
            (대체된 리스트, 대체 방법)
        """
        if value and len(value) > 0:
            return value, "original"

        self._log_missing(field_name, value, [], "empty_list", False)
        return [], "empty_list"

    def process_country_info(
        self,
        country_info: Dict[str, Any],
        country_code: str
    ) -> tuple[Dict[str, Any], Dict[str, str]]:
        """국가 정보 결측치 일괄 처리.

        Args:
            country_info: 원본 국가 정보
            country_code: 국가 코드

        Returns:
            (처리된 국가 정보, 대체 방법 맵)
        """
        processed = {}
        methods = {}

        # GDP
        processed["gdp"], methods["gdp"] = self.impute_numeric(
            country_info.get("gdp"),
            "gdp",
            country_code,
            1000.0
        )

        # 성장률
        processed["growth_rate"], methods["growth_rate"] = self.impute_numeric(
            country_info.get("growth_rate"),
            "growth_rate",
            country_code,
            2.0
        )

        # 인플레이션
        processed["inflation_rate"], methods["inflation_rate"] = self.impute_numeric(
            country_info.get("inflation_rate"),
            "inflation_rate",
            country_code,
            3.0
        )

        # 리스크 등급
        processed["risk_grade"], methods["risk_grade"] = self.impute_categorical(
            country_info.get("risk_grade"),
            "risk_grade",
            country_code,
            "C"
        )

        # 시장 특성 (텍스트)
        market_char = country_info.get("market_characteristics", "")
        processed["market_characteristics"] = market_char if market_char else "정보 없음"
        methods["market_characteristics"] = "original" if market_char else "default"

        # 유망 상품 (리스트)
        processed["promising_goods"], methods["promising_goods"] = self.impute_list(
            country_info.get("promising_goods"),
            "promising_goods"
        )

        return processed, methods

    def get_missing_rate(self, context: str = "recommendation") -> float:
        """결측률 계산.

        Args:
            context: 컨텍스트 (recommendation, simulation, matching)

        Returns:
            결측률 (0-1)
        """
        critical_fields = self.CRITICAL_FIELDS.get(context, [])
        if not critical_fields:
            return 0.0

        missing_count = sum(
            1 for log in self._missing_log
            if log.field_name in critical_fields and log.imputation_method != "original"
        )

        return missing_count / len(critical_fields)

    def get_missing_fields(self) -> List[str]:
        """결측 필드 목록 반환.

        Returns:
            결측 필드명 리스트
        """
        return [
            log.field_name
            for log in self._missing_log
            if log.imputation_method != "original"
        ]

    def get_data_coverage(self) -> Dict[str, Any]:
        """데이터 커버리지 요약 반환.

        Returns:
            커버리지 정보
        """
        total = len(self._missing_log)
        missing = [log for log in self._missing_log if log.imputation_method != "original"]

        return {
            "total_fields": total,
            "missing_count": len(missing),
            "missing_rate": len(missing) / total if total > 0 else 0.0,
            "missing_fields": [log.field_name for log in missing],
            "imputation_methods": {
                log.field_name: log.imputation_method
                for log in missing
            }
        }

    def reset(self):
        """결측 로그 초기화."""
        self._missing_log.clear()

    def _log_missing(
        self,
        field_name: str,
        original: Any,
        imputed: Any,
        method: str,
        is_critical: bool
    ):
        """결측 정보 기록."""
        self._missing_log.append(MissingFieldInfo(
            field_name=field_name,
            original_value=original,
            imputed_value=imputed,
            imputation_method=method,
            is_critical=is_critical
        ))
