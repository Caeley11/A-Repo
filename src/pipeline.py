"""
Main Python Automation Pipeline Orchestrator.
Orchestrates:
1. MAPI Ingestion Layer (fetching unread emails, generating snapshot PDF logs).
2. Local Parsing Engine (In-Memory regex & pdfplumber extraction).
3. Data Mapping & Schema Validation (Pydantic payload validation and sanitization).
4. Secure Keyring Handler (Retrieving API secrets from Credential Manager/Keyring).
5. REST API Client / Playwright Bot submission to Internal Ivalua System.
"""

import os
import logging
from typing import Any, Dict, List, Optional

from src.schema import PurchaseRequisitionPayload
from src.parser import parse_email_and_quotation
from src.ingestion import IngestedEmail, EmailSnapshotRenderer, MAPIClientInterface
from src.keyring_handler import KeyringHandler
from src.ivalua_client import IvaluaApiClient, IvaluaPlaywrightBot

logger = logging.getLogger(__name__)


class AutomationPipeline:
    """End-to-End Purchase Requisition Automation Pipeline Orchestrator."""

    def __init__(
        self,
        ivalua_base_url: str = "http://127.0.0.1:8000",
        snapshot_dir: str = "/tmp/email_snapshots",
        use_playwright_fallback: bool = True
    ):
        self.ivalua_base_url = ivalua_base_url
        self.snapshot_dir = snapshot_dir
        self.use_playwright_fallback = use_playwright_fallback
        self.keyring_handler = KeyringHandler()

        os.makedirs(self.snapshot_dir, exist_ok=True)

    def process_single_email(self, email: IngestedEmail) -> Dict[str, Any]:
        """
        Processes a single ingested email end-to-end:
        1. Generates PDF audit snapshot.
        2. Extracts Project ID, TPM Name, Vendor, Currency, and Line Items.
        3. Validates and sanitizes payload against schema.
        4. Retrieves secure API secrets.
        5. Submits payload to Ivalua via REST API (or Playwright Bot fallback).
        """
        result: Dict[str, Any] = {
            "email_id": email.email_id,
            "subject": email.subject,
            "status": "PROCESSING",
            "snapshot_pdf": None,
            "payload": None,
            "ivalua_response": None
        }

        # Step 1: Render email snapshot PDF for audit
        try:
            snapshot_path = os.path.join(self.snapshot_dir, f"snapshot_{email.email_id[:12]}.pdf")
            EmailSnapshotRenderer.render_email_to_pdf(email, snapshot_path)
            result["snapshot_pdf"] = snapshot_path
        except Exception as e:
            logger.error(f"Failed to render email snapshot PDF: {e}")

        # Step 2 & 3: Parse email and PDF attachment into validated schema payload
        pdf_bytes: Optional[bytes] = None
        for att in email.attachments:
            if att.filename.lower().endswith(".pdf"):
                pdf_bytes = att.content_bytes
                break

        payload: PurchaseRequisitionPayload = parse_email_and_quotation(
            email_body=email.body_text,
            email_subject=email.subject,
            sender=email.sender,
            pdf_bytes=pdf_bytes
        )
        result["payload"] = payload.model_dump()

        # Step 4: Secure Keyring Secret Retrieval
        api_token = self.keyring_handler.get_secret("api_token", default="default-dev-token")

        # Step 5: Submit to Ivalua via REST API Client (or Playwright Bot fallback)
        try:
            enforce_tls = self.ivalua_base_url.startswith("https://")
            client = IvaluaApiClient(base_url=self.ivalua_base_url, api_token=api_token, enforce_tls13=enforce_tls)
            ivalua_res = client.submit_purchase_requisition(payload)
            result["status"] = "SUCCESS"
            result["ivalua_response"] = ivalua_res
            result["submission_method"] = "REST_API"
        except Exception as api_err:
            logger.warning(f"REST API submission failed: {api_err}.")
            if self.use_playwright_fallback:
                logger.info("Attempting submission via Playwright UI Bot...")
                try:
                    bot = IvaluaPlaywrightBot(portal_url=self.ivalua_base_url, headless=True)
                    bot_res = bot.submit_via_ui(payload)
                    result["status"] = bot_res.get("status", "SUCCESS")
                    result["ivalua_response"] = bot_res
                    result["submission_method"] = "PLAYWRIGHT_BOT"
                except Exception as bot_err:
                    result["status"] = "FAILED"
                    result["error"] = f"Both REST API ({api_err}) and Playwright Bot ({bot_err}) failed."
            else:
                result["status"] = "FAILED"
                result["error"] = str(api_err)

        return result

    def run_batch_processing(self, mapi_client: Optional[MAPIClientInterface] = None, max_emails: int = 10) -> List[Dict[str, Any]]:
        """Runs the pipeline over unread MAPI emails."""
        if mapi_client is None:
            mapi_client = MAPIClientInterface()

        emails = mapi_client.fetch_unread_emails(max_count=max_emails)
        results = []

        for email in emails:
            res = self.process_single_email(email)
            results.append(res)

        return results
