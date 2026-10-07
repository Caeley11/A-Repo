"""
Local Parsing Engine (In-Memory).
Extracts Project ID, TPM Name, Quotation Grand Total, Vendor Name, Currency, and Line Items
from raw email text/subject and PDF quotation attachments using Regex and pdfplumber.
"""

import io
import re
from typing import Any, Dict, List, Optional, Tuple
import pdfplumber

from src.schema import LineItem, PurchaseRequisitionPayload, sanitize_string


class EmailParser:
    """Extracts metadata such as Project ID and TPM Name from email text or subject."""

    PROJECT_ID_PATTERNS = [
        r"(?:Project\s*(?:ID|Code|#|Num)?\s*[:=\-]\s*)([A-Z0-9\-_]+)",
        r"\b(PRJ-[A-Z0-9]+)\b",
        r"\b(PROJ-[A-Z0-9]+)\b",
        r"\b(PR-[0-9]{4,8})\b",
    ]

    TPM_NAME_PATTERNS = [
        r"(?:TPM\s*(?:Name)?|Technical Program Manager)\s*[:=\-]\s*([A-Za-z\s\.\'-]+?)(?=\r|\n|;|,|\t|$)",
        r"(?:Program Manager)\s*[:=\-]\s*([A-Za-z\s\.\'-]+?)(?=\r|\n|;|,|\t|$)",
        r"(?:Requested\s*by)\s*[:=\-]\s*([A-Za-z\s\.\'-]+?)(?=\r|\n|;|,|\t|$)",
    ]

    @classmethod
    def extract_project_id(cls, text: str, subject: str = "") -> Optional[str]:
        combined = f"{subject}\n{text}"
        for pattern in cls.PROJECT_ID_PATTERNS:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return sanitize_string(match.group(1))
        return None

    @classmethod
    def extract_tpm_name(cls, text: str, subject: str = "") -> Optional[str]:
        combined = f"{subject}\n{text}"
        for pattern in cls.TPM_NAME_PATTERNS:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                res = sanitize_string(match.group(1))
                if len(res) > 2:
                    return res
        return None


