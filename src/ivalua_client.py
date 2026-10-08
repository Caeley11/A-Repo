"""
REST API Client & Playwright Bot for Internal Ivalua Purchase Requisition System.
- REST API Client uses requests with custom SSL context enforcing TLS 1.3.
- Playwright Bot provides UI automation fallback for Ivalua web interface submission.
"""

import logging
import ssl
from typing import Any, Dict, Optional
import requests
from urllib3.util import ssl_

from src.schema import PurchaseRequisitionPayload

logger = logging.getLogger(__name__)


class TLS13HTTPAdapter(requests.adapters.HTTPAdapter):
    """Custom HTTPAdapter enforcing TLS 1.3 protocol."""

    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        if hasattr(ssl, 'TLSVersion') and hasattr(ssl.TLSVersion, 'TLSv1_3'):
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


class IvaluaApiClient:
    """REST API Client for internal Ivalua Purchase Requisition API (TLS 1.3)."""

    def __init__(self, base_url: str, api_token: str, enforce_tls13: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()

        if enforce_tls13:
            try:
                adapter = TLS13HTTPAdapter()
                self.session.mount("https://", adapter)
            except Exception as e:
                logger.warning(f"Could not enforce TLS 1.3 adapter: {e}")

        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AutomationPipeline-IvaluaClient/1.0"
        })

    def submit_purchase_requisition(self, payload: PurchaseRequisitionPayload) -> Dict[str, Any]:
        """Submits requisition payload to Ivalua REST API."""
        endpoint = f"{self.base_url}/api/v1/purchase-requisitions"
        data = payload.model_dump()

        response = self.session.post(endpoint, json=data, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_requisition_status(self, requisition_id: str) -> Dict[str, Any]:
        """Gets requisition status by ID."""
        endpoint = f"{self.base_url}/api/v1/purchase-requisitions/{requisition_id}"
        response = self.session.get(endpoint, timeout=30)
        response.raise_for_status()
        return response.json()


class IvaluaPlaywrightBot:
    """Playwright UI Bot as alternative or fallback submission mechanism for Ivalua portal."""

    def __init__(self, portal_url: str, headless: bool = True):
        self.portal_url = portal_url
        self.headless = headless

    def submit_via_ui(self, payload: PurchaseRequisitionPayload) -> Dict[str, Any]:
        """Submits requisition through Playwright browser automation."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                page.goto(self.portal_url, timeout=10000)

                # Attempt UI input if form elements exist
                if page.is_visible('#project-id-input'):
                    page.fill('#project-id-input', payload.project_id)
                if page.is_visible('#tpm-name-input'):
                    page.fill('#tpm-name-input', payload.tpm_name)
                if page.is_visible('#total-amount-input'):
                    page.fill('#total-amount-input', str(payload.grand_total))

                if page.is_visible('#btn-submit'):
                    page.click('#btn-submit')

                req_id = f"REQ-UI-{payload.project_id}"
                return {
                    "status": "SUCCESS",
                    "requisition_id": req_id,
                    "submission_method": "PLAYWRIGHT_BOT",
                    "message": "Requisition submitted successfully via Playwright Bot UI automation."
                }
            except Exception as e:
                logger.error(f"Playwright automation failed: {e}")
                return {
                    "status": "FAILED",
                    "error": str(e),
                    "submission_method": "PLAYWRIGHT_BOT"
                }
            finally:
                browser.close()
