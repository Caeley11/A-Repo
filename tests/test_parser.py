"""
Tests for Local Parsing Engine (`src/parser.py`).
"""

import io
import pytest
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table

from src.parser import EmailParser, PDFQuotationParser, parse_email_and_quotation


def create_dummy_quotation_pdf_bytes() -> bytes:
    """Helper to generate a dummy PDF quotation with a table and grand total."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, "Vendor: Hardware Solutions Ltd")
    p.drawString(100, 730, "Quotation Total: $1,250.00")
    p.drawString(100, 710, "Widgets 10 100.00 1000.00")
    p.drawString(100, 690, "Gadgets 5 50.00 250.00")
    p.save()
    return buffer.getvalue()


def test_email_parser_regex():
    email_text = """
    Hi Team,
    Please process the attached quotation.
    Project ID: PRJ-88412
    TPM Name: Sarah Jenkins
    Thanks!
    """
    subject = "Requisition Request - PROJ-88412"

    project_id = EmailParser.extract_project_id(email_text, subject)
    tpm_name = EmailParser.extract_tpm_name(email_text, subject)

    assert project_id == "PRJ-88412"
    assert tpm_name == "Sarah Jenkins"


def test_pdf_quotation_parser():
    pdf_bytes = create_dummy_quotation_pdf_bytes()
    res = PDFQuotationParser.parse_pdf(pdf_bytes)

    assert res["grand_total"] == 1250.00
    assert res["currency"] == "USD"
    assert res["vendor_name"] == "Hardware Solutions Ltd"


def test_parse_email_and_quotation():
    pdf_bytes = create_dummy_quotation_pdf_bytes()
    body = "Project ID: PRJ-555\nTPM: Alex Smith"
    payload = parse_email_and_quotation(
        email_body=body,
        email_subject="New Purchase Request",
        sender="alex@example.com",
        pdf_bytes=pdf_bytes
    )

    assert payload.project_id == "PRJ-555"
    assert payload.tpm_name == "Alex Smith"
    assert payload.grand_total == 1250.00
    assert payload.vendor_name == "Hardware Solutions Ltd"
