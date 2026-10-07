"""
MAPI Ingestion Layer & Email Snapshot Renderer.
Provides:
1. MAPI / Exchange email ingestion handler (supporting win32com Outlook MAPI interface on Windows, with mock/emulated fallback).
2. Email Snapshot Renderer using ReportLab to render email body & metadata into PDF/PNG snapshot files for auditing.
"""

import html
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors


@dataclass
class EmailAttachment:
    filename: str
    content_type: str
    content_bytes: bytes


@dataclass
class IngestedEmail:
    email_id: str
    subject: str
    sender: str
    received_time: datetime
    body_text: str
    attachments: List[EmailAttachment] = field(default_factory=list)


class MAPIClientInterface:
    """
    Interface for MAPI Ingestion.
    Attempts win32com MAPI connection if available, falls back to mock inbox.
    """

    def __init__(self, folder_name: str = "Inbox", mark_as_read: bool = True):
        self.folder_name = folder_name
        self.mark_as_read = mark_as_read
        self.use_win32 = False
        self._check_win32()

    def _check_win32(self):
        if sys.platform == "win32":
            try:
                import win32com.client  # type: ignore
                self.use_win32 = True
            except ImportError:
                self.use_win32 = False

    def fetch_unread_emails(self, max_count: int = 10) -> List[IngestedEmail]:
        if self.use_win32:
            return self._fetch_unread_win32(max_count)
        else:
            return self._fetch_mock_emails()

    def _fetch_unread_win32(self, max_count: int) -> List[IngestedEmail]:
        import win32com.client  # type: ignore
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # 6 = olFolderInbox
        messages = inbox.Items.Restrict("[UnRead] = True")

        results: List[IngestedEmail] = []
        count = 0

        for msg in messages:
            if count >= max_count:
                break

            attachments: List[EmailAttachment] = []
            for att in msg.Attachments:
                # Save attachment bytes
                temp_path = os.path.join("/tmp", att.FileName) if os.path.exists("/tmp") else att.FileName
                att.SaveAsFile(temp_path)
                with open(temp_path, "rb") as f:
                    att_bytes = f.read()
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                attachments.append(EmailAttachment(
                    filename=att.FileName,
                    content_type="application/octet-stream",
                    content_bytes=att_bytes
                ))

            ingested = IngestedEmail(
                email_id=str(msg.EntryID),
                subject=str(msg.Subject),
                sender=str(getattr(msg, "SenderEmailAddress", getattr(msg, "SenderName", "unknown"))),
                received_time=datetime.now(),
                body_text=str(msg.Body),
                attachments=attachments
            )
            results.append(ingested)

            if self.mark_as_read:
                msg.UnRead = False
                msg.Save()

            count += 1

        return results

    def _fetch_mock_emails(self) -> List[IngestedEmail]:
        """Provides mock ingested email if not running on Windows with Outlook MAPI."""
        return []


class EmailSnapshotRenderer:
    """Renders ingested email metadata and body text into a PDF snapshot for local archiving/auditing."""

    @staticmethod
    def render_email_to_pdf(email: IngestedEmail, output_pdf_path: str) -> str:
        """
        Renders an email to a PDF file at output_pdf_path.
        Returns the path to the created PDF file.
        """
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#003366')
        )
        meta_label_style = ParagraphStyle(
            'MetaLabel',
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=12,
            textColor=colors.HexColor('#333333')
        )
        meta_val_style = ParagraphStyle(
            'MetaVal',
            fontName='Helvetica',
            fontSize=10,
            leading=12,
            textColor=colors.HexColor('#111111')
        )
        body_style = ParagraphStyle(
            'BodyText',
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#222222')
        )

        elements = []

        # Header
        elements.append(Paragraph("Email Snapshot Audit Log", title_style))
        elements.append(Spacer(1, 10))

        # Metadata Table
        meta_data = [
            [Paragraph("Subject:", meta_label_style), Paragraph(html.escape(email.subject), meta_val_style)],
            [Paragraph("Sender:", meta_label_style), Paragraph(html.escape(email.sender), meta_val_style)],
            [Paragraph("Received Time:", meta_label_style), Paragraph(email.received_time.strftime("%Y-%m-%d %H:%M:%S"), meta_val_style)],
            [Paragraph("Message ID:", meta_label_style), Paragraph(html.escape(email.email_id), meta_val_style)],
            [Paragraph("Attachments:", meta_label_style), Paragraph(html.escape(", ".join([a.filename for a in email.attachments]) or "None"), meta_val_style)],
        ]

        table = Table(meta_data, colWidths=[100, 440])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F7FA')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#003366'), spaceAfter=15))

        # Email Body
        elements.append(Paragraph("<b>Email Body Content:</b>", meta_label_style))
        elements.append(Spacer(1, 8))

        escaped_body = html.escape(email.body_text)
        formatted_body = escaped_body.replace("\n", "<br/>")
        elements.append(Paragraph(formatted_body, body_style))

        doc.build(elements)
        return output_pdf_path
