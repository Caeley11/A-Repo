"""
Tests for Core Data Schema & Input Sanitization (`src/schema.py`).
"""

import pytest
from pydantic import ValidationError
from src.schema import LineItem, PurchaseRequisitionPayload, sanitize_string


def test_sanitize_string():
    assert sanitize_string("  Hello World  ") == "Hello World"
    assert sanitize_string("<b>Bold Text</b>") == "Bold Text"
    assert sanitize_string("Line 1\x00\x07Text") == "Line 1Text"
    assert sanitize_string("&lt;div&gt;Escaped&lt;/div&gt;") == "Escaped"
    assert sanitize_string(None) == ""


def test_line_item_validation():
    item = LineItem(
        item_number=1,
        description="<b>Cloud Server Subscription</b>",
        quantity=2.0,
        unit_price=150.0,
        total_price=300.0
    )
    assert item.description == "Cloud Server Subscription"
    assert item.quantity == 2.0
    assert item.unit_price == 150.0
    assert item.total_price == 300.0


def test_purchase_requisition_payload_validation():
    payload = PurchaseRequisitionPayload(
        project_id="prj-991",
        tpm_name="  Jane Doe  ",
        vendor_name="<i>Acme Corp</i>",
        currency="usd",
        grand_total=300.0,
        line_items=[
            LineItem(
                item_number=1,
                description="Server",
                quantity=2.0,
                unit_price=150.0,
                total_price=300.0
            )
        ]
    )

    assert payload.project_id == "PRJ-991"
    assert payload.tpm_name == "Jane Doe"
    assert payload.vendor_name == "Acme Corp"
    assert payload.currency == "USD"
    assert payload.grand_total == 300.0


def test_invalid_project_id():
    with pytest.raises(ValidationError):
        PurchaseRequisitionPayload(
            project_id="",
            tpm_name="John",
            grand_total=100.0
        )
