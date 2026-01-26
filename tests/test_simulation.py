"""Simulation Service Tests

테스트 케이스:
1. 정상 시뮬레이션 요청
2. 수출불가국 시뮬레이션 거부
3. 수출제한국 경고 + 감점
4. 결측치 처리 (0 아닌 지역평균)
5. low confidence 경고
"""

import pytest
from unittest.mock import AsyncMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.schemas import SimulationRequest
from backend.services.simulation_service import SimulationService


class TestSimulationService:
    """Simulation 서비스 테스트."""

    @pytest.fixture
    def mock_kotra_client(self):
        """Mock KOTRA client."""
        client = AsyncMock()
        client.get_export_recommendations = AsyncMock(return_value=[
            {"HSCD": "330499", "NAT_NAME": "미국", "EXP_BHRC_SCR": 8.5}
        ])
        client.get_country_economic_indicators = AsyncMock(return_value={
            "gdp": 25000, "growth_rate": 2.5, "risk_grade": "A", "country_name": "미국"
        })
        client.get_product_info = AsyncMock(return_value=[])
        client.analyze_news_risk = AsyncMock(return_value={
            "risk_adjustment": 5, "positive_count": 10, "negative_count": 5
        })
        return client

    @pytest.fixture
    def service(self, mock_kotra_client):
        """Create service with mock client."""
        return SimulationService(kotra_client=mock_kotra_client)

    # ==========================================================================
    # Test 1: 정상 시뮬레이션 요청
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_normal_simulation(self, service):
        """정상적인 시뮬레이션 요청 테스트."""
        request = SimulationRequest(
            hs_code="330499",
            target_country="US",
            price_per_unit=10.0,
            moq=1000,
            annual_capacity=50000,
            include_news_risk=True
        )

        result = await service.simulate(request)

        assert result.target_country == "US"
        assert result.hs_code == "330499"
        assert result.success_probability > 0
        assert result.estimated_revenue_min >= 0
        assert result.estimated_revenue_max >= result.estimated_revenue_min
        assert result.explanation.kotra_status == "ok"
        assert result.explanation.confidence > 0

    # ==========================================================================
    # Test 2: 수출불가국 시뮬레이션 거부
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_blocked_country_simulation(self, service):
        """차단국 시뮬레이션 거부 테스트."""
        request = SimulationRequest(
            hs_code="330499",
            target_country="KP",  # 북한
            price_per_unit=10.0,
            moq=1000,
            annual_capacity=50000
        )

        result = await service.simulate(request)

        assert result.success_probability == 0.0
        assert result.estimated_revenue_min == 0.0
        assert result.estimated_revenue_max == 0.0
        assert result.compliance is not None
        assert result.compliance.compliance_status == "blocked"
        assert result.explanation.kotra_status == "blocked"
        assert result.explanation.confidence == 0.0

    # ==========================================================================
    # Test 3: 수출제한국 경고 + 감점
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_restricted_country_warning(self, service):
        """제한국 시뮬레이션 경고 테스트."""
        request = SimulationRequest(
            hs_code="330499",
            target_country="RU",  # 러시아
            price_per_unit=10.0,
            moq=1000,
            annual_capacity=50000
        )

        result = await service.simulate(request)

        # 시뮬레이션은 가능하지만 경고
        assert result.success_probability > 0  # 0은 아님
        assert result.compliance is not None
        assert result.compliance.compliance_status == "restricted"
        assert result.compliance.score_penalty < 0

    # ==========================================================================
    # Test 4: explanation 필드 포함 확인
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_explanation_fields(self, service):
        """explanation 필드가 모두 포함되는지 테스트."""
        request = SimulationRequest(
            hs_code="330499",
            target_country="US",
            price_per_unit=10.0,
            moq=1000,
            annual_capacity=50000
        )

        result = await service.simulate(request)

        assert hasattr(result, 'explanation')
        assert hasattr(result.explanation, 'kotra_status')
        assert hasattr(result.explanation, 'fallback_used')
        assert hasattr(result.explanation, 'confidence')
        assert hasattr(result.explanation, 'data_coverage')
        assert hasattr(result.explanation.data_coverage, 'missing_rate')

    # ==========================================================================
    # Test 5: 시장규모 추정 테스트
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_market_size_estimation(self, service):
        """시장규모가 합리적으로 추정되는지 테스트."""
        request = SimulationRequest(
            hs_code="330499",
            target_country="US",
            price_per_unit=10.0,
            moq=1000,
            annual_capacity=50000,
            market_size_estimate=None  # 자동 추정
        )

        result = await service.simulate(request)

        assert result.market_size > 0
        assert result.market_share_min >= 0
        assert result.market_share_max >= result.market_share_min


class TestMissingDataHandler:
    """결측치 처리 테스트."""

    def test_numeric_imputation_region_avg(self):
        """지역 평균으로 수치 결측치 대체 테스트."""
        from backend.utils.missing_data import MissingDataHandler

        handler = MissingDataHandler()
        value, method = handler.impute_numeric(None, "gdp", "US")

        assert value > 0  # 0이 아닌 값
        assert "region_avg" in method or method == "fallback"

    def test_categorical_imputation(self):
        """범주형 결측치 대체 테스트."""
        from backend.utils.missing_data import MissingDataHandler

        handler = MissingDataHandler()
        value, method = handler.impute_categorical(None, "risk_grade", "US")

        assert value != ""
        assert value != "0"

    def test_process_country_info(self):
        """국가 정보 일괄 처리 테스트."""
        from backend.utils.missing_data import MissingDataHandler

        handler = MissingDataHandler()
        empty_info = {}

        processed, methods = handler.process_country_info(empty_info, "US")

        assert processed["gdp"] > 0  # 0이 아님
        assert processed["risk_grade"] != ""


class TestConfidenceCalculator:
    """신뢰도 계산 테스트."""

    def test_high_confidence(self):
        """높은 신뢰도 테스트."""
        from backend.utils.confidence import ConfidenceCalculator

        calc = ConfidenceCalculator()
        confidence, breakdown = calc.calculate(
            context="simulation",
            missing_fields=[],
            data_sources_used=["KOTRA 수출유망추천정보", "KOTRA 국가정보", "KOTRA 상품DB", "KOTRA 해외시장뉴스"],
            fallback_used=False,
            kotra_status="ok"
        )

        assert confidence >= 0.7

    def test_low_confidence_with_fallback(self):
        """fallback 사용 시 낮은 신뢰도 테스트."""
        from backend.utils.confidence import ConfidenceCalculator

        calc = ConfidenceCalculator()
        confidence, breakdown = calc.calculate(
            context="simulation",
            missing_fields=["gdp", "growth_rate", "market_size"],
            data_sources_used=[],
            fallback_used=True,
            kotra_status="unavailable"
        )

        assert confidence < 0.5

    def test_warning_for_low_confidence(self):
        """낮은 신뢰도 시 경고 메시지 테스트."""
        from backend.utils.confidence import ConfidenceCalculator

        calc = ConfidenceCalculator()
        warning = calc.get_confidence_warning(0.2)

        assert warning is not None
        assert "경고" in warning or "주의" in warning


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
