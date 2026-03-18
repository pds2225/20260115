"""Step 4 — 연락처 확보 (의사결정권자 직접 연락처)
- Hunter.io API: 이메일 주소 검색 및 검증
- Apollo.io API: B2B 연락처 enrichment
- LinkedIn 패턴 추정: domain → 이메일 포맷 추정
- 전화번호: 국가별 포맷 추정
"""
import os
import asyncio
import httpx
import re
from backend.models.schemas import (
    ContactEnrichRequest, ContactEnrichResult,
    DecisionMakerContact, ContactChannel, ActiveBuyer, BuyerVerificationResult
)

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

# 의사결정권자 직책 우선순위 (높을수록 우선)
DECISION_MAKER_TITLES = [
    "CEO", "Managing Director", "Director", "Import Manager",
    "Purchasing Manager", "Procurement Manager", "General Director",
    "Co-Founder", "Founder", "President", "VP of Operations",
    "Head of Purchasing", "Supply Chain Manager",
]

# 국가별 이메일 도메인 패턴
COUNTRY_DOMAIN_HINTS = {
    "VN": [".com.vn", ".vn"],
    "TH": [".co.th", ".th"],
    "US": [".com"],
    "DE": [".de", ".com"],
    "JP": [".co.jp", ".jp"],
}

# Mock 연락처 데이터 (Hunter.io / Apollo.io 실연동 전 사용)
MOCK_CONTACTS_DB = {
    "Saigon Cosmetics Import JSC": {
        "domain": "saigoncosmetics.com.vn",
        "contacts": [
            {
                "name": "Nguyễn Thị Hương",
                "title": "Import Director",
                "email": "huong.nguyen@saigoncosmetics.com.vn",
                "email_confidence": 0.92,
                "phone": "+84-28-3823-4567",
                "linkedin_url": "https://linkedin.com/in/huong-nguyen-import",
            }
        ],
    },
    "Korea Beauty VN Import": {
        "domain": "kbeautyvn.com",
        "contacts": [
            {
                "name": "Park Ji-Young",
                "title": "CEO",
                "email": "jiyoung@kbeautyvn.com",
                "email_confidence": 0.88,
                "phone": "+84-90-123-4567",
                "linkedin_url": None,
            }
        ],
    },
    "Vietnam Beauty Trading Co.": {
        "domain": "vnbeautytrading.vn",
        "contacts": [
            {
                "name": "Trần Văn Nam",
                "title": "Purchasing Manager",
                "email": "nam.tran@vnbeautytrading.vn",
                "email_confidence": 0.85,
                "phone": "+84-24-3678-9012",
                "linkedin_url": None,
            }
        ],
    },
    "Hanoi Skincare Distribution": {
        "domain": "hanoiskindist.vn",
        "contacts": [
            {
                "name": "Lê Thị Mai",
                "title": "Managing Director",
                "email": "mai.le@hanoiskindist.vn",
                "email_confidence": 0.90,
                "phone": "+84-24-3891-2345",
                "linkedin_url": "https://linkedin.com/in/mai-le-hanoi",
            }
        ],
    },
    "VN Premium Skincare": {
        "domain": "vnpremiumskin.com",
        "contacts": [
            {
                "name": "Đinh Quốc Hùng",
                "title": "Import Manager",
                "email": "hung.dinh@vnpremiumskin.com",
                "email_confidence": 0.87,
                "phone": "+84-91-456-7890",
                "linkedin_url": None,
            }
        ],
    },
}


