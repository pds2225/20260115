"""
데이터 모듈 테스트 (30개).

TC-DAT-001 ~ TC-DAT-030

- KOTRA API 클라이언트/캐시
- UN Comtrade 데이터 (HS4 49개 품목)
- World Bank 데이터
"""

import pytest
from datetime import datetime, timedelta

from backend.data.kotra_api import (
    CacheEntry,
    KOTRACache,
    KOTRAClient,
    KOTRACountryInfo,
    DEFAULT_COUNTRIES,
    CACHE_TTL_SECONDS,
)
from backend.data.comtrade import (
    COVERAGE_RATIO,
    HS4_ITEM_COUNT,
    KOREA_EXPORT_HS4_DATA,
    ComtradeClient,
    TradeRecord,
    get_all_hs4_codes,
    get_hs4_data,
    get_top_partners_for_hs4,
    get_trade_value,
)
from backend.data.worldbank import (
    BUILTIN_WORLDBANK_DATA,
    WorldBankRecord,
    WSB_FIELDS,
    get_builtin_records,
)


# ===========================================================================
# KOTRA API 테스트 (TC-DAT-001 ~ 010)
# ===========================================================================

class TestKOTRACache:
    def test_cache_miss(self):
        """TC-DAT-001: 캐시 미스 시 None 반환."""
        cache = KOTRACache("/tmp/test_kotra_cache_miss")
        result = cache.get("999999", "test")
        assert result is None

    def test_cache_put_and_get(self):
        """TC-DAT-002: 캐시 저장 후 조회."""
        cache = KOTRACache("/tmp/test_kotra_cache_put")
        cache.put("330499", "new_market", [{"test": True}])
        result = cache.get("330499", "new_market")
        assert result is not None
        assert result.data == [{"test": True}]

    def test_cache_expiry(self):
        """TC-DAT-003: TTL 만료된 캐시는 무시."""
        entry = CacheEntry(
            data=["expired"],
            cached_at=datetime.now() - timedelta(seconds=CACHE_TTL_SECONDS + 100),
        )
        assert entry.is_expired

    def test_cache_not_expired(self):
        """TC-DAT-004: TTL 내 캐시는 유효."""
        entry = CacheEntry(
            data=["valid"],
            cached_at=datetime.now(),
        )
        assert not entry.is_expired

    def test_cache_ttl_remaining(self):
        """TC-DAT-005: 남은 TTL 계산."""
        entry = CacheEntry(
            data=["valid"],
            cached_at=datetime.now(),
        )
        assert entry.ttl_remaining_seconds > 0


class TestKOTRAClient:
    def test_fallback_to_defaults(self):
        """TC-DAT-006: API+캐시 실패 시 기본값 반환."""
        client = KOTRAClient(api_key=None, cache=KOTRACache("/tmp/test_fallback"))
        results = client.fetch_promising_countries("330499")
        assert len(results) > 0

    def test_default_countries_have_data(self):
        """TC-DAT-007: 기본 국가에 데이터가 있음."""
        for c in DEFAULT_COUNTRIES:
            assert c.country_code != ""
            assert c.gdp_usd > 0

    def test_data_source_tracked(self):
        """TC-DAT-008: 데이터 소스가 추적됨."""
        client = KOTRAClient()
        client.fetch_promising_countries("330499")
        assert client.last_data_source != ""

    def test_top_n_respected(self):
        """TC-DAT-009: top_n 제한."""
        client = KOTRAClient()
        results = client.fetch_promising_countries("330499", top_n=3)
        assert len(results) <= 3

    def test_country_info_to_dict(self):
        """TC-DAT-010: KOTRACountryInfo 직렬화."""
        info = DEFAULT_COUNTRIES[0]
        d = info.to_dict()
        assert "country_code" in d
        assert "gdp_usd" in d


# ===========================================================================
# UN Comtrade 테스트 (TC-DAT-011 ~ 020)
# ===========================================================================

