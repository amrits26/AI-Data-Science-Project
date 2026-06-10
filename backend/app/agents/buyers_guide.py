"""Buyer's Guide PDF generator for Imperial Cars."""
from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

IMPERIAL_RED = colors.HexColor("#B22234")
IMPERIAL_BLACK = colors.HexColor("#1A1A1A")
ROW_ALT = colors.HexColor("#F5F5F5")
GRID_GRAY = colors.HexColor("#DDDDDD")

FINANCING_FAQS: list[tuple[str, str]] = [
    (
        "What credit score do I need?",
        "Most financing options are available with a score of 620+. We work with 15+ lenders to find the best rate for your situation.",
    ),
    (
        "How much down payment is required?",
        "We recommend 10–20% down, but $0-down options are available with approved credit.",
    ),
    (
        "What is the difference between leasing and buying?",
        "Leasing has lower monthly payments but you return the vehicle at term end. Buying builds equity and you own the vehicle outright.",
    ),
    (
        "Can I trade in my current vehicle?",
        "Yes — we accept all trade-ins and apply your equity directly toward your new purchase.",
    ),
    (
        "How long does financing approval take?",
        "Most approvals are instant or within one business day.",
    ),
]

FINANCING_OVERVIEW: list[list[str]] = [
    ["Loan Term", "Typical APR Range", "Best For"],
    ["24 months", "4.9% – 7.9%", "Minimize interest, fast equity"],
    ["36 months", "5.4% – 8.4%", "Balance payment vs. interest"],
    ["48 months", "5.9% – 9.0%", "Moderate monthly payment"],
    ["60 months", "6.4% – 9.9%", "Most popular option"],
    ["72 months", "7.0% – 11.0%", "Lowest payment, higher interest"],
]


def _header_table_style(bg: Any) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
            ("GRID", (0, 0), (-1, -1), 0.5, GRID_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def generate_buyers_guide_pdf(cars: list) -> bytes:
    """Build a Buyer's Guide PDF from a list of Car ORM objects (or mock objects).

    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Imperial Cars Buyer's Guide",
        author="Imperial Cars AI",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ImperialTitle",
        parent=styles["Title"],
        textColor=IMPERIAL_RED,
        fontSize=26,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "ImperialSubtitle",
        parent=styles["Normal"],
        textColor=IMPERIAL_BLACK,
        fontSize=11,
        spaceAfter=16,
    )
    heading2 = ParagraphStyle(
        "Heading2",
        parent=styles["Heading2"],
        textColor=IMPERIAL_BLACK,
        fontSize=14,
        spaceBefore=18,
        spaceAfter=8,
    )
    body = styles["BodyText"]
    footer_style = ParagraphStyle(
        "Footer",
        parent=body,
        textColor=colors.grey,
        fontSize=8,
        alignment=TA_CENTER,
    )

    story = []

    # ── Title ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("Imperial Cars — Buyer's Guide", title_style))
    story.append(Paragraph("Your comprehensive guide to finding the perfect vehicle.", subtitle_style))
    story.append(Spacer(1, 0.2 * inch))

    # ── Inventory Highlights ───────────────────────────────────────────────────
    story.append(Paragraph("Current Inventory Highlights", heading2))
    if cars:
        rows: list[list[str]] = [["Year", "Make", "Model", "Trim", "MSRP", "MPG Hwy", "Safety"]]
        for c in cars[:20]:
            rows.append(
                [
                    str(c.year or ""),
                    str(c.make or ""),
                    str(c.model or ""),
                    str(c.trim or ""),
                    f"${c.msrp:,.0f}" if c.msrp else "—",
                    str(c.mpg_highway or "—"),
                    str(c.safety_rating or "—"),
                ]
            )
        tbl = Table(rows, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(_header_table_style(IMPERIAL_RED))
        story.append(tbl)
    else:
        story.append(Paragraph("Contact us for our full current inventory.", body))

    story.append(Spacer(1, 0.2 * inch))

    # ── Financing FAQ ──────────────────────────────────────────────────────────
    story.append(Paragraph("Financing FAQ", heading2))
    for question, answer in FINANCING_FAQS:
        story.append(Paragraph(f"<b>Q: {question}</b>", body))
        story.append(Paragraph(f"A: {answer}", body))
        story.append(Spacer(1, 0.08 * inch))

    # ── Financing Overview ─────────────────────────────────────────────────────
    story.append(Paragraph("Financing Overview", heading2))
    ovt = Table(FINANCING_OVERVIEW, repeatRows=1, hAlign="LEFT")
    ovt.setStyle(_header_table_style(IMPERIAL_BLACK))
    story.append(ovt)

    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            "© Imperial Cars — Mendon, MA | imperialcars.com | All pricing subject to change.",
            footer_style,
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
