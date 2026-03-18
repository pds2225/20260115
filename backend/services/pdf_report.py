"""PDF 리포트 생성 — Top 10 buyer list + 강이드
ReportLab 기반 A4 PDF 출력
"""
import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from backend.models.schemas import PipelineResult, VerificationStatus, SignalColor

# 색상 팔레트 (VALUE-UP AI 브랜드)
DARK_NAVY = colors.HexColor("#0D2137")
TEAL = colors.HexColor("#00B4D8")
LIGHT_TEAL = colors.HexColor("#90E0EF")
ORANGE = colors.HexColor("#FF8C00")
GREEN = colors.HexColor("#28A745")
YELLOW = colors.HexColor("#FFC107")
RED_COLOR = colors.HexColor("#DC3545")
LIGHT_GRAY = colors.HexColor("#F8F9FA")
MID_GRAY = colors.HexColor("#6C757D")


def _signal_color(signal: SignalColor) -> colors.Color:
    return {
        SignalColor.GREEN: GREEN,
        SignalColor.YELLOW: YELLOW,
        SignalColor.RED: RED_COLOR,
    }.get(signal, MID_GRAY)


def _status_color(status: VerificationStatus) -> colors.Color:
    return {
        VerificationStatus.PASS: GREEN,
        VerificationStatus.WARNING: YELLOW,
        VerificationStatus.FAIL: RED_COLOR,
        VerificationStatus.PENDING: MID_GRAY,
    }.get(status, MID_GRAY)


def _status_label(status: VerificationStatus) -> str:
    return {
        VerificationStatus.PASS: "✅ PASS",
        VerificationStatus.WARNING: "⚠️ WARNING",
        VerificationStatus.FAIL: "🚫 FAIL",
        VerificationStatus.PENDING: "⏳ PENDING",
    }.get(status, "N/A")


