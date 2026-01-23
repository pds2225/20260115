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
    # =========================================================================
    async def get_export_recommendations(
        self,
        hs_code: str,
        export_scale: Optional[str] = None,
        num_rows: int = 20
    ) -> List[Dict[str, Any]]:
        """Get ML-based export recommendation scores.
        
        Uses CatBoost model to predict export success probability.
        
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
        params = {
            "numOfRows": num_rows,
        }
        
        # Filter by HS code if provided
        # Note: API may require specific filtering mechanism
        
        result = await self._request("export_recommend", params)
        
        records = result.get("records", [])
        
        # Filter by HS code (first 4 digits match)
        if hs_code and records:
            hs_prefix = hs_code[:4]
            records = [
                r for r in records 
                if r.get("HSCD", "").startswith(hs_prefix)
            ]
        
        # Sort by score descending
        records.sort(key=lambda x: float(x.get("EXP_BHRC_SCR", 0)), reverse=True)
        
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
    # 3. Product DB API (상품DB)
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
        
        Args:
            country_code: Filter by country
            search_keyword: Search in product name/content
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            num_rows: Number of results
            
        Returns:
            List of product entries with:
            - bbstxSn: Article serial number
            - natn: Country name
            - regn: Region
            - newsTitl: Title
            - cntntSumar: Summary
            - cmdltNmKorn: Product name (Korean)
            - hsCdNm: HS Code name
            - indstCl: Industry classification
            - othbcDt: Published date
            - kotraNewsUrl: Detail URL
        """
        params = {
            "numOfRows": num_rows,
        }
        
        if search_keyword:
            params["search"] = search_keyword
        
        result = await self._request("product_db", params)
        
        items = result.get("items", result.get("data", []))
        
        # Filter by country if specified
        if country_code and items:
            items = [i for i in items if country_code.upper() in str(i.get("natn", "")).upper()]
        
        return items[:num_rows]
    
    # =========================================================================
    # 4. Overseas Market News API (해외시장뉴스)
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
        
        Args:
            country_code: Filter by country (search1 parameter)
            search_keyword: Search in title (search2 parameter)
            from_date: Start date for search3
            to_date: End date for search4
            num_rows: Number of results
            
        Returns:
            List of news articles with:
            - nttSn: Article serial number
            - natCd: Country code
            - natNm: Country name
            - newsCdNm: News category
            - title: News title
            - cntnt: Content
            - wrtDt: Written date
            - kbcNm: Trade office name
            - url: Detail URL
        """
        params = {
            "numOfRows": num_rows,
        }
        
        if country_code:
            params["search1"] = country_code  # Country name filter
        if search_keyword:
            params["search2"] = search_keyword  # Title filter
        
        result = await self._request("overseas_news", params)
        
        return result.get("items", result.get("data", []))[:num_rows]
    
    async def analyze_news_risk(
        self,
        country_code: str,
        num_articles: int = 50
    ) -> Dict[str, Any]:
        """Analyze news for risk indicators.
        
        Searches recent news for positive/negative keywords
        to calculate risk adjustment factor.
        
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
            title = article.get("title", "") or ""
            content = article.get("cntnt", "") or ""
            text = f"{title} {content}".lower()
            
            has_negative = any(kw.lower() in text for kw in NEGATIVE_KEYWORDS)
            has_positive = any(kw.lower() in text for kw in POSITIVE_KEYWORDS)
            
            if has_negative:
                negative_count += 1
            if has_positive:
                positive_count += 1
            
            if has_negative or has_positive:
                relevant_news.append({
                    "title": title,
                    "date": article.get("wrtDt", ""),
                    "sentiment": "negative" if has_negative else "positive"
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
    # 5. Trade Fraud Cases API (무역사기사례)
    # =========================================================================
    async def get_fraud_cases(
        self,
        country_code: Optional[str] = None,
        search_keyword: Optional[str] = None,
        num_rows: int = 20
    ) -> List[Dict[str, Any]]:
        """Get trade fraud case reports.
        
        Args:
            country_code: Filter by country
            search_keyword: Search in content
            num_rows: Number of results
            
        Returns:
            List of fraud cases with:
            - nttSn: Case serial number
            - natCd: Country code
            - natNm: Country name
            - title: Case title
            - fraudTypNm: Fraud type name
            - cntnt: Case content
            - wrtDt: Written date
            - prvntMthd: Prevention method
            - kbcNm: Trade office name
        """
        params = {
            "numOfRows": num_rows,
        }
        
        if search_keyword:
            params["search"] = search_keyword
        
        result = await self._request("fraud_cases", params)
        
        items = result.get("items", result.get("data", []))
        
        # Filter by country if specified
        if country_code and items:
            items = [i for i in items if country_code.upper() in str(i.get("natNm", "")).upper()]
        
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
        
        # Count fraud types
        fraud_types = {}
        for case in cases:
            ft = case.get("fraudTypNm", "기타")
            fraud_types[ft] = fraud_types.get(ft, 0) + 1
        
        return {
            "risk_level": risk_level,
            "case_count": case_count,
            "score_penalty": score_penalty,
            "fraud_types": fraud_types,
            "recent_cases": [
                {
                    "title": c.get("title", ""),
                    "type": c.get("fraudTypNm", ""),
                    "date": c.get("wrtDt", ""),
                    "prevention": c.get("prvntMthd", "")
                }
                for c in cases[:3]
            ],
            "prevention_tips": list(set(
                c.get("prvntMthd", "") for c in cases if c.get("prvntMthd")
            ))[:5]
        }
    
    # =========================================================================
    # 6. Company Success Cases API (기업성공사례)
    # =========================================================================
    async def get_success_cases(
        self,
        country_code: Optional[str] = None,
        industry: Optional[str] = None,
        num_rows: int = 10
    ) -> List[Dict[str, Any]]:
        """Get company success case studies.
        
        Args:
            country_code: Filter by country
            industry: Filter by industry
            num_rows: Number of results
            
        Returns:
            List of success cases with:
            - nttSn: Case serial number
            - natCd: Country code
            - natNm: Country name
            - corpNm: Company name
            - indutyNm: Industry name
            - title: Case title
            - cntnt: Case content
            - entryTypNm: Entry type name
            - wrtDt: Written date
            - url: Detail URL
        """
        params = {
            "numOfRows": num_rows,
        }
        
        if industry:
            params["search"] = industry
        
        result = await self._request("success_cases", params)
        
        items = result.get("items", result.get("data", []))
        
        # Filter by country if specified
        if country_code and items:
            items = [i for i in items if country_code.upper() in str(i.get("natNm", "")).upper()]
        
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
            
            # Industry match
            if industry and industry.lower() in str(case.get("indutyNm", "")).lower():
                score += 30
            
            # Entry type bonus
            entry_type = case.get("entryTypNm", "")
            if "직접수출" in entry_type:
                score += 10
            elif "현지법인" in entry_type:
                score += 5
            
            scored_cases.append({
                "company": case.get("corpNm", ""),
                "country": case.get("natNm", ""),
                "industry": case.get("indutyNm", ""),
                "title": case.get("title", ""),
                "entry_type": entry_type,
                "date": case.get("wrtDt", ""),
                "relevance_score": score,
                "url": case.get("url", ""),
                "summary": (case.get("cntnt", "") or "")[:200] + "..."
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
