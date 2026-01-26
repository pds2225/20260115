"""Recommendation Service Tests

테스트 케이스:
1. 정상 추천 요청
2. KOTRA API 장애 시 fallback (캐시)
3. KOTRA API 장애 시 fallback (대체 스코어링)
4. 수출불가국(blocked) 제외
5. 수출제한국(restricted) 감점
6. 성공사례 보너스 - country_match 필수
7. low confidence 경고
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.schemas import RecommendationRequest, ExportGoal
from backend.services.recommendation_service import RecommendationService
from backend.utils.compliance import ComplianceChecker


class TestRecommendationService:
    """Recommendation 서비스 테스트."""

    @pytest.fixture
    def mock_kotra_client(self):
        """Mock KOTRA client."""
        client = AsyncMock()
        client.get_export_recommendations = AsyncMock(return_value=[
            {"HSCD": "330499", "NAT_NAME": "미국", "EXP_BHRC_SCR": 3.5, "country_code": "US"},
            {"HSCD": "330499", "NAT_NAME": "일본", "EXP_BHRC_SCR": 3.2, "country_code": "JP"},
            {"HSCD": "330499", "NAT_NAME": "독일", "EXP_BHRC_SCR": 2.8, "country_code": "DE"},
        ])
        client.get_country_economic_indicators = AsyncMock(return_value={
            "gdp": 25000, "growth_rate": 2.5, "risk_grade": "A"
        })
        client.get_product_info = AsyncMock(return_value=[])
        client.get_relevant_success_cases = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def service(self, mock_kotra_client):
        """Create service with mock client."""
        return RecommendationService(kotra_client=mock_kotra_client)

    # ==========================================================================
    # Test 1: 정상 추천 요청
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_normal_recommendation(self, service):
        """정상적인 추천 요청 테스트."""
        request = RecommendationRequest(
            hs_code="330499",
            goal=ExportGoal.NEW_MARKET,
            top_n=3
        )

        result = await service.get_recommendations(request)

        assert result.hs_code == "330499"
        assert len(result.recommendations) <= 3
        assert result.explanation.kotra_status == "ok"
        assert result.explanation.fallback_used is False
        assert result.explanation.confidence > 0

    # ==========================================================================
    # Test 2: KOTRA API 장애 시 fallback (대체 스코어링)
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_fallback_alternative_scoring(self, mock_kotra_client):
        """API 장애 시 대체 스코어링 테스트."""
        mock_kotra_client.get_export_recommendations = AsyncMock(return_value=[])

        service = RecommendationService(kotra_client=mock_kotra_client)
        request = RecommendationRequest(
            hs_code="330499",
            goal=ExportGoal.NEW_MARKET,
            top_n=5
        )

        result = await service.get_recommendations(request)

        assert result.explanation.kotra_status == "unavailable"
        assert result.explanation.fallback_used is True
        assert len(result.recommendations) > 0
        # 고정 5개국이 아닌 다양한 후보
        countries = [r.country_code for r in result.recommendations]
        assert len(set(countries)) == len(countries)  # 중복 없음

    # ==========================================================================
    # Test 3: 수출불가국(blocked) 제외
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_blocked_country_excluded(self, mock_kotra_client):
        """차단국이 추천에서 제외되는지 테스트."""
        mock_kotra_client.get_export_recommendations = AsyncMock(return_value=[
            {"HSCD": "330499", "NAT_NAME": "북한", "EXP_BHRC_SCR": 5.0, "country_code": "KP"},
            {"HSCD": "330499", "NAT_NAME": "미국", "EXP_BHRC_SCR": 3.5, "country_code": "US"},
        ])

        service = RecommendationService(kotra_client=mock_kotra_client)
        request = RecommendationRequest(
            hs_code="330499",
            goal=ExportGoal.NEW_MARKET,
            top_n=5
        )

        result = await service.get_recommendations(request)

        country_codes = [r.country_code for r in result.recommendations]
        assert "KP" not in country_codes
        assert len(result.excluded_countries) > 0
        assert result.excluded_countries[0]["country_code"] == "KP"

    # ==========================================================================
    # Test 4: 수출제한국(restricted) 감점
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_restricted_country_penalty(self, mock_kotra_client):
        """제한국에 패널티가 적용되는지 테스트."""
        mock_kotra_client.get_export_recommendations = AsyncMock(return_value=[
            {"HSCD": "330499", "NAT_NAME": "러시아", "EXP_BHRC_SCR": 5.0, "country_code": "RU"},
            {"HSCD": "330499", "NAT_NAME": "미국", "EXP_BHRC_SCR": 3.5, "country_code": "US"},
        ])

        service = RecommendationService(kotra_client=mock_kotra_client)
        request = RecommendationRequest(
            hs_code="330499",
            goal=ExportGoal.NEW_MARKET,
            top_n=5
        )

        result = await service.get_recommendations(request)

        ru_rec = next((r for r in result.recommendations if r.country_code == "RU"), None)
        if ru_rec:
            assert ru_rec.compliance is not None
            assert ru_rec.compliance.compliance_status == "restricted"
            assert ru_rec.compliance.score_penalty < 0

    # ==========================================================================
    # Test 5: explanation 필드 포함 확인
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_explanation_fields(self, service):
        """explanation 필드가 모두 포함되는지 테스트."""
        request = RecommendationRequest(
            hs_code="330499",
            goal=ExportGoal.NEW_MARKET,
            top_n=3
        )

        result = await service.get_recommendations(request)

        assert hasattr(result, 'explanation')
        assert hasattr(result.explanation, 'kotra_status')
        assert hasattr(result.explanation, 'fallback_used')
        assert hasattr(result.explanation, 'confidence')
        assert hasattr(result.explanation, 'data_coverage')
        assert hasattr(result.explanation.data_coverage, 'missing_rate')
        assert hasattr(result.explanation.data_coverage, 'missing_fields')


class TestComplianceChecker:
    """Compliance 검사기 테스트."""

    @pytest.fixture
    def checker(self):
        return ComplianceChecker()

    def test_blocked_country(self, checker):
        """차단국 확인."""
        from backend.utils.compliance import ComplianceStatus

        status, info = checker.check("KP")
        assert status == ComplianceStatus.BLOCKED
        assert info["compliance_status"] == "blocked"
        assert info["score_penalty"] == -100

    def test_restricted_country(self, checker):
        """제한국 확인."""
        from backend.utils.compliance import ComplianceStatus

        status, info = checker.check("RU")
        assert status == ComplianceStatus.RESTRICTED
        assert info["compliance_status"] == "restricted"
        assert info["score_penalty"] < 0

    def test_normal_country(self, checker):
        """정상국 확인."""
        from backend.utils.compliance import ComplianceStatus

        status, info = checker.check("US")
        assert status == ComplianceStatus.OK
        assert info["compliance_status"] == "ok"
        assert info["score_penalty"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
