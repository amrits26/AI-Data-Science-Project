"""
Paperwork Finisher - Professional PDF generation for dealership documents.

Uses reportlab to generate:
- Completed credit applications
- Deal jackets
- Service tickets
- Warranty summaries
- Finance agreements (templates)
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


OUTPUT_DIR = Path(os.getenv("DATA_DIR", "./data")) / "paperwork"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_credit_application_pdf(applicant_data: Dict[str, Any]) -> str:
    """
    Generate a completed credit application PDF.

    Args:
        applicant_data: Dict with "first_name", "last_name", "ssn", "address", "phone", "email", etc.

    Returns:
        Path to generated PDF
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"credit_application_{timestamp}.pdf"

    # Create PDF
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#003399"), spaceAfter=20)

    elements = []

    # Header
    elements.append(Paragraph("CREDIT APPLICATION", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Applicant info table
    applicant_data_items = [
        ["First Name", applicant_data.get("first_name", "")],
        ["Last Name", applicant_data.get("last_name", "")],
        ["SSN", applicant_data.get("ssn", "")],
        ["Date of Birth", applicant_data.get("birth_date", "")],
        ["Address", applicant_data.get("address", "")],
        ["Phone", applicant_data.get("home_phone", "")],
        ["Email", applicant_data.get("email", "")],
    ]

    t = Table(applicant_data_items, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E0E0E0")),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 0.3*inch))

    # Signature section
    elements.append(Paragraph("<b>Applicant Signature:</b> ___________________________     Date: __________", styles["Normal"]))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%m/%d/%Y %I:%M %p')}", styles["Normal"]))

    # Build PDF
    doc.build(elements)
    return str(output_path)


def generate_deal_jacket_pdf(deal_data: Dict[str, Any]) -> str:
    """
    Generate a deal jacket (sales summary sheet).

    Args:
        deal_data: Dict with "customer_name", "vehicle", "price", "trade_in", "commission", etc.

    Returns:
        Path to generated PDF
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"deal_jacket_{timestamp}.pdf"

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#003399"))

    elements = []

    # Header
    elements.append(Paragraph("IMPERIAL CARS - DEAL JACKET", title_style))
    elements.append(Spacer(1, 0.1*inch))

    # Deal info
    deal_info = [
        ["Deal Number", deal_data.get("deal_number", "")],
        ["Date", deal_data.get("sale_date", datetime.now().strftime("%m/%d/%Y"))],
        ["Customer", deal_data.get("customer_name", "")],
        ["Sales Person", deal_data.get("sales_person", "")],
    ]

    t1 = Table(deal_info, colWidths=[2*inch, 4*inch])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E0E0E0")),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 0.2*inch))

    # Vehicle info
    elements.append(Paragraph("<b>Vehicle Information</b>", styles["Heading2"]))
    vehicle_info = [
        ["Year/Make/Model", deal_data.get("vehicle", "")],
        ["VIN", deal_data.get("vin", "")],
        ["Stock Number", deal_data.get("stock_number", "")],
        ["Color", deal_data.get("color", "")],
    ]

    t2 = Table(vehicle_info, colWidths=[2*inch, 4*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E0E0E0")),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 0.2*inch))

    # Pricing info
    elements.append(Paragraph("<b>Pricing & Finance</b>", styles["Heading2"]))
    pricing_info = [
        ["Sale Price", f"${deal_data.get('sale_price', 0):,.2f}"],
        ["Trade-In Allowance", f"${deal_data.get('trade_in_allowance', 0):,.2f}"],
        ["Down Payment", f"${deal_data.get('down_payment', 0):,.2f}"],
        ["Amount Financed", f"${deal_data.get('amount_financed', 0):,.2f}"],
        ["Commission", f"${deal_data.get('commission', 0):,.2f}"],
    ]

    t3 = Table(pricing_info, colWidths=[2*inch, 4*inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E0E0E0")),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t3)

    # Build PDF
    doc.build(elements)
    return str(output_path)


def generate_service_ticket_pdf(service_data: Dict[str, Any]) -> str:
    """
    Generate a service ticket/work order.

    Args:
        service_data: Dict with "ticket_number", "customer", "vehicle", "service_type", "notes", etc.

    Returns:
        Path to generated PDF
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"service_ticket_{timestamp}.pdf"

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#003399"))

    elements = []

    # Header
    elements.append(Paragraph("IMPERIAL CARS - SERVICE TICKET", title_style))
    elements.append(Spacer(1, 0.1*inch))

    # Service info
    service_info = [
        ["Ticket #", service_data.get("ticket_number", "")],
        ["Date", service_data.get("date", datetime.now().strftime("%m/%d/%Y"))],
        ["Customer", service_data.get("customer", "")],
        ["Phone", service_data.get("phone", "")],
    ]

    t1 = Table(service_info, colWidths=[1.5*inch, 4.5*inch])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E0E0E0")),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 0.15*inch))

    # Vehicle info
    elements.append(Paragraph("<b>Vehicle</b>", styles["Heading3"]))
    vehicle_info = [
        ["Year/Make/Model", service_data.get("vehicle", "")],
        ["VIN", service_data.get("vin", "")],
        ["Mileage", service_data.get("mileage", "")],
    ]

    t2 = Table(vehicle_info, colWidths=[1.5*inch, 4.5*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F0F0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 0.15*inch))

    # Service description
    elements.append(Paragraph("<b>Service Description</b>", styles["Heading3"]))
    notes = service_data.get("service_description", "")
    elements.append(Paragraph(notes, styles["Normal"]))
    elements.append(Spacer(1, 0.15*inch))

    # Authorization
    elements.append(Paragraph("<b>Customer Authorization:</b> ___________________________", styles["Normal"]))
    elements.append(Spacer(1, 0.05*inch))
    elements.append(Paragraph(f"Date: _________     Technician: __________________________", styles["Normal"]))

    # Build PDF
    doc.build(elements)
    return str(output_path)


def save_document_json(doc_type: str, document_data: Dict[str, Any]) -> str:
    """
    Save structured document data as JSON for archival.

    Args:
        doc_type: "credit_application", "deal_jacket", "service_ticket", etc.
        document_data: Structured data dict

    Returns:
        Path to saved JSON file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"{doc_type}_{timestamp}.json"

    data_with_metadata = {
        "document_type": doc_type,
        "created_at": datetime.now().isoformat(),
        "data": document_data,
    }

    with open(output_path, "w") as f:
        json.dump(data_with_metadata, f, indent=2, default=str)

    return str(output_path)