class TestComtradeData:
    def test_49_hs4_items(self):
        """TC-DAT-011: HS4 49개 품목 데이터 존재."""
        assert HS4_ITEM_COUNT == 49

    def test_coverage_about_48_percent(self):
        """TC-DAT-012: 커버리지 약 48.8%."""
        assert 0.45 <= COVERAGE_RATIO <= 0.55

    def test_get_hs4_data_found(self):
        """TC-DAT-013: 반도체(8541) 데이터 조회."""
        data = get_hs4_data("8541")
        assert data is not None
        assert data["name"] == "반도체 소자"

    def test_get_hs4_data_not_found(self):
        """TC-DAT-014: 없는 HS코드는 None."""
        assert get_hs4_data("9999") is None

    def test_top_partners(self):
        """TC-DAT-015: 8541의 상위 파트너 5개."""
        partners = get_top_partners_for_hs4("8541")
        assert len(partners) == 5
        assert "CHN" in partners

    def test_trade_value_positive(self):
        """TC-DAT-016: 모든 품목 수출액 > 0."""
        for item in KOREA_EXPORT_HS4_DATA:
            assert item["value_usd"] > 0

    def test_get_trade_value(self):
        """TC-DAT-017: 화장품(3304) 수출액 조회."""
        val = get_trade_value("3304")
        assert val == 4_100_000_000

    def test_all_hs4_codes_list(self):
        """TC-DAT-018: 전체 HS4 코드 목록."""
        codes = get_all_hs4_codes()
        assert len(codes) == 49
        assert "8541" in codes

    def test_comtrade_client_builtin(self):
        """TC-DAT-019: ComtradeClient 내장 데이터 조회."""
        client = ComtradeClient()
        records = client.get_export_data("KOR", "330499")
        assert len(records) > 0
        assert all(isinstance(r, TradeRecord) for r in records)

    def test_trade_record_to_dict(self):
        """TC-DAT-020: TradeRecord 직렬화."""
        rec = TradeRecord("KOR", "USA", "3304", 2023, 1e9)
        d = rec.to_dict()
        assert d["reporter_iso3"] == "KOR"
        assert d["trade_value_usd"] == 1e9


# ===========================================================================
# World Bank 테스트 (TC-DAT-021 ~ 030)
# ===========================================================================

class TestWorldBankData:
    def test_builtin_data_count(self):
        """TC-DAT-021: 내장 국가 30개."""
        assert len(BUILTIN_WORLDBANK_DATA) == 30

    def test_builtin_records_generation(self):
        """TC-DAT-022: 내장 데이터로 레코드 생성."""
        records = get_builtin_records()
        assert len(records) == 30

    def test_usa_gdp_present(self):
        """TC-DAT-023: USA GDP 데이터 존재."""
        records = get_builtin_records()
        usa = [r for r in records if r.country_iso3 == "USA"]
        assert len(usa) == 1
        assert usa[0].get_value("gdp_usd") > 0

    def test_record_missing_fields(self):
        """TC-DAT-024: 결측 필드 감지."""
        rec = WorldBankRecord("XXX", "Test", "2026-01-01", gdp_usd=None)
        assert "gdp_usd" in rec.missing_fields

    def test_record_valid_for_scoring(self):
        """TC-DAT-025: GDP 있으면 valid."""
        rec = WorldBankRecord("USA", "US", "2026-01-01", gdp_usd=(25000e9, 2023))
        assert rec.is_valid_for_scoring

    def test_record_invalid_no_gdp(self):
        """TC-DAT-026: GDP 없으면 invalid."""
        rec = WorldBankRecord("XXX", "X", "2026-01-01")
        assert not rec.is_valid_for_scoring

    def test_record_invalid_zero_gdp(self):
        """TC-DAT-027: GDP=0이면 invalid."""
        rec = WorldBankRecord("XXX", "X", "2026-01-01", gdp_usd=(0, 2023))
        assert not rec.is_valid_for_scoring

    def test_record_warnings(self):
        """TC-DAT-028: GDP <= 0 경고 생성."""
        rec = WorldBankRecord("XXX", "X", "2026-01-01", gdp_usd=(-100, 2023))
        warnings = rec.warnings()
        assert any("GDP" in w for w in warnings)

    def test_wsb_fields_count(self):
        """TC-DAT-029: WSB 필드 2개."""
        assert len(WSB_FIELDS) == 2

    def test_all_builtin_valid(self):
        """TC-DAT-030: 내장 데이터 전체 valid."""
        records = get_builtin_records()
        for rec in records:
            assert rec.is_valid_for_scoring, f"{rec.country_iso3} is invalid"
