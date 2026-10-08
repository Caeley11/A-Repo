"""
Tests for MAPI Ingestion Layer & Email Snapshot Renderer (`src/ingestion.py`).
"""

import os
import pytest
from datetime import datetime

from src.ingestion import EmailAttachment, EmailSnapshotRenderer, IngestedEmail, MAPIClientInterface


def test_mapi_client_interface_fallback():
    client = MAPIClientInterface()
    emails = client.fetch_unread_emails()
    assert isinstance(emails, list)


def test_email_snapshot_renderer(tmp_path):
    email = IngestedEmail(
        email_id="MSG-123456",
        subject="Request for Requisition Approval",
        sender="jdoe@example.com",
        received_time=datetime(2025, 1, 15, 10, 30, 0),
        body_text="Hi Team,\n\nPlease process PRJ-101 for TPM Michael Scott.\nQuotation total is $5,000.\n\nThanks!",
        attachments=[
            EmailAttachment(
                filename="quotation_101.pdf",
                content_type="application/pdf",
                content_bytes=b"%PDF-1.4 Mock PDF Content"
            )
        ]
    )

    output_pdf = str(tmp_path / "snapshot.pdf")
    rendered_path = EmailSnapshotRenderer.render_email_to_pdf(email, output_pdf)

    assert os.path.exists(rendered_path)
    assert os.path.getsize(rendered_path) > 0
