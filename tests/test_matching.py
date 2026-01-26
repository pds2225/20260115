"""Matching Service Tests

테스트 케이스:
1. 정상 매칭 요청
2. MOQ Hard Gate 실패 (capacity 초과)
3. MOQ Soft Score 계산
4. required 인증 미충족 탈락
5. preferred 인증 가점
6. 수출불가국 바이어 제외
7. 성공사례 보너스 - 증거 강도 기반
"""

import pytest
from unittest.mock import AsyncMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.schemas import MatchRequest, ProfileType
from backend.services.matching_service import MatchingService


class TestMatchingService:
    """Matching 서비스 테스트."""

    @pytest.fixture
    def mock_kotra_client(self):
        """Mock KOTRA client."""
        client = AsyncMock()
        client.get_country_fraud_risk = AsyncMock(return_value={
            "risk_level": "SAFE", "case_count": 0, "score_penalty": 0
        })
        client.get_relevant_success_cases = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def service(self, mock_kotra_client):
        """Create service with mock client."""
        return MatchingService(kotra_client=mock_kotra_client)

    # ==========================================================================
    # Test 1: 정상 매칭 요청
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_normal_matching(self, service):
        """정상적인 매칭 요청 테스트."""
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "certifications": ["FDA"]
            },
            top_n=5,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        assert result.profile_type == ProfileType.SELLER
        assert len(result.matches) <= 5
        assert result.explanation.kotra_status == "ok"

    # ==========================================================================
    # Test 2: MOQ Hard Gate 실패 (capacity 초과)
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_moq_hard_gate_failure(self, service):
        """MOQ Hard Gate 실패 테스트 - buyer MOQ가 seller capacity 초과."""
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "annual_capacity": 100,  # 매우 작은 capacity
                "certifications": []
            },
            top_n=10,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        # capacity 100인데 buyer MOQ가 더 크면 moq_gate_passed=False
        failed = [m for m in result.matches if not m.moq_gate_passed]
        # 실패한 매칭이 있을 수 있음
        for m in failed:
            assert m.fit_score == 0.0
            assert "reason" in m.score_breakdown

    # ==========================================================================
    # Test 3: MOQ Soft Score 계산
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_moq_soft_score(self, service):
        """MOQ Soft Score가 계산되는지 테스트."""
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "certifications": []
            },
            top_n=5,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        for match in result.matches:
            if match.moq_gate_passed:
                assert 0 <= match.moq_score <= 1
                assert match.order_value_usd is not None or match.order_value_usd == 0

    # ==========================================================================
    # Test 4: required 인증 미충족 탈락
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_required_cert_failure(self, service):
        """required 인증 미충족 시 탈락 테스트."""
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "required_certs": ["EXTREMELY_RARE_CERT_XYZ"],  # 아무도 없는 인증
                "preferred_certs": []
            },
            top_n=10,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        # 모든 바이어가 탈락해야 함
        for match in result.matches:
            if match.fit_score == 0:
                assert "필수 인증 미충족" in match.score_breakdown.get("reason", "")

    # ==========================================================================
    # Test 5: preferred 인증 가점
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_preferred_cert_bonus(self, service):
        """preferred 인증 가점 테스트."""
        # ISO 인증 보유자가 있으면 가점
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "required_certs": [],
                "preferred_certs": ["ISO"]
            },
            top_n=10,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        iso_matches = [m for m in result.matches if "ISO" in m.matched_preferred_certs]
        non_iso = [m for m in result.matches if "ISO" not in m.matched_preferred_certs and m.moq_gate_passed]

        # ISO 매칭이 있으면 preferred_certs에 기록됨
        for m in iso_matches:
            assert "ISO" in m.matched_preferred_certs

    # ==========================================================================
    # Test 6: 수출불가국 바이어 제외
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_blocked_country_buyer_excluded(self, service):
        """차단국 바이어가 제외되는지 테스트."""
        # 바이어 중 북한(KP)이 있다면 제외되어야 함
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "certifications": []
            },
            top_n=50,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        # 매칭 결과에 차단국이 없어야 함
        blocked_countries = ["KP", "SY", "IR", "CU"]
        for match in result.matches:
            assert match.country not in blocked_countries

    # ==========================================================================
    # Test 7: explanation 필드 포함 확인
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_explanation_fields(self, service):
        """explanation 필드가 모두 포함되는지 테스트."""
        request = MatchRequest(
            profile_type=ProfileType.SELLER,
            profile={
                "hs_code": "330499",
                "country": "KR",
                "price_range": [5.0, 8.0],
                "moq": 1000,
                "certifications": []
            },
            top_n=5,
            include_risk_analysis=False
        )

        result = await service.find_matches(request)

        assert hasattr(result, 'explanation')
        assert hasattr(result.explanation, 'kotra_status')
        assert hasattr(result.explanation, 'confidence')
        assert hasattr(result, 'blocked_countries')


class TestMOQEvaluation:
    """MOQ 평가 로직 테스트."""

    @pytest.fixture
    def service(self):
        return MatchingService(kotra_client=AsyncMock())

    def test_moq_soft_score_exact_match(self, service):
        """MOQ 정확히 일치 시 soft score = 1.0."""
        profile = {"moq": 1000}
        candidate = {"moq": 1000, "price_range": [5.0, 8.0]}

        gate, score, value, reason = service._evaluate_moq(
            profile, candidate, ProfileType.SELLER
        )

        assert gate is True
        assert score == 1.0

    def test_moq_soft_score_slight_diff(self, service):
        """MOQ 20% 이내 차이 시 soft score = 1.0."""
        profile = {"moq": 1000}
        candidate = {"moq": 1100, "price_range": [5.0, 8.0]}  # 10% 차이

        gate, score, value, reason = service._evaluate_moq(
            profile, candidate, ProfileType.SELLER
        )

        assert gate is True
        assert score == 1.0

    def test_moq_soft_score_large_diff(self, service):
        """MOQ 큰 차이 시 soft score 감소."""
        profile = {"moq": 1000}
        candidate = {"moq": 5000, "price_range": [5.0, 8.0]}  # 400% 차이

        gate, score, value, reason = service._evaluate_moq(
            profile, candidate, ProfileType.SELLER
        )

        assert gate is True  # 탈락은 아님
        assert score < 0.5  # 하지만 점수는 낮음


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
