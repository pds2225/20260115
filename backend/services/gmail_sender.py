"""
Gmail SMTP 실연동 이메일 발송 모듈
✅ 실제 작동 확인: Gmail App Password 기반 발송

환경변수:
    GMAIL_ADDRESS       — 발신 Gmail 주소 (예: yourname@gmail.com)
    GMAIL_APP_PASSWORD  — Gmail 앱 비밀번호 (2단계 인증 후 발급)
                          구글 계정 → 보안 → 앱 비밀번호

Gmail 앱 비밀번호 발급 방법:
  1. https://myaccount.google.com/security
  2. 2단계 인증 활성화
  3. 앱 비밀번호 → "메일" + "기타(직접 입력)" → 생성
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465  # SSL


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class EmailMessage:
    """발송할 이메일 메시지."""
    to_address: str
    subject: str
    body_text: str                        # 플레인 텍스트
    body_html: str = ""                   # HTML (선택)
    reply_to: str = ""
    cc: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)   # 추적용 태그 (메타데이터)


@dataclass
class SendResult:
    """이메일 발송 결과."""
    to_address: str
    success: bool
    message_id: str = ""
    error: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return f"✅ {self.to_address} 발송 완료"
        return f"❌ {self.to_address} 발송 실패: {self.error}"


# ---------------------------------------------------------------------------
# Gmail 발송 클라이언트
# ---------------------------------------------------------------------------

class GmailSender:
    """
    Gmail SMTP SSL 기반 이메일 발송 클라이언트.

    실제 작동 확인 (2026-03-18):
    - ImportGenius·TradeInt·Panjiva 초안 3개사 실제 발송 성공
    """

    def __init__(
        self,
        gmail_address: Optional[str] = None,
        app_password: Optional[str] = None,
    ):
        self.gmail_address = gmail_address or os.getenv("GMAIL_ADDRESS", "")
        self.app_password = app_password or os.getenv("GMAIL_APP_PASSWORD", "")
        self._available = bool(self.gmail_address and self.app_password)

    # ------------------------------------------------------------------
    # 단일 발송
    # ------------------------------------------------------------------

    def send(self, message: EmailMessage) -> SendResult:
        """
        단일 이메일을 발송한다.

        Args:
            message: 발송할 이메일 메시지

        Returns:
            SendResult
        """
        if not self._available:
            logger.warning("Gmail credentials not set. Cannot send email.")
            return SendResult(
                to_address=message.to_address,
                success=False,
                error="Gmail 인증 정보 미설정 (GMAIL_ADDRESS / GMAIL_APP_PASSWORD)",
            )

        try:
            msg = self._build_mime(message)
            context = ssl.create_default_context()

            with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, context=context) as server:
                server.login(self.gmail_address, self.app_password)
                server.sendmail(
                    self.gmail_address,
                    [message.to_address] + message.cc,
                    msg.as_string(),
                )

            logger.info("Email sent to %s", message.to_address)
            return SendResult(
                to_address=message.to_address,
                success=True,
                message_id=msg["Message-ID"] or "",
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error("Gmail auth error: %s", e)
            return SendResult(
                to_address=message.to_address,
                success=False,
                error="Gmail 인증 실패 — 앱 비밀번호를 확인하세요",
            )
        except smtplib.SMTPRecipientsRefused as e:
            logger.error("Recipient refused: %s", e)
            return SendResult(
                to_address=message.to_address,
                success=False,
                error=f"수신 주소 거부: {message.to_address}",
            )
        except Exception as e:
            logger.error("Gmail send error: %s", e)
            return SendResult(
                to_address=message.to_address,
                success=False,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # 배치 발송
    # ------------------------------------------------------------------

    def send_batch(
        self,
        messages: list[EmailMessage],
        delay_seconds: float = 2.0,
    ) -> list[SendResult]:
        """
        여러 이메일을 순차 발송한다. (스팸 방지 딜레이 포함)

        Args:
            messages: 발송할 이메일 목록
            delay_seconds: 발송 간격 (기본 2초 — Gmail 속도 제한 방지)

        Returns:
            SendResult 목록
        """
        import time
        results = []
        for i, msg in enumerate(messages):
            result = self.send(msg)
            results.append(result)
            if i < len(messages) - 1:
                time.sleep(delay_seconds)
        return results

    # ------------------------------------------------------------------
    # 이메일 미리보기 (발송 없이 내용 확인)
    # ------------------------------------------------------------------

    def preview(self, message: EmailMessage) -> str:
        """발송 없이 이메일 내용을 문자열로 반환한다."""
        lines = [
            f"From   : {self.gmail_address or '(미설정)'}",
            f"To     : {message.to_address}",
            f"Subject: {message.subject}",
            "─" * 60,
            message.body_text,
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        """MIME 메시지 객체를 생성한다."""
        import uuid
        msg = MIMEMultipart("alternative")
        msg["From"] = self.gmail_address
        msg["To"] = message.to_address
        msg["Subject"] = message.subject
        msg["Message-ID"] = f"<{uuid.uuid4().hex}@valueupai>"
        if message.reply_to:
            msg["Reply-To"] = message.reply_to
        if message.cc:
            msg["Cc"] = ", ".join(message.cc)

        # 플레인 텍스트
        msg.attach(MIMEText(message.body_text, "plain", "utf-8"))

        # HTML (있을 경우)
        if message.body_html:
            msg.attach(MIMEText(message.body_html, "html", "utf-8"))

        return msg

    @property
    def is_available(self) -> bool:
        return self._available


# ---------------------------------------------------------------------------
# 이메일 템플릿 빌더 (VALUE-UP AI 아웃리치용)
# ---------------------------------------------------------------------------

def build_outreach_email(
    sender_company: str,
    sender_product: str,
    buyer_company: str,
    contact_name: str,
    contact_email: str,
    monthly_volume_usd: float,
    credit_grade: str = "A",
    payment_terms: str = "T/T 30일",
    certifications: list[str] | None = None,
    moq: int = 0,
    unit_price_usd: float = 0.0,
    language: str = "en",
) -> EmailMessage:
    """
    VALUE-UP AI 파이프라인 통과 바이어에게 보낼 아웃리치 이메일을 생성한다.

    Args:
        sender_company: 셀러 회사명
        sender_product: 제품명
        buyer_company: 바이어 회사명
        contact_name: 담당자 이름
        contact_email: 담당자 이메일
        monthly_volume_usd: 월 수입 규모 ($)
        credit_grade: 신용등급 (A/B/C)
        payment_terms: 결제 조건
        certifications: 인증 목록
        moq: 최소주문수량
        unit_price_usd: 단가 ($)
        language: "en" | "ko"

    Returns:
        EmailMessage
    """
    certs = certifications or []
    cert_str = ", ".join(certs) if certs else "ISO22716"
    moq_str = f"{moq:,} units @ ${unit_price_usd:.2f}/pc" if moq > 0 else "Flexible MOQ"
    vol_str = f"${monthly_volume_usd:,.0f}/month"

    if language == "ko":
        subject = f"[수출 제안] {sender_product} 공급 협력 제안 — {buyer_company}"
        body = f"""안녕하세요, {contact_name or '담당자'} 님,

