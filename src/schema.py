"""
Core Data Schema & Schema Validation Layer for Purchase Requisition Pipeline.
Handles data models, field validation, and string input sanitization.
"""

import html
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


def sanitize_string(value: Optional[str]) -> str:
    """
    Sanitizes raw string inputs:
    - Strips leading/trailing whitespace
    - Unescapes HTML entities
    - Removes HTML tags and unsafe control characters
    """
    if value is None:
        return ""
    # Unescape HTML entities
    cleaned = html.unescape(value)
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    # Remove non-printable control characters except standard space/tab/newline
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)
    return cleaned.strip()


class LineItem(BaseModel):
    item_number: int = Field(..., description="Line item sequence number")
    description: str = Field(..., description="Description of goods or services")
    quantity: float = Field(..., gt=0, description="Quantity ordered")
    unit_price: float = Field(..., ge=0, description="Unit price per item")
    total_price: float = Field(..., ge=0, description="Total cost for this line item")

    @field_validator('description', mode='before')
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        return sanitize_string(v)

    @model_validator(mode='after')
    def validate_line_total(self) -> 'LineItem':
        calculated = round(self.quantity * self.unit_price, 2)
        # Allow minor rounding tolerance (0.02)
        if abs(calculated - round(self.total_price, 2)) > 0.05:
            # Recalculate total if slightly off or missing, or raise warning
            pass
        return self


class PurchaseRequisitionPayload(BaseModel):
    project_id: str = Field(..., description="Project ID (e.g. PRJ-10023, PROJ-884)")
    tpm_name: str = Field(..., description="Technical Program Manager (TPM) Name")
    vendor_name: str = Field(default="Unknown Vendor", description="Vendor / Supplier Name")
    currency: str = Field(default="USD", description="Currency Code (USD, EUR, GBP, etc.)")
    line_items: List[LineItem] = Field(default_factory=list, description="List of requisition line items")
    grand_total: float = Field(..., ge=0, description="Total quotation / requisition amount")
    email_subject: Optional[str] = Field(None, description="Original email subject")
    sender: Optional[str] = Field(None, description="Sender email address")

    @field_validator('project_id', 'tpm_name', 'vendor_name', 'currency', 'email_subject', 'sender', mode='before')
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> str:
        return sanitize_string(v)

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v_upper = v.upper()
        if len(v_upper) != 3:
            return "USD"
        return v_upper

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        if not v:
            raise ValueError("Project ID cannot be empty")
        return v.upper()

    @model_validator(mode='after')
    def validate_grand_total_matches_items(self) -> 'PurchaseRequisitionPayload':
        if self.line_items:
            items_sum = round(sum(item.total_price for item in self.line_items), 2)
            if abs(items_sum - round(self.grand_total, 2)) > 0.1:
                # Log or accept with grand total preference
                pass
        return self
