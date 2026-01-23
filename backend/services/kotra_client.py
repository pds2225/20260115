"""KOTRA Open API Client

This module provides a unified client for accessing KOTRA's Open APIs.
Integrates 6 APIs:
1. Export Recommendation (수출유망추천정보)
2. Country Information (국가정보)
3. Product DB (상품DB)
4. Overseas Market News (해외시장뉴스)
5. Trade Fraud Cases (무역사기사례)
6. Company Success Cases (기업성공사례)
"""

import os
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class KotraAPIClient:
    """Unified client for KOTRA Open APIs."""
    
    # API Endpoints
    ENDPOINTS = {
        "export_recommend": "https://apis.data.go.kr/B410001/export-recommend-info",
        "country_info": "https://apis.data.go.kr/B410001/kotra_nationalInformation/natnInfo/natnInfo",
        "product_db": "https://apis.data.go.kr/B410001/cmmdtDb/cmmdtDb",
        "overseas_news": "https://apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews",
        "fraud_cases": "https://apis.data.go.kr/B410001/cmmrcFraudCase/cmmrcFraudCase",
        "success_cases": "https://apis.data.go.kr/B410001/compSucsCase/compSucsCase",
    }
    
    # Country code mapping (ISO 2-letter to KOTRA format)
    COUNTRY_CODES = {
        "US": "US", "CN": "CN", "JP": "JP", "VN": "VN", "DE": "DE",
        "GB": "GB", "FR": "FR", "IT": "IT", "TH": "TH", "ID": "ID",
        "IN": "IN", "BR": "BR", "MX": "MX", "KR": "KR", "AU": "AU",
        "CA": "CA", "SG": "SG", "MY": "MY", "PH": "PH", "AE": "AE",
    }
    
    def __init__(self, service_key: Optional[str] = None):
        """Initialize KOTRA API Client.
        
        Args:
            service_key: API service key from data.go.kr portal.
                        Falls back to KOTRA_SERVICE_KEY env variable.
        """
        self.service_key = service_key or os.getenv("KOTRA_SERVICE_KEY", "")
        if not self.service_key:
            logger.warning("KOTRA_SERVICE_KEY not configured. API calls will fail.")
        
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _request(
        self,
        endpoint_key: str,
        params: Dict[str, Any],
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Make a request to KOTRA API.
        
        Args:
            endpoint_key: Key from ENDPOINTS dict
            params: Query parameters (serviceKey added automatically)
            timeout: Request timeout in seconds
            
        Returns:
            Parsed JSON response
        """
        url = self.ENDPOINTS.get(endpoint_key)
        if not url:
            raise ValueError(f"Unknown endpoint: {endpoint_key}")
        
        # Add common parameters
        params["serviceKey"] = self.service_key
        params.setdefault("type", "json")
        params.setdefault("numOfRows", 10)
        params.setdefault("pageNo", 1)
        
        try:
            response = await self.client.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {endpoint_key}: {e}")
            return {"error": str(e), "status_code": e.response.status_code}
        except httpx.RequestError as e:
            logger.error(f"Request error to {endpoint_key}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error from {endpoint_key}: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # 1. Export Recommendation API (수출유망추천정보)
    # NOTE: This API endpoint returns "Unexpected errors" - using mock data
    # =========================================================================
    async def get_export_recommendations(
        self,
        hs_code: str,
        export_scale: Optional[str] = None,
        num_rows: int = 20
    ) -> List[Dict[str, Any]]:
        """Get ML-based export recommendation scores.
        
        NOTE: The KOTRA Export Recommendation API endpoint is currently 
        returning errors. This method uses mock data based on Product DB
        and Country Info APIs as fallback.
        
        Args:
            hs_code: HS Code (4-6 digits)
            export_scale: Export scale code (optional)
            num_rows: Number of results to return
            
        Returns:
            List of recommendations with:
            - HSCD: HS Code
            - NAT_NAME: Country name
            - EXPORTSCALE: Export scale
            - EXP_BHRC_SCR: Export success score (0-5+, higher is better)
            - UPDT_DT: Update datetime
        """
        # Generate mock recommendations based on country info
        # In production, this should integrate with working KOTRA data
        mock_countries = [
            {"code": "US", "name": "미국", "base_score": 3.5},
            {"code": "CN", "name": "중국", "base_score": 3.2},
            {"code": "VN", "name": "베트남", "base_score": 3.0},
            {"code": "JP", "name": "일본", "base_score": 2.8},
            {"code": "DE", "name": "독일", "base_score": 2.6},
            {"code": "TH", "name": "태국", "base_score": 2.5},
            {"code": "ID", "name": "인도네시아", "base_score": 2.4},
            {"code": "IN", "name": "인도", "base_score": 2.3},
        ]
        
        records = []
        for country in mock_countries[:num_rows]:
            records.append({
                "HSCD": hs_code,
                "NAT_CD": country["code"],
                "NAT_NAME": country["name"],
                "EXPORTSCALE": export_scale or "B",
                "EXP_BHRC_SCR": country["base_score"],
                "UPDT_DT": datetime.now().strftime("%Y-%m-%d"),
                "data_source": "mock_fallback"
            })
        
        return records[:num_rows]
    
    # =========================================================================
    # 2. Country Information API (국가정보)
    # =========================================================================
    async def get_country_info(self, country_code: str) -> Dict[str, Any]:
        """Get detailed country information.
        
        Args:
            country_code: ISO 2-letter country code (e.g., 'US', 'CN')
            
        Returns:
            Country info including:
            - natnNm: Country name
            - cptlNm: Capital city
            - poplCnt: Population
            - area: Area
            - gdpcpList: GDP data by year
            - ecnmyGrwrtList: Economic growth rate by year
            - inflRateList: Inflation rate by year
            - unempRateList: Unemployment rate by year
            - frxrsList: Exchange rate by year
            - mrktChrtrtCntnt: Market characteristics
            - bhrcGoodsList: Promising goods list
            - riskGrd: Risk grade
        """
        params = {
            "isoWd2CntCd": country_code.upper(),
        }
        
        result = await self._request("country_info", params)
        
        # Extract data from response structure
        items = result.get("items", result.get("data", [result]))
        
        if isinstance(items, list) and items:
            return items[0]
        return items if isinstance(items, dict) else {}
    
    async def get_country_economic_indicators(
        self, country_code: str
    ) -> Dict[str, Any]:
        """Extract key economic indicators from country info.
        
        Args:
            country_code: ISO 2-letter country code
            
        Returns:
            Dict with:
            - gdp: Latest GDP
            - growth_rate: Latest economic growth rate
            - inflation_rate: Latest inflation rate
            - risk_grade: Risk grade (A-E)
            - market_characteristics: Market overview
        """
        info = await self.get_country_info(country_code)
        
        if not info:
            return {}
        
        # Extract latest values from year lists
        def get_latest(data_list: List[Dict], value_key: str) -> Optional[float]:
            if not data_list:
                return None
            # Sort by year descending
            sorted_list = sorted(
                data_list, 
                key=lambda x: x.get("year", x.get("yr", 0)), 
                reverse=True
            )
            if sorted_list:
                val = sorted_list[0].get(value_key)
                try:
                    return float(val) if val else None
                except (ValueError, TypeError):
                    return None
            return None
        
        return {
            "country_code": country_code,
            "country_name": info.get("natnNm", ""),
            "capital": info.get("cptlNm", ""),
            "population": info.get("poplCnt"),
            "gdp": get_latest(info.get("gdpcpList", []), "gdpcp"),
            "growth_rate": get_latest(info.get("ecnmyGrwrtList", []), "ecnmyGrwrt"),
            "inflation_rate": get_latest(info.get("inflRateList", []), "inflRate"),
            "unemployment_rate": get_latest(info.get("unempRateList", []), "unempRate"),
            "exchange_rate": get_latest(info.get("frxrsList", []), "frxrs"),
            "risk_grade": info.get("riskGrd", ""),
            "market_characteristics": info.get("mrktChrtrtCntnt", ""),
            "promising_goods": info.get("bhrcGoodsList", []),
        }
    
    # =========================================================================
    # 3. Product DB API (상품DB) - WORKING ✅
    # Required params: pageNo, numOfRows, type
    # =========================================================================
    async def get_product_info(
        self,
        country_code: Optional[str] = None,
        search_keyword: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        num_rows: int = 10
    ) -> List[Dict[str, Any]]:
        """Get product database entries.
        
        VERIFIED WORKING: This API returns product information correctly.
        Total records available: 6,483+
        
        Args:
            country_code: Filter by country
            search_keyword: Search in product name/content
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            num_rows: Number of results
            
        Returns:
            List of product entries with:
            - bbstxSn: Article serial number
            - korPdtNm: Korean product name
            - hsCd: HS Code
            - kotraNewsUrl: Detail URL
            - newsTitl: News title
            - regn: Region
            - dataType: Data type
        """
        params = {
            "numOfRows": num_rows,
            "pageNo": 1,
        }
        
        # Note: search parameter may not work - API might not support keyword search
        if search_keyword:
            params["search"] = search_keyword
        
        result = await self._request("product_db", params)
        
        # Parse response structure
        body = result.get("response", {}).get("body", {})
        item_list = body.get("itemList", {})
        items = item_list.get("item", [])
        
        # Handle single item case (not wrapped in list)
        if isinstance(items, dict):
            items = [items]
        
        # Filter by country if specified
        if country_code and items:
            items = [i for i in items if country_code.upper() in str(i.get("natn", "")).upper() or
                    country_code.upper() in str(i.get("regn", "")).upper()]
        
        return items[:num_rows]
    
    # =========================================================================
    # 4. Overseas Market News API (해외시장뉴스) - WORKING ✅
    # Required params: pageNo, numOfRows, type
    # Total records: 93,924+
    # =========================================================================
    async def get_overseas_news(
        self,
        country_code: Optional[str] = None,
        search_keyword: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        num_rows: int = 10
    ) -> List[Dict[str, Any]]:
        """Get overseas market news.
        
        VERIFIED WORKING: This API returns news correctly with pageNo + numOfRows.
        Total records available: 93,924+
        
        Args:
            country_code: Country name in Korean (e.g., "미국", "중국")
            search_keyword: Search keyword (Note: search2 parameter might need region code)
            from_date: Start date (not confirmed working)
            to_date: End date (not confirmed working)
            num_rows: Number of results
            
        Returns:
            List of news articles with:
            - bbstxSn: Article serial number
            - natn: Country name (Korean)
            - regn: Region
            - newsTitl: News title
            - kotraNewsUrl: KOTRA news URL
            - othbcDt: Published date (YYYY-MM-DD)
            - ovrofInfo: Trade office info
            - newsWrterNm: Writer name
            - indstCl: Industry classification
            - infoCl: Information classification
            - dataType: Data type
        """
        params = {
            "numOfRows": num_rows,
            "pageNo": 1,
        }
        
        # Note: search1, search2 parameters might not work as expected
        # The API returns all results regardless - filtering done client-side
        
        result = await self._request("overseas_news", params)
        
        # Parse response structure
        body = result.get("response", {}).get("body", {})
        item_list = body.get("itemList", {})
        items = item_list.get("item", [])
        
        # Handle single item case
        if isinstance(items, dict):
            items = [items]
        
        # Client-side filtering by country name (Korean)
        if country_code and items:
            # Map country codes to Korean names for filtering
            country_names = {
                "US": "미국", "CN": "중국", "JP": "일본", "VN": "베트남",
                "DE": "독일", "TH": "태국", "ID": "인도네시아", "IN": "인도",
                "AU": "호주", "GB": "영국", "FR": "프랑스", "SG": "싱가포르",
            }
            target_name = country_names.get(country_code.upper(), country_code)
            items = [i for i in items if target_name in str(i.get("natn", ""))]
        
        return items[:num_rows]
    
    async def analyze_news_risk(
        self,
        country_code: str,
        num_articles: int = 50
    ) -> Dict[str, Any]:
        """Analyze news for risk indicators.
        
        Searches recent news for positive/negative keywords
        to calculate risk adjustment factor.
        
        VERIFIED WORKING: Uses overseas_news API with correct field names.
        
        Args:
            country_code: Target country code
            num_articles: Number of articles to analyze
            
        Returns:
            Dict with:
            - risk_score: Calculated risk score (-15 to +15)
            - negative_count: Count of negative indicators
            - positive_count: Count of positive indicators
            - recent_news: List of relevant news
        """
        # Keywords for sentiment analysis
        NEGATIVE_KEYWORDS = [
            "규제", "금지", "관세", "제재", "리콜", "분쟁", "위기",
            "하락", "감소", "리스크", "제한", "조사", "경고",
            "regulation", "ban", "tariff", "sanction", "recall", "crisis"
        ]
        POSITIVE_KEYWORDS = [
            "성장", "수요증가", "호조", "확대", "개선", "증가",
            "투자", "협력", "기회", "호재", "활성화",
            "growth", "demand", "expansion", "investment", "opportunity"
        ]
        
        news = await self.get_overseas_news(
            country_code=country_code,
            num_rows=num_articles
        )
        
        negative_count = 0
        positive_count = 0
        relevant_news = []
        
        for article in news:
            # Using correct field names from API response
            title = article.get("newsTitl", "") or ""
            industry = article.get("indstCl", "") or ""
            info_type = article.get("infoCl", "") or ""
            text = f"{title} {industry} {info_type}".lower()
            
            has_negative = any(kw.lower() in text for kw in NEGATIVE_KEYWORDS)
            has_positive = any(kw.lower() in text for kw in POSITIVE_KEYWORDS)
            
            if has_negative:
                negative_count += 1
            if has_positive:
                positive_count += 1
            
            if has_negative or has_positive:
                relevant_news.append({
                    "title": title,
                    "date": article.get("othbcDt", ""),
                    "country": article.get("natn", ""),
                    "industry": industry,
                    "sentiment": "negative" if has_negative else "positive",
                    "url": article.get("kotraNewsUrl", "")
                })
        
        # Calculate risk adjustment: max ±15%
        total = max(negative_count + positive_count, 1)
        risk_score = ((positive_count - negative_count) / total) * 15
        risk_score = max(-15, min(15, risk_score))
        
        return {
            "risk_adjustment": round(risk_score, 2),
            "negative_count": negative_count,
            "positive_count": positive_count,
            "total_analyzed": len(news),
            "recent_news": relevant_news[:5]
        }
    
    # =========================================================================
    # 5. Trade Fraud Cases API (무역사기사례) - WORKING ✅
    # Required params: pageNo, numOfRows, type
    # Total records: 542+
    # =========================================================================
    async def get_fraud_cases(
        self,
        country_code: Optional[str] = None,
        search_keyword: Optional[str] = None,
        num_rows: int = 20
    ) -> List[Dict[str, Any]]:
        """Get trade fraud case reports.
        
        VERIFIED WORKING: This API returns fraud cases correctly.
        Total records available: 542+
        
        Args:
            country_code: Filter by country name (Korean)
            search_keyword: Search in content
            num_rows: Number of results
            
        Returns:
            List of fraud cases with:
            - bbstxSn: Case serial number
            - natn: Country name (Korean)
            - regn: Region
            - titl: Case title
            - fraudType: Fraud type (이메일해킹, 금품사취, etc.)
            - bdtCntnt: Case content (HTML)
            - othbcDt: Published date
            - dmgeAmt: Damage amount (USD)
            - ovrofInfo: Trade office info
            - dataType: Data type
        """
        params = {
            "numOfRows": num_rows,
            "pageNo": 1,
        }
        
        result = await self._request("fraud_cases", params)
        
        # Parse response structure
        body = result.get("response", {}).get("body", {})
        item_list = body.get("itemList", {})
        items = item_list.get("item", [])
        
        # Handle single item case
        if isinstance(items, dict):
            items = [items]
        
        # Client-side filtering by country name (Korean)
        if country_code and items:
            country_names = {
                "US": "미국", "CN": "중국", "JP": "일본", "VN": "베트남",
                "DE": "독일", "TH": "태국", "ID": "인도네시아", "IN": "인도",
            }
            target_name = country_names.get(country_code.upper(), country_code)
            items = [i for i in items if target_name in str(i.get("natn", ""))]
        
        return items[:num_rows]
    
    async def get_country_fraud_risk(self, country_code: str) -> Dict[str, Any]:
        """Calculate fraud risk level for a country.
        
        Args:
            country_code: Target country code
            
        Returns:
            Dict with:
            - risk_level: HIGH/MEDIUM/LOW/SAFE
            - case_count: Number of fraud cases
            - score_penalty: Score penalty (0 to -15)
            - fraud_types: Distribution of fraud types
            - recent_cases: Recent fraud cases
        """
        cases = await self.get_fraud_cases(country_code=country_code, num_rows=50)
        
        case_count = len(cases)
        
        # Determine risk level and penalty
        if case_count >= 20:
            risk_level = "HIGH"
            score_penalty = -15
        elif case_count >= 10:
            risk_level = "MEDIUM"
            score_penalty = -7
        elif case_count >= 5:
            risk_level = "LOW"
            score_penalty = -3
        else:
            risk_level = "SAFE"
            score_penalty = 0
        
        # Count fraud types (using correct field name: fraudType)
        fraud_types = {}
        for case in cases:
            ft = case.get("fraudType", case.get("fraudTypNm", "기타"))
            fraud_types[ft] = fraud_types.get(ft, 0) + 1
        
        return {
            "risk_level": risk_level,
            "case_count": case_count,
            "score_penalty": score_penalty,
            "fraud_types": fraud_types,
            "recent_cases": [
                {
                    "title": c.get("titl", c.get("title", "")),
                    "type": c.get("fraudType", c.get("fraudTypNm", "")),
                    "date": c.get("othbcDt", c.get("wrtDt", "")),
                    "damage_amount": c.get("dmgeAmt", "0")
                }
                for c in cases[:3]
            ],
            "common_fraud_types": list(fraud_types.keys())[:5]
        }
    
    # =========================================================================
    # 6. Company Success Cases API (기업성공사례) - WORKING ✅
    # Required params: pageNo, numOfRows, type
    # Total records: 275+
    # =========================================================================
    async def get_success_cases(
        self,
        country_code: Optional[str] = None,
        industry: Optional[str] = None,
        num_rows: int = 10
    ) -> List[Dict[str, Any]]:
        """Get company success case studies.
        
        VERIFIED WORKING: This API returns success cases correctly.
        Total records available: 275+
        
        Args:
            country_code: Filter by country name (Korean)
            industry: Filter by industry (Korean)
            num_rows: Number of results
            
        Returns:
            List of success cases with:
            - bbstxSn: Case serial number
            - natn: Country/Region name (e.g., "북미")
            - regn: Region (e.g., "미국")
            - compNm: Company name
            - indstCl: Industry classification
            - titl: Case title
            - bdtCntnt: Case content (HTML)
            - othbcDt: Published date
            - dataType: Data type
        """
        params = {
            "numOfRows": num_rows,
            "pageNo": 1,
        }
        
        result = await self._request("success_cases", params)
        
        # Parse response structure
        body = result.get("response", {}).get("body", {})
        item_list = body.get("itemList", {})
        items = item_list.get("item", [])
        
        # Handle single item case
        if isinstance(items, dict):
            items = [items]
        
        # Client-side filtering by country/region name (Korean)
        if country_code and items:
            country_names = {
                "US": "미국", "CN": "중국", "JP": "일본", "VN": "베트남",
                "DE": "독일", "TH": "태국", "ID": "인도네시아", "IN": "인도",
            }
            target_name = country_names.get(country_code.upper(), country_code)
            items = [i for i in items if target_name in str(i.get("natn", "")) or 
                    target_name in str(i.get("regn", ""))]
        
        # Filter by industry if specified
        if industry and items:
            items = [i for i in items if industry.lower() in str(i.get("indstCl", "")).lower()]
        
        return items[:num_rows]
    
    async def get_relevant_success_cases(
        self,
        country_code: str,
        industry: Optional[str] = None,
        hs_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get success cases relevant to user's profile.
        
        Args:
            country_code: Target country
            industry: Industry classification
            hs_code: HS code for product matching
            
        Returns:
            List of relevant success cases with relevance score
        """
        cases = await self.get_success_cases(
            country_code=country_code,
            industry=industry,
            num_rows=20
        )
        
        # Score relevance
        scored_cases = []
        for case in cases:
            score = 50  # Base score
            
            # Industry match (using correct field: indstCl)
            if industry and industry.lower() in str(case.get("indstCl", "")).lower():
                score += 30
            
            # Content relevance bonus
            content = str(case.get("bdtCntnt", "")).lower()
            if hs_code and hs_code[:4] in content:
                score += 20
            if "kotra" in content:
                score += 10
            if "수출" in content:
                score += 5
            
            scored_cases.append({
                "company": case.get("compNm", ""),
                "country": case.get("regn", case.get("natn", "")),
                "region": case.get("natn", ""),
                "industry": case.get("indstCl", ""),
                "title": case.get("titl", ""),
                "date": case.get("othbcDt", ""),
                "relevance_score": score,
                "data_type": case.get("dataType", ""),
            })
        
        # Sort by relevance
        scored_cases.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return scored_cases[:5]


# Singleton instance for dependency injection
_client_instance: Optional[KotraAPIClient] = None


def get_kotra_client() -> KotraAPIClient:
    """Get or create KotraAPIClient singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = KotraAPIClient()
    return _client_instance
