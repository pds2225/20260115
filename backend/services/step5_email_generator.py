"""Step 5 — 맞춤형 이메일 생성
GPT-4o 기반 AI 개인화 컨택 메시지 + 현지 언어 자동 생성
"""
import os
from openai import AsyncOpenAI
from backend.models.schemas import (
    EmailGenerationRequest, EmailGenerationResult, GeneratedEmail,
    ActiveBuyer, ContactEnrichResult, DecisionMakerContact
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 언어별 이메일 템플릿 (GPT 없을 때 fallback)
EMAIL_TEMPLATES = {
    "en": {
        "subject": "Partnership Opportunity: {product} Supply from Korea — {hs_code}",
        "greeting": "Dear {contact_name},",
        "opener": "I hope this message finds you well. My name is [Representative Name] from {seller_company}, a specialized Korean exporter of {product}.",
        "hook": "I came across your company, {buyer_company}, through trade data analysis and noticed your consistent import activity in our product category over the past 6 months — {shipment_count} shipments totaling ${trade_value:,.0f} USD.",
        "value_prop": "We believe there is strong synergy between our offerings and your procurement needs. {usp}",
        "cta": "Would you be available for a 20-minute call this week or next to explore a potential collaboration?",
        "closing": "Best regards,\n[Representative Name]\n{seller_company}\n[Phone] | [Email]",
    },
    "vi": {
        "subject": "Cơ hội hợp tác: Cung cấp {product} từ Hàn Quốc — {hs_code}",
        "greeting": "Kính gửi {contact_name},",
        "opener": "Tôi là [Tên Đại Diện] từ công ty {seller_company}, chuyên xuất khẩu {product} từ Hàn Quốc.",
        "hook": "Qua phân tích dữ liệu thương mại, tôi nhận thấy công ty {buyer_company} đã nhập khẩu sản phẩm trong danh mục của chúng tôi đều đặn trong 6 tháng qua — {shipment_count} lô hàng với tổng giá trị ${trade_value:,.0f} USD.",
        "value_prop": "Chúng tôi tin rằng có sự phù hợp tuyệt vời giữa sản phẩm của chúng tôi và nhu cầu nhập khẩu của quý công ty. {usp}",
        "cta": "Quý vị có thể sắp xếp một cuộc trao đổi 20 phút trong tuần này hoặc tuần tới để chúng tôi tìm hiểu về cơ hội hợp tác không?",
        "closing": "Trân trọng,\n[Tên Đại Diện]\n{seller_company}",
    },
    "ko": {
        "subject": "파트너십 제안: 한국산 {product} 공급 — HS {hs_code}",
        "greeting": "{contact_name} 담당자님께,",
        "opener": "안녕하세요. 저는 한국 {product} 전문 수출기업 {seller_company}의 [담당자 이름]입니다.",
        "hook": "무역 데이터 분석을 통해 {buyer_company}가 최근 6개월간 당사 제품 카테고리에서 활발한 수입 활동({shipment_count}건, 총 ${trade_value:,.0f} USD)을 이어오고 있음을 확인했습니다.",
        "value_prop": "저희 제품과 귀사의 수입 니즈 간에 강력한 시너지가 있다고 판단합니다. {usp}",
        "cta": "이번 주 또는 다음 주 중 20분 정도 통화가 가능하실까요?",
        "closing": "감사합니다.\n[담당자 이름]\n{seller_company}",
    },
}

FOLLOW_UP_TEMPLATES = {
    "en": [
        "Follow-up #1 (3 days): Gentle reminder — resend subject with 'RE:' prefix and attach product catalog",
        "Follow-up #2 (7 days): Value-add email — share case study of similar Korean exporter's success in their market",
        "Follow-up #3 (14 days): Final attempt — offer free sample shipment or virtual product demo call",
    ],
    "vi": [
        "Nhắc lại lần 1 (3 ngày): Gửi lại email với tiêu đề 'RE:' và đính kèm catalogue sản phẩm",
        "Nhắc lại lần 2 (7 ngày): Chia sẻ case study thành công của nhà xuất khẩu Hàn Quốc tại thị trường tương tự",
        "Nhắc lại lần 3 (14 ngày): Đề nghị gửi mẫu miễn phí hoặc demo sản phẩm trực tuyến",
    ],
}


def _build_template_email(req: EmailGenerationRequest) -> GeneratedEmail:
    """템플릿 기반 이메일 생성 (GPT 없을 때 fallback)"""
    lang = req.target_language if req.target_language in EMAIL_TEMPLATES else "en"
    tmpl = EMAIL_TEMPLATES[lang]

    contact_name = req.contact.name or "Sir/Madam"
    usp = req.seller_usp or (
        "Our products are certified to international standards (ISO/FDA/CE) "
        "and competitively priced with flexible MOQ."
    )

    fmt_args = {
        "product": req.seller_product,
        "hs_code": req.hs_code,
        "contact_name": contact_name,
        "seller_company": req.seller_company,
        "buyer_company": req.target_buyer.company_name,
        "shipment_count": req.target_buyer.shipment_count,
        "trade_value": req.target_buyer.total_trade_value_usd,
        "usp": usp,
    }

    body_parts = [
        tmpl["greeting"].format(**fmt_args),
        "",
        tmpl["opener"].format(**fmt_args),
        "",
        tmpl["hook"].format(**fmt_args),
        "",
        tmpl["value_prop"].format(**fmt_args),
        "",
        tmpl["cta"].format(**fmt_args),
        "",
        tmpl["closing"].format(**fmt_args),
    ]

    personalization_points = [
        f"바이어 거래 이력 활용: {req.target_buyer.shipment_count}회 수입, ${req.target_buyer.total_trade_value_usd:,.0f}",
        f"의사결정권자 직접 지목: {contact_name} ({req.contact.title or 'N/A'})",
        f"HS 코드 특정: {req.hs_code} ({req.seller_product})",
        "현지 언어 작성" if lang != "en" else "영어 전문 작성",
    ]

    follow_ups = FOLLOW_UP_TEMPLATES.get(lang, FOLLOW_UP_TEMPLATES["en"])

    return GeneratedEmail(
        subject=tmpl["subject"].format(**fmt_args),
        body="\n".join(body_parts),
        language=lang,
        personalization_points=personalization_points,
        call_to_action=tmpl["cta"].format(**fmt_args),
    ), follow_ups


async def _gpt_generate_email(req: EmailGenerationRequest) -> tuple[GeneratedEmail, list]:
    """GPT-4o 기반 이메일 생성"""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    lang_label = {"en": "English", "vi": "Vietnamese", "ko": "Korean"}.get(req.target_language, "English")
    contact_info = f"{req.contact.name or 'the decision maker'} ({req.contact.title or 'Import Manager'})"

    prompt = f"""You are a professional B2B export sales email writer for a Korean company.

Write a personalized cold outreach email with these specifications:
- Language: {lang_label}
- Tone: {req.tone}
- From: {req.seller_company} (Korean exporter of {req.seller_product}, HS code {req.hs_code})
- To: {contact_info} at {req.target_buyer.company_name} ({req.target_buyer.country})
- Buyer activity: {req.target_buyer.shipment_count} shipments in last 6 months, ${req.target_buyer.total_trade_value_usd:,.0f} total trade value
- Average order: ${req.target_buyer.average_order_value_usd:,.0f}
- USP: {req.seller_usp or "Quality Korean products with international certifications"}

Requirements:
1. Reference their specific trade activity data (shows research)
2. Be concise (under 200 words)
3. Clear value proposition
4. One specific CTA (call or meeting request)
5. Professional closing

Return JSON with these fields:
{{
  "subject": "email subject line",
  "body": "full email body",
  "personalization_points": ["point1", "point2", "point3"],
  "call_to_action": "the specific CTA used"
}}"""

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        import json
        result = json.loads(resp.choices[0].message.content)
        email = GeneratedEmail(
            subject=result["subject"],
            body=result["body"],
            language=req.target_language,
            personalization_points=result.get("personalization_points", []),
            call_to_action=result.get("call_to_action", ""),
        )
        follow_ups = FOLLOW_UP_TEMPLATES.get(req.target_language, FOLLOW_UP_TEMPLATES["en"])
        return email, follow_ups
    except Exception as e:
        # GPT 실패 시 템플릿으로 fallback
        return _build_template_email(req)


class EmailGenerator:
    """Step 5: 맞춤형 이메일 생성 서비스"""

    async def generate(
        self,
        buyer: ActiveBuyer,
        contact_result: ContactEnrichResult,
        seller_company: str,
        seller_product: str,
        hs_code: str,
        language: str = "en",
        seller_usp: str = None,
    ) -> EmailGenerationResult:
        best_contact = contact_result.best_contact
        if not best_contact:
            best_contact = DecisionMakerContact(
                name=None,
                title="Import Manager",
                email=None,
                email_confidence=0,
                phone=None,
                linkedin_url=None,
                channel=[],
                source="estimated",
            )

        req = EmailGenerationRequest(
            seller_company=seller_company,
            seller_product=seller_product,
            hs_code=hs_code,
            target_buyer=buyer,
            contact=best_contact,
            target_language=language,
            seller_usp=seller_usp,
        )

        if OPENAI_API_KEY:
            email, follow_ups = await _gpt_generate_email(req)
        else:
            email, follow_ups = _build_template_email(req)

        return EmailGenerationResult(
            buyer_company=buyer.company_name,
            contact_name=best_contact.name,
            email_address=best_contact.email,
            generated_email=email,
            follow_up_sequence=follow_ups,
        )

    async def generate_batch(
        self,
        buyers: list[ActiveBuyer],
        contact_results: list[ContactEnrichResult],
        seller_company: str,
        seller_product: str,
        hs_code: str,
        language: str = "en",
        seller_usp: str = None,
    ) -> list[EmailGenerationResult]:
        import asyncio
        tasks = [
            self.generate(buyer, contact, seller_company, seller_product, hs_code, language, seller_usp)
            for buyer, contact in zip(buyers, contact_results)
        ]
        return await asyncio.gather(*tasks)
