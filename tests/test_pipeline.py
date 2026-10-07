"""
Integration tests for End-to-End Automation Pipeline (`src/pipeline.py`).
"""

import io
from datetime import datetime
import pytest
import requests_mock
from reportlab.pdfgen import canvas

from src.ingestion import EmailAttachment, IngestedEmail
from src.pipeline import AutomationPipeline


def create_sample_quotation_pdf() -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, "Vendor: Enterprise Cloud Solutions")
    p.drawString(100, 730, "Quotation Total: $2,500.00")
    p.drawString(100, 700, "Server Cluster 2 1250.00 2500.00")
    p.save()
    return buffer.getvalue()


def test_pipeline_end_to_end_rest_api():
    pipeline = AutomationPipeline(ivalua_base_url="https://ivalua.internal.corp", snapshot_dir="/tmp/test_snapshots")

    pdf_bytes = create_sample_quotation_pdf()
    email = IngestedEmail(
        email_id="INTEG-EMAIL-001",
        subject="Requisition Request - PRJ-77112",
        sender="tpm.lead@corp.com",
        received_time=datetime.now(),
        body_text="Project ID: PRJ-77112\nTPM Name: David Kim\nPlease find attached quotation.",
        attachments=[
            EmailAttachment(
                filename="quotation_77112.pdf",
                content_type="application/pdf",
                content_bytes=pdf_bytes
            )
        ]
    )

    with requests_mock.Mocker() as m:
        m.post(
            "https://ivalua.internal.corp/api/v1/purchase-requisitions",
            json={"status": "SUCCESS", "requisition_id": "IV-REQ-77112", "message": "Approved"},
            status_code=201
        )

        res = pipeline.process_single_email(email)

        assert res["status"] == "SUCCESS"
        assert res["submission_method"] == "REST_API"
        assert res["payload"]["project_id"] == "PRJ-77112"
        assert res["payload"]["tpm_name"] == "David Kim"
        assert res["payload"]["grand_total"] == 2500.0
        assert res["payload"]["vendor_name"] == "Enterprise Cloud Solutions"
        assert res["ivalua_response"]["requisition_id"] == "IV-REQ-77112"