def generate_pdf_report(result: PipelineResult) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── 스타일 정의 ──────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title", parent=styles["Normal"],
        fontSize=20, textColor=DARK_NAVY, fontName="Helvetica-Bold",
        spaceAfter=4, alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=10, textColor=MID_GRAY, fontName="Helvetica",
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Normal"],
        fontSize=13, textColor=DARK_NAVY, fontName="Helvetica-Bold",
        spaceBefore=12, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica",
        spaceAfter=2, leading=14,
    )
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, textColor=MID_GRAY, fontName="Helvetica",
    )

    # ── 헤더 ──────────────────────────────────────────────────────
    story.append(Paragraph("VALUE-UP AI", title_style))
    story.append(Paragraph("데이터 기반 바이어 검증 및 자동화 워크플로우 리포트", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=8))

    # 메타 정보 테이블
    meta_data = [
        ["파이프라인 ID", result.pipeline_id, "실행일시", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["HS 코드", result.hs_code, "대상 국가", result.target_country],
        ["실행 시간", f"{result.execution_time_seconds}초", "준비도", f"{result.readiness_checklist.completion_pct}%"],
    ]
    meta_table = Table(meta_data, colWidths=[3 * cm, 5 * cm, 3 * cm, 5 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK_NAVY),
        ("TEXTCOLOR", (2, 0), (2, -1), DARK_NAVY),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GRAY),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_GRAY),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # ── 신호등 섹션 ────────────────────────────────────────────────
    sig_color = _signal_color(result.signal_color)
    signal_style = ParagraphStyle(
        "Signal", parent=styles["Normal"],
        fontSize=14, textColor=sig_color, fontName="Helvetica-Bold",
        spaceBefore=4, spaceAfter=4,
    )
    story.append(Paragraph(f"진입 가능성 신호: {result.signal_color.value}", signal_style))
    story.append(Paragraph(result.signal_message, body_style))

    # KPI 요약 테이블
    kpi_data = [
        ["수입자 발견", "활성 바이어", "검증 통과", "연락처 확보", "이메일 생성"],
        [
            str(result.step1_hs_analysis.total_importers_found if result.step1_hs_analysis else 0),
            str(result.step2_filter_result.active_buyers_count if result.step2_filter_result else 0),
            str(result.total_verified_buyers),
            str(result.total_contacts_found),
            str(result.total_emails_generated),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[3.2 * cm] * 5)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_TEAL),
        ("TEXTCOLOR", (0, 1), (-1, 1), DARK_NAVY),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    story.append(Spacer(1, 6))
    story.append(kpi_table)

    # ── 준비도 체크리스트 ──────────────────────────────────────────
    story.append(Paragraph("준비도 체크리스트", section_style))
    checklist = result.readiness_checklist
    check_items = [
        ("HS코드 유효성", checklist.hs_code_valid),
        ("타겟 시장 확인", checklist.target_market_identified),
        ("활성 바이어 발견", checklist.active_buyers_found),
        ("바이어 검증 완료", checklist.buyers_verified),
        ("연락처 확보", checklist.contacts_enriched),
        ("이메일 준비 완료", checklist.emails_ready),
    ]
    check_data = [["항목", "상태"]] + [
        [item, "✅ 완료" if ok else "❌ 미완료"]
        for item, ok in check_items
    ]
    check_table = Table(check_data, colWidths=[10 * cm, 6 * cm])
    check_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(check_table)

    # ── Top 바이어 리스트 ─────────────────────────────────────────
    story.append(Paragraph(f"Top {min(10, result.total_verified_buyers)} 검증 바이어 리스트", section_style))

    if result.step3_verified_buyers:
        buyer_header = ["#", "기업명", "국가", "수입횟수", "거래액(USD)", "검증 상태", "리스크"]
        buyer_rows = [buyer_header]
        for i, v in enumerate(result.step3_verified_buyers[:10], 1):
            # 활성 바이어 정보 매칭
            ab = None
            if result.step2_filter_result:
                for b in result.step2_filter_result.active_buyers:
                    if b.company_name == v.company_name:
                        ab = b
                        break
            buyer_rows.append([
                str(i),
                v.company_name[:30],
                v.country,
                str(ab.shipment_count) if ab else "-",
                f"${ab.total_trade_value_usd:,.0f}" if ab else "-",
                _status_label(v.overall_status),
                f"{v.risk_score:.0f}점",
            ])

        buyer_table = Table(
            buyer_rows,
            colWidths=[0.7 * cm, 5.5 * cm, 1.2 * cm, 1.8 * cm, 2.8 * cm, 2.5 * cm, 1.5 * cm],
        )
        buyer_ts = [
            ("BACKGROUND", (0, 0), (-1, 0), DARK_NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (1, 1), (1, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        # 검증 상태별 색상
        for i, v in enumerate(result.step3_verified_buyers[:10], 1):
            sc = _status_color(v.overall_status)
            buyer_ts.append(("TEXTCOLOR", (5, i), (5, i), sc))
            buyer_ts.append(("FONTNAME", (5, i), (5, i), "Helvetica-Bold"))

        buyer_table.setStyle(TableStyle(buyer_ts))
        story.append(buyer_table)

    # ── 연락처 + 이메일 섹션 ──────────────────────────────────────
    story.append(Paragraph("의사결정권자 연락처 및 이메일 초안", section_style))

    for i, (contact_r, email_r) in enumerate(
        zip(result.step4_contacts[:5], result.step5_emails[:5]), 1
    ):
        best = contact_r.best_contact
        if not best:
            continue

        block = KeepTogether([
            Paragraph(
                f"<b>{i}. {contact_r.company_name}</b>",
                ParagraphStyle("CName", parent=body_style, fontSize=10, textColor=DARK_NAVY),
            ),
            Paragraph(
                f"담당자: {best.name or 'N/A'} ({best.title or 'N/A'}) | "
                f"📧 {best.email or 'N/A'} | "
                f"신뢰도 {(best.email_confidence or 0)*100:.0f}%",
                body_style,
            ),
            Spacer(1, 3),
            Paragraph(f"<b>이메일 제목:</b> {email_r.generated_email.subject}", body_style),
            Paragraph(
                "<b>개인화 포인트:</b> " +
                " | ".join(email_r.generated_email.personalization_points[:3]),
                small_style,
            ),
            Spacer(1, 6),
        ])
        story.append(block)

    # ── 푸터 ──────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_TEAL))
    story.append(Paragraph(
        f"Generated by VALUE-UP AI Pipeline v1.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"전 과정 {result.execution_time_seconds}초 완료",
        small_style,
    ))

    doc.build(story)
    return buffer.getvalue()
