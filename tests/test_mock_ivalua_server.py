"""
Tests for Mock Ivalua Server (`src/mock_ivalua_server.py`).
"""

import pytest
from fastapi.testclient import TestClient
from src.mock_ivalua_server import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_create_requisition_success():
    payload = {
        "project_id": "PRJ-99901",
        "tpm_name": "Sarah Connor",
        "vendor_name": "Cyberdyne Systems",
        "currency": "USD",
        "line_items": [
            {
                "item_number": 1,
                "description": "Neural Processor",
                "quantity": 1.0,
                "unit_price": 50000.0,
                "total_price": 50000.0
            }
        ],
        "grand_total": 50000.0
    }

    headers = {"Authorization": "Bearer valid-test-token"}
    response = client.post("/api/v1/purchase-requisitions", json=payload, headers=headers)

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["status"] == "SUCCESS"
    assert "requisition_id" in res_data

    req_id = res_data["requisition_id"]
    get_res = client.get(f"/api/v1/purchase-requisitions/{req_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["project_id"] == "PRJ-99901"


def test_create_requisition_unauthorized():
    payload = {
        "project_id": "PRJ-101",
        "tpm_name": "John Doe",
        "vendor_name": "Test Vendor",
        "currency": "USD",
        "line_items": [],
        "grand_total": 100.0
    }
    response = client.post("/api/v1/purchase-requisitions", json=payload)
    assert response.status_code in (401, 403)