저는 {sender_company}의 수출 담당자입니다.

귀사({buyer_company})의 수입 이력 분석을 통해 당사 제품과 높은 적합성을 확인하였습니다.

■ 제품 정보
  - 제품: {sender_product}
  - 인증: {cert_str}
  - MOQ/단가: {moq_str}

■ 협력 제안
  귀사의 월 수입 규모({vol_str})에 적합한 공급 조건을 제안드립니다.
  결제 조건: {payment_terms}

관심이 있으시면 30분 화상 미팅을 요청드립니다.

감사합니다.
{sender_company} 드림"""
    else:
        greeting = f"Dear {contact_name}," if contact_name and contact_name != "(담당자미상)" else "Dear Purchasing Manager,"
        subject = f"Partnership Opportunity: {sender_product} Supply from Korea"
        body = f"""{greeting}

I hope this message finds you well. I am reaching out from {sender_company}, a Korean exporter specializing in {sender_product}.

Through trade data analysis, I identified {buyer_company} as a strong potential partner based on your consistent import activity in this product category ({vol_str}).

■ Why Partner with Us?
  • Product: {sender_product}
  • Certifications: {cert_str}
  • MOQ / Unit Price: {moq_str}
  • Payment Terms: {payment_terms} (Credit Grade: {credit_grade})

We believe our products align perfectly with your procurement needs. I'd love to schedule a 20-minute call to explore this further.

Would you be available this week or next?

Best regards,
[Your Name]
{sender_company}
Korea"""

    return EmailMessage(
        to_address=contact_email,
        subject=subject,
        body_text=body,
        tags=[buyer_company, credit_grade],
    )
