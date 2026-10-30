"""Render the project's Markdown report as a downloadable PDF."""
from html import escape
from io import BytesIO
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _inline_markup(text: str) -> str:
    """Convert the small inline Markdown subset used by reports to ReportLab markup."""
    safe = escape(text, quote=False)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", safe)
    return safe


def markdown_to_pdf(markdown: str) -> bytes:
    """Return a formatted A4 PDF for a report produced by ``render_markdown``."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Executive summary and anomaly report",
        author="Projet 15 - Generative BI",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontSize=19,
                                leading=23, textColor=colors.HexColor("#16324F"),
                                alignment=TA_CENTER, spaceAfter=14),
        "h2": ParagraphStyle("ReportH2", parent=base["Heading2"], fontSize=13,
                              leading=16, textColor=colors.HexColor("#176B87"),
                              spaceBefore=8, spaceAfter=4, keepWithNext=True),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=9.5,
                                leading=12.5, spaceAfter=4, wordWrap="CJK"),
        "meta": ParagraphStyle("ReportMeta", parent=base["BodyText"], fontSize=8.5,
                                leading=12, textColor=colors.HexColor("#455468"),
                                leftIndent=8, spaceAfter=3),
        "bullet": ParagraphStyle("ReportBullet", parent=base["BodyText"], fontSize=9.5,
                                  leading=14, leftIndent=14, firstLineIndent=-9,
                                  spaceAfter=4),
    }

    story = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 3))
        elif line.startswith("# "):
            story.append(Paragraph(_inline_markup(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(_inline_markup(line[3:]), styles["h2"]))
        elif line.startswith("- "):
            meta = line.startswith(("- Scope:", "- Source:", "- Text generated", "- Generated on:"))
            style = styles["meta"] if meta else styles["bullet"]
            story.append(Paragraph("&#8226; " + _inline_markup(line[2:]), style))
        else:
            story.append(Paragraph(_inline_markup(line), styles["body"]))

    def page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#68778A"))
        canvas.drawString(20 * mm, 10 * mm, "Projet 15 - Generative BI")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    return buffer.getvalue()
