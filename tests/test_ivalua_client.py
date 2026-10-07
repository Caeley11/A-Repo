"""
Tests for REST API Client & Playwright Bot (`src/ivalua_client.py`).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.schema import LineItem, PurchaseRequisitionPayload
from src.ivalua_client import IvaluaApiClient, IvaluaPlaywrightBot


def test_ivalua_api_client_requests(requests_mock):
    base_url = "https://ivalua.internal.corp"
    api_token = "test-token-123"

    client = IvaluaApiClient(base_url=base_url, api_token=api_token, enforce_tls13=False)

    payload = PurchaseRequisitionPayload(
        project_id="PRJ-100",
        tpm_name="Alice Vance",
        vendor_name="Global Tech",
        currency="USD",
        grand_total=1000.0,
        line_items=[
            LineItem(
                item_number=1,
                description="Consulting",
                quantity=10.0,
                unit_price=100.0,
                total_price=1000.0
            )
        ]
    )

    requests_mock.post(
        f"{base_url}/api/v1/purchase-requisitions",
        json={"status": "SUCCESS", "requisition_id": "IV-REQ-001"},
        status_code=201
    )

    res = client.submit_purchase_requisition(payload)
    assert res["status"] == "SUCCESS"
    assert res["requisition_id"] == "IV-REQ-001"


def test_playwright_bot_mock():
    bot = IvaluaPlaywrightBot(portal_url="http://127.0.0.1:8000", headless=True)

    payload = PurchaseRequisitionPayload(
        project_id="PRJ-200",
        tpm_name="Bob Miller",
        grand_total=500.0
    )

    # Mock sync_playwright to avoid needing actual browser binary or display server in container
    with patch("playwright.sync_api.sync_playwright") as mock_playwright:
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.is_visible.return_value = True

        res = bot.submit_via_ui(payload)

        assert res["status"] == "SUCCESS"
        assert res["submission_method"] == "PLAYWRIGHT_BOT"
        assert "REQ-UI-PRJ-200" in res["requisition_id"]