async def hunter_domain_search(domain: str, company: str) -> list:
    """Hunter.io Domain Search API"""
    if not HUNTER_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/domain-search",
                params={
                    "domain": domain,
                    "company": company,
                    "api_key": HUNTER_API_KEY,
                    "limit": 5,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                emails = data.get("data", {}).get("emails", [])
                return [
                    {
                        "name": f"{e.get('first_name', '')} {e.get('last_name', '')}".strip(),
                        "title": e.get("position", ""),
                        "email": e.get("value", ""),
                        "email_confidence": e.get("confidence", 0) / 100,
                        "phone": None,
                        "linkedin_url": e.get("linkedin", None),
                        "source": "hunter.io",
                    }
                    for e in emails
                    if e.get("position", "").lower() in [t.lower() for t in DECISION_MAKER_TITLES]
                ]
    except Exception:
        pass
    return []


async def apollo_people_search(company: str, domain: str = None) -> list:
    """Apollo.io People Search API"""
    if not APOLLO_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "q_organization_name": company,
                "person_titles": DECISION_MAKER_TITLES[:5],
                "page": 1,
                "per_page": 5,
            }
            if domain:
                payload["q_organization_domains"] = [domain]

            resp = await client.post(
                "https://api.apollo.io/api/v1/mixed_people/search",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": APOLLO_API_KEY,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                people = data.get("people", [])
                return [
                    {
                        "name": p.get("name", ""),
                        "title": p.get("title", ""),
                        "email": p.get("email", ""),
                        "email_confidence": 0.85 if p.get("email") else 0,
                        "phone": p.get("phone_numbers", [{}])[0].get("sanitized_number") if p.get("phone_numbers") else None,
                        "linkedin_url": p.get("linkedin_url"),
                        "source": "apollo.io",
                    }
                    for p in people
                    if p.get("title", "").lower() in [t.lower() for t in DECISION_MAKER_TITLES]
                ]
    except Exception:
        pass
    return []


def estimate_email(name: str, domain: str) -> tuple[str, float]:
    """이메일 포맷 추정 (Hunter.io 패턴 기반)"""
    if not name or not domain:
        return ("", 0.3)
    parts = name.lower().split()
    if len(parts) >= 2:
        # 가장 흔한 포맷들
        formats = [
            f"{parts[0]}.{parts[-1]}@{domain}",  # john.doe
            f"{parts[0][0]}.{parts[-1]}@{domain}",  # j.doe
            f"{parts[0]}@{domain}",  # john
            f"{parts[-1]}@{domain}",  # doe
        ]
        return (formats[0], 0.55)  # 첫 포맷이 가장 일반적
    return (f"{parts[0]}@{domain}", 0.45)


def get_mock_contacts(company_name: str) -> list:
    """Mock 연락처 DB 조회"""
    # 완전 일치
    if company_name in MOCK_CONTACTS_DB:
        return MOCK_CONTACTS_DB[company_name]["contacts"]

    # 부분 일치
    for key, val in MOCK_CONTACTS_DB.items():
        if key.lower() in company_name.lower() or company_name.lower() in key.lower():
            return val["contacts"]
    return []


def get_mock_domain(company_name: str) -> str:
    if company_name in MOCK_CONTACTS_DB:
        return MOCK_CONTACTS_DB[company_name]["domain"]
    # 도메인 추정
    clean = re.sub(r"[^\w\s]", "", company_name.lower())
    words = clean.split()[:3]
    domain_part = "".join(words)
    return f"{domain_part}.com"


class ContactEnricher:
    """Step 4: 연락처 확보 서비스"""

    async def enrich(self, buyer: ActiveBuyer) -> ContactEnrichResult:
        company = buyer.company_name
        domain = get_mock_domain(company)

        # 병렬 조회: Hunter.io + Apollo.io
        hunter_task = hunter_domain_search(domain, company)
        apollo_task = apollo_people_search(company, domain)
        hunter_results, apollo_results = await asyncio.gather(hunter_task, apollo_task)

        # Mock fallback
        mock_results = get_mock_contacts(company)

        # 중복 제거하여 통합
        all_raw = hunter_results + apollo_results
        if not all_raw:
            all_raw = mock_results

        contacts = []
        seen_emails = set()

        for r in all_raw:
            email = r.get("email", "")
            if email and email in seen_emails:
                continue
            if email:
                seen_emails.add(email)

            channels = []
            if r.get("email"):
                channels.append(ContactChannel.EMAIL)
            if r.get("phone"):
                channels.append(ContactChannel.PHONE)
            if r.get("linkedin_url"):
                channels.append(ContactChannel.LINKEDIN)

            contacts.append(
                DecisionMakerContact(
                    name=r.get("name") or None,
                    title=r.get("title") or None,
                    email=r.get("email") or None,
                    email_confidence=r.get("email_confidence", 0.7),
                    phone=r.get("phone") or None,
                    linkedin_url=r.get("linkedin_url") or None,
                    channel=channels or [ContactChannel.EMAIL],
                    source=r.get("source", "mock"),
                )
            )

        # 의사결정권자 우선 정렬
        def dm_rank(c: DecisionMakerContact) -> int:
            if not c.title:
                return 99
            for i, title in enumerate(DECISION_MAKER_TITLES):
                if title.lower() in (c.title or "").lower():
                    return i
            return 50

        contacts.sort(key=lambda c: (dm_rank(c), -(c.email_confidence or 0)))

        best = contacts[0] if contacts else None

        return ContactEnrichResult(
            company_name=company,
            domain=domain,
            contacts=contacts,
            total_contacts_found=len(contacts),
            best_contact=best,
        )

    async def enrich_batch(self, buyers: list[ActiveBuyer]) -> list[ContactEnrichResult]:
        tasks = [self.enrich(buyer) for buyer in buyers]
        return await asyncio.gather(*tasks)
