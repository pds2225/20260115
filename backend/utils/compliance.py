"""Compliance Checker Module

수출불가국(제재/전쟁/금수 등) 처리:
- hard_block: 무조건 제외
- restricted: 감점 + 경고
- config 파일 기반 관리 (하드코딩 금지)
"""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ComplianceStatus(str, Enum):
    """규정 준수 상태."""
    OK = "ok"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"


class ComplianceChecker:
    """수출 규정 준수 검사기."""

    def __init__(self, config_path: Optional[str] = None):
        """검사기 초기화.

        Args:
            config_path: 설정 파일 경로 (기본: config/export_blocklist.json)
        """
        self.config_path = Path(
            config_path or
            os.getenv("BLOCKLIST_CONFIG_PATH", "config/export_blocklist.json")
        )
        self._config: Optional[Dict[str, Any]] = None
        self._load_config()

    def _load_config(self):
        """설정 파일 로드."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                logger.info(f"Blocklist config loaded: {self.config_path}")
            else:
                logger.warning(f"Blocklist config not found: {self.config_path}")
                self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"Blocklist config load error: {e}")
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환 (fallback)."""
        return {
            "hard_block": {
                "countries": ["KP", "SY", "IR", "CU"],
                "reasons": {
                    "KP": "UN/미국 대북제재",
                    "SY": "시리아 제재",
                    "IR": "이란 제재",
                    "CU": "쿠바 금수조치"
                }
            },
            "restricted": {
                "countries": ["RU", "BY", "VE", "MM", "AF"],
                "reasons": {},
                "score_penalty": {}
            },
            "high_risk_warning": {
                "countries": [],
                "reasons": {},
                "score_penalty": {}
            }
        }

    def check(self, country_code: str) -> Tuple[ComplianceStatus, Dict[str, Any]]:
        """국가 규정 준수 상태 확인.

        Args:
            country_code: ISO 2자리 국가 코드

        Returns:
            (상태, 상세 정보)
        """
        code = country_code.upper()

        # 1. hard_block 확인
        hard_block = self._config.get("hard_block", {})
        if code in hard_block.get("countries", []):
            reason = hard_block.get("reasons", {}).get(code, "수출 금지 대상국")
            return ComplianceStatus.BLOCKED, {
                "country_code": code,
                "compliance_status": "blocked",
                "reason": reason,
                "action": "이 국가는 수출이 금지되어 있습니다.",
                "score_penalty": -100  # 완전 제외
            }

        # 2. restricted 확인
        restricted = self._config.get("restricted", {})
        if code in restricted.get("countries", []):
            reason = restricted.get("reasons", {}).get(code, "수출 제한 대상국")
            penalty = restricted.get("score_penalty", {}).get(code, -20)
            return ComplianceStatus.RESTRICTED, {
                "country_code": code,
                "compliance_status": "restricted",
                "reason": reason,
                "action": "수출이 제한되어 있습니다. 추가 검토가 필요합니다.",
                "score_penalty": penalty,
                "warning": f"경고: {code}는 {reason}로 인해 수출이 제한됩니다."
            }

        # 3. high_risk_warning 확인
        high_risk = self._config.get("high_risk_warning", {})
        if code in high_risk.get("countries", []):
            reason = high_risk.get("reasons", {}).get(code, "고위험 지역")
            penalty = high_risk.get("score_penalty", {}).get(code, -10)
            return ComplianceStatus.OK, {
                "country_code": code,
                "compliance_status": "ok",
                "reason": None,
                "action": None,
                "score_penalty": penalty,
                "warning": f"주의: {code}는 {reason}로 분류됩니다."
            }

        # 4. 정상
        return ComplianceStatus.OK, {
            "country_code": code,
            "compliance_status": "ok",
            "reason": None,
            "action": None,
            "score_penalty": 0,
            "warning": None
        }

    def filter_countries(
        self,
        country_codes: List[str]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """국가 목록에서 blocked 국가 제외.

        Args:
            country_codes: 국가 코드 목록

        Returns:
            (허용된 국가 목록, 제외/제한 정보)
        """
        allowed = []
        exclusion_info = []

        for code in country_codes:
            status, info = self.check(code)

            if status == ComplianceStatus.BLOCKED:
                exclusion_info.append({
                    "country_code": code,
                    "action": "excluded",
                    "reason": info["reason"]
                })
            else:
                allowed.append(code)
                if status == ComplianceStatus.RESTRICTED:
                    exclusion_info.append({
                        "country_code": code,
                        "action": "restricted",
                        "reason": info["reason"],
                        "penalty": info["score_penalty"]
                    })

        return allowed, exclusion_info

    def get_blocked_countries(self) -> List[str]:
        """차단된 국가 목록 반환."""
        return self._config.get("hard_block", {}).get("countries", [])

    def get_restricted_countries(self) -> List[str]:
        """제한된 국가 목록 반환."""
        return self._config.get("restricted", {}).get("countries", [])

    def get_penalty(self, country_code: str) -> int:
        """국가별 페널티 점수 반환.

        Args:
            country_code: 국가 코드

        Returns:
            페널티 점수 (0 ~ -100)
        """
        _, info = self.check(country_code)
        return info.get("score_penalty", 0)

    def is_blocked(self, country_code: str) -> bool:
        """차단 국가 여부 확인."""
        status, _ = self.check(country_code)
        return status == ComplianceStatus.BLOCKED

    def is_restricted(self, country_code: str) -> bool:
        """제한 국가 여부 확인."""
        status, _ = self.check(country_code)
        return status == ComplianceStatus.RESTRICTED

    def reload_config(self):
        """설정 다시 로드."""
        self._load_config()


# 싱글톤 인스턴스
_checker_instance: Optional[ComplianceChecker] = None


def get_compliance_checker() -> ComplianceChecker:
    """ComplianceChecker 싱글톤 반환."""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = ComplianceChecker()
    return _checker_instance