class PDFQuotationParser:
    """Parses PDF quotation attachments using pdfplumber to extract amounts and line items."""

    GRAND_TOTAL_PATTERNS = [
        r"(?:Grand\s*Total|Total\s*Amount|Quotation\s*Total|Total\s*Due|Amount\s*Due|Total)\s*[:=\$-]?\s*([A-Z]{3})?\s*[\$€£]?\s*([\d,]+\.?\d*)",
        r"[\$€£]\s*([\d,]+\.\d{2})",
    ]

    VENDOR_PATTERNS = [
        r"(?:Vendor|Supplier|From|Company)\s*[:=\-]\s*([A-Za-z0-9\s,\.&'-]+?)(?=\r|\n|$)",
        r"(?:Quotation\s*From)\s*[:=\-]\s*([A-Za-z0-9\s,\.&'-]+?)(?=\r|\n|$)",
    ]

    CURRENCY_PATTERNS = [
        r"\b(USD|EUR|GBP|CAD|AUD|JPY|SGD|INR)\b",
        r"(\$)",
        r"(€)",
        r"(£)",
    ]

    @classmethod
    def parse_pdf(cls, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Parses raw bytes of a PDF file.
        Returns a dict containing grand_total, line_items, vendor_name, currency, raw_text.
        """
        raw_text_pages: List[str] = []
        tables: List[List[List[Optional[str]]]] = []

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    raw_text_pages.append(txt)
                extracted_tables = page.extract_tables()
                if extracted_tables:
                    tables.extend(extracted_tables)

        full_text = "\n".join(raw_text_pages)

        grand_total, currency = cls._extract_grand_total_and_currency(full_text)
        vendor_name = cls._extract_vendor(full_text)
        line_items = cls._extract_line_items(tables, full_text)

        # If grand total not found from regex, sum up line items
        if grand_total == 0.0 and line_items:
            grand_total = round(sum(item.total_price for item in line_items), 2)

        return {
            "grand_total": grand_total,
            "currency": currency,
            "vendor_name": vendor_name,
            "line_items": line_items,
            "raw_text": full_text
        }

    @classmethod
    def _extract_grand_total_and_currency(cls, text: str) -> Tuple[float, str]:
        currency = "USD"
        grand_total = 0.0

        # Currency check
        for pattern in cls.CURRENCY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                symbol_or_code = match.group(1)
                if symbol_or_code == "$":
                    currency = "USD"
                elif symbol_or_code == "€":
                    currency = "EUR"
                elif symbol_or_code == "£":
                    currency = "GBP"
                elif len(symbol_or_code) == 3:
                    currency = symbol_or_code.upper()
                break

        # Grand total check
        for pattern in cls.GRAND_TOTAL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Get last match which is usually the final total
                last_match = matches[-1]
                val_str = last_match[1] if isinstance(last_match, tuple) else last_match
                if not val_str and isinstance(last_match, tuple) and len(last_match) > 0:
                    val_str = last_match[0]
                val_str = val_str.replace(',', '')
                try:
                    val = float(val_str)
                    if val > grand_total:
                        grand_total = val
                except ValueError:
                    continue

        return grand_total, currency

    @classmethod
    def _extract_vendor(cls, text: str) -> str:
        for pattern in cls.VENDOR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                v = sanitize_string(match.group(1))
                if len(v) > 2:
                    return v
        return "Acme Solutions Ltd"

    @classmethod
    def _extract_line_items(cls, tables: List[List[List[Optional[str]]]], text: str) -> List[LineItem]:
        items: List[LineItem] = []
        item_counter = 1

        # First attempt: structured tables from pdfplumber
        for table in tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                # Clean row strings
                row_str = [sanitize_string(cell) for cell in row if cell is not None]

                # Look for row containing numbers representing quantity, unit price, total price
                nums = []
                desc_parts = []
                for cell in row_str:
                    clean_cell = cell.replace('$', '').replace('€', '').replace('£', '').replace(',', '')
                    try:
                        num = float(clean_cell)
                        nums.append(num)
                    except ValueError:
                        if cell and not cell.lower().startswith(('item', 'desc', 'qty', 'unit', 'total', 'price', 'sl')):
                            desc_parts.append(cell)

                if len(nums) >= 2 and desc_parts:
                    # Usually: qty, unit_price, total_price OR unit_price, qty, total_price
                    desc = " ".join(desc_parts)
                    if len(nums) >= 3:
                        qty = nums[0]
                        unit_price = nums[1]
                        total_price = nums[2]
                    else:
                        qty = nums[0]
                        unit_price = nums[1]
                        total_price = round(qty * unit_price, 2)

                    if qty > 0 and unit_price >= 0:
                        items.append(LineItem(
                            item_number=item_counter,
                            description=desc,
                            quantity=qty,
                            unit_price=unit_price,
                            total_price=total_price
                        ))
                        item_counter += 1

        # Fallback text parsing if no items extracted from tables
        if not items:
            # Match lines with format: ItemDescription Qty Price Total
            line_pattern = r'([A-Za-z0-9\s\-_]+?)\s+(\d+(?:\.\d+)?)\s+[\$€£]?([\d,]+\.\d{2})\s+[\$€£]?([\d,]+\.\d{2})'
            for match in re.finditer(line_pattern, text):
                desc, qty_s, unit_s, total_s = match.groups()
                desc = sanitize_string(desc)
                if desc and not desc.lower().startswith(('description', 'total', 'grand')):
                    try:
                        qty = float(qty_s)
                        unit_price = float(unit_s.replace(',', ''))
                        total_price = float(total_s.replace(',', ''))
                        items.append(LineItem(
                            item_number=item_counter,
                            description=desc,
                            quantity=qty,
                            unit_price=unit_price,
                            total_price=total_price
                        ))
                        item_counter += 1
                    except ValueError:
                        continue

        return items


def parse_email_and_quotation(
    email_body: str,
    email_subject: str = "",
    sender: str = "",
    pdf_bytes: Optional[bytes] = None
) -> PurchaseRequisitionPayload:
    """
    Combines EmailParser and PDFQuotationParser to build a validated PurchaseRequisitionPayload.
    """
    project_id = EmailParser.extract_project_id(email_body, email_subject) or "PRJ-9999"
    tpm_name = EmailParser.extract_tpm_name(email_body, email_subject) or "Unknown TPM"

    grand_total = 0.0
    currency = "USD"
    vendor_name = "Default Supplier"
    line_items: List[LineItem] = []

    if pdf_bytes:
        pdf_res = PDFQuotationParser.parse_pdf(pdf_bytes)
        grand_total = pdf_res["grand_total"]
        currency = pdf_res["currency"]
        if pdf_res["vendor_name"]:
            vendor_name = pdf_res["vendor_name"]
        line_items = pdf_res["line_items"]

    # Fallback default line item if none parsed but grand total exists
    if not line_items and grand_total > 0:
        line_items.append(LineItem(
            item_number=1,
            description="Quotation Services / Goods",
            quantity=1.0,
            unit_price=grand_total,
            total_price=grand_total
        ))

    payload = PurchaseRequisitionPayload(
        project_id=project_id,
        tpm_name=tpm_name,
        vendor_name=vendor_name,
        currency=currency,
        line_items=line_items,
        grand_total=grand_total,
        email_subject=email_subject,
        sender=sender
    )
    return payload
