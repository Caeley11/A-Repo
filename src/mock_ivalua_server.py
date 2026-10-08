"""
Mock Ivalua System Server for Purchase Requisition REST API.
Simulates internal Ivalua backend endpoint.
"""

import uuid
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Header, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

app = FastAPI(title="Mock Internal Ivalua System API", version="1.0.0")

security = HTTPBearer()

# In-memory store for requisitions
REQUISITIONS_DB: Dict[str, Dict[str, Any]] = {}


class LineItemModel(BaseModel):
    item_number: int
    description: str
    quantity: float
    unit_price: float
    total_price: float


class PurchaseRequisitionModel(BaseModel):
    project_id: str
    tpm_name: str
    vendor_name: str
    currency: str
    line_items: List[LineItemModel]
    grand_total: float
    email_subject: str | None = None
    sender: str | None = None


@app.get("/health")
def health_check():
    return {"status": "UP", "system": "Ivalua Internal System"}


@app.post("/api/v1/purchase-requisitions", status_code=status.HTTP_201_CREATED)
def create_purchase_requisition(
    payload: PurchaseRequisitionModel,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    token = credentials.credentials
    if not token or token == "invalid-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Token"
        )

    req_id = f"IV-REQ-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "requisition_id": req_id,
        "status": "APPROVED_AND_QUEUED",
        "project_id": payload.project_id,
        "tpm_name": payload.tpm_name,
        "vendor_name": payload.vendor_name,
        "currency": payload.currency,
        "grand_total": payload.grand_total,
        "line_items_count": len(payload.line_items),
        "details": payload.model_dump()
    }
    REQUISITIONS_DB[req_id] = record

    return {
        "status": "SUCCESS",
        "requisition_id": req_id,
        "message": f"Purchase requisition {req_id} created successfully in Ivalua.",
        "data": record
    }


@app.get("/api/v1/purchase-requisitions/{requisition_id}")
def get_purchase_requisition(
    requisition_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    if requisition_id not in REQUISITIONS_DB:
        raise HTTPException(status_code=404, detail="Requisition not found")
    return REQUISITIONS_DB[requisition_id]
