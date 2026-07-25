"""Native PDF renderer for the Module-7 investigation report.

Ported from the retired standalone ``report generation`` prototype (Module 6)
and rebuilt against the integrated report's ``sections`` model. The prototype's
two evidentiary features are preserved:

* every page carries a footer with the report ID and "Page X of Y", and
* the report embeds SHA-256 provenance hashes tying it to the exact stored
  artifacts it was generated from.

Rendering is strictly template-over-data: every paragraph is produced from a
concrete value in ``sections``; there is no free-text generation. If
``reportlab`` is not installed the caller receives ``None`` and the pipeline
continues (Markdown + JSON remain the canonical artifacts).
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

try:  # reportlab is an optional dependency (installed by dev.sh setup)
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas as _BaseCanvas
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _REPORTLAB = True
except ImportError:  # pragma: no cover - environment-dependent
    _REPORTLAB = False

ACCENT = "#14532d"
MUTED = "#4a5568"
RULE = "#cbd5e0"

#: Section rendering order and display titles (mirrors the Markdown renderer).
SECTION_TITLES = [
    ("executive_summary", "Executive Summary"),
    ("scope_and_methodology", "Scope & Methodology"),
    ("case_overview", "Case Overview"),
    ("evidence_summary", "Evidence Summary"),
    ("correlation_analysis", "Correlation Analysis"),
    ("cross_case_correlation", "Cross-Case Correlation"),
    ("campaign_analysis", "Campaign Analysis"),
    ("timeline_analysis", "Timeline Analysis"),
    ("suspect_assessment", "Suspect Assessment"),
    ("threat_intelligence_summary", "Threat Intelligence Summary"),
    ("model_predictions", "Model Prediction Results"),
    ("evidence_quality_summary", "Evidence Quality Summary"),
    ("metadata_summary", "Metadata Summary"),
    ("investigation_statistics", "Investigation Statistics"),
    ("confidence_analysis", "Confidence Analysis"),
    ("investigation_conclusion", "Investigation Conclusion"),
    ("recommendations", "Recommendations"),
    ("report_provenance", "Report Provenance & Integrity"),
    ("appendix", "Appendix"),
]


def _esc(value: Any) -> str:
    """Escape text for ReportLab's mini-HTML paragraph markup.

    Model reasons contain ``&`` and quoted brand names, which would otherwise
    be parsed as markup and abort the render.
    """
    return (str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _prediction_facts(row: Dict[str, Any]) -> List[str]:
    """Short 'label: value' facts behind a URL verdict, in reading order.

    Only what an investigator would cite. Fields the provider did not supply
    are skipped, so an offline analysis simply shows fewer facts instead of
    claiming a domain has no registrar or an age of zero.
    """
    facts: List[str] = []
    if row.get("domain"):
        facts.append(f"domain: {row['domain']}")
    if row.get("ip_address"):
        facts.append(f"resolves to: {row['ip_address']}")
    age = row.get("domain_age_days")
    if isinstance(age, int):
        facts.append(f"domain age: {age} day{'' if age == 1 else 's'}")
    if row.get("registrar"):
        facts.append(f"registrar: {row['registrar']}")
    if row.get("hosting"):
        facts.append(f"hosted by: {row['hosting']}")
    if row.get("ssl_status"):
        left = row.get("ssl_days_left")
        facts.append(f"SSL: {row['ssl_status']}"
                     + (f" ({left} days left)" if isinstance(left, int) else ""))
    if isinstance(row.get("spf_present"), bool):
        facts.append(f"SPF: {'present' if row['spf_present'] else 'missing'}")
    if isinstance(row.get("dmarc_present"), bool):
        facts.append(f"DMARC: {'present' if row['dmarc_present'] else 'missing'}")
    if row.get("brand_impersonated"):
        facts.append(f"brand: {row['brand_impersonated']}"
                     + ("" if row.get("official_domain") else " (impersonated)"))
    if isinstance(row.get("trust_score"), int):
        facts.append(f"trust: {row['trust_score']}/100")
    return facts


def available() -> bool:
    """True when reportlab is importable in this environment."""
    return _REPORTLAB


def render_pdf(
    case_id: str,
    sections: Dict[str, Any],
    *,
    report_id: str,
    generated_at: str,
    report_version: int = 1,
) -> Optional[bytes]:
    """Render the report to PDF bytes, or ``None`` if reportlab is missing."""
    if not _REPORTLAB:
        return None

    footer_text = f"{report_id}  ·  CIIS Investigation Report  ·  {case_id}"

    class _NumberedCanvas(_BaseCanvas):
        """Two-pass canvas so every footer can say 'Page X of Y'."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._saved: List[dict] = []

        def showPage(self) -> None:  # noqa: N802 - reportlab API
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_footer(self, total: int) -> None:
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor(MUTED))
            self.drawString(18 * mm, 10 * mm, footer_text)
            self.drawRightString(
                A4[0] - 18 * mm, 10 * mm, f"Page {self._pageNumber} of {total}"
            )
            self.setStrokeColor(colors.HexColor(RULE))
            self.setLineWidth(0.4)
            self.line(18 * mm, 13.5 * mm, A4[0] - 18 * mm, 13.5 * mm)

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "r_title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=17, leading=21, textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT, spaceAfter=2),
        "subtitle": ParagraphStyle(
            "r_subtitle", parent=base["Normal"], fontSize=9, leading=13,
            textColor=colors.HexColor(MUTED)),
        "h2": ParagraphStyle(
            "r_h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=15, textColor=colors.HexColor(ACCENT),
            spaceBefore=12, spaceAfter=4),
        "body": ParagraphStyle(
            "r_body", parent=base["Normal"], fontSize=9, leading=13.5,
            textColor=colors.HexColor("#1f2937")),
        "bullet": ParagraphStyle(
            "r_bullet", parent=base["Normal"], fontSize=9, leading=13.5,
            leftIndent=10, bulletIndent=2,
            textColor=colors.HexColor("#1f2937")),
        "mono": ParagraphStyle(
            "r_mono", parent=base["Normal"], fontName="Courier", fontSize=7.5,
            leading=10.5, textColor=colors.HexColor("#374151")),
    }

    def esc(value: Any) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    story: List[Any] = []

    # ------------------------------------------------------------- title block
    story.append(Paragraph(
        "CYBERCRIME INVESTIGATION INTELLIGENCE SYSTEM", styles["subtitle"]))
    story.append(Paragraph("Forensic Investigation Report", styles["title"]))
    story.append(Spacer(1, 3))
    header_rows = [
        ["Case ID", case_id, "Report ID", report_id],
        ["Generated (UTC)", generated_at, "Report version", f"v{report_version}"],
    ]
    header_table = Table(
        header_rows, colWidths=[28 * mm, 62 * mm, 28 * mm, 56 * mm])
    header_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor(RULE)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Every statement in this report references stored forensic findings; "
        "no content is generated outside computed results. Section "
        "“Report Provenance &amp; Integrity” lists the SHA-256 "
        "digests of the source artifacts.", styles["subtitle"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.8,
                            color=colors.HexColor(ACCENT)))

    # ------------------------------------------------------------ table helper
    def data_table(headers: List[str], rows: List[List[str]],
                   widths: Optional[List[float]] = None) -> Table:
        wrapped = [[Paragraph(f"<b>{esc(h)}</b>", styles["body"])
                    for h in headers]]
        for row in rows:
            wrapped.append([Paragraph(esc(cell), styles["body"])
                            for cell in row])
        table = Table(wrapped, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0fdf4")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor(RULE)),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return table

    # ------------------------------------------------- generic value rendering
    def emit(value: Any, indent: int = 0) -> None:
        pad = "&nbsp;" * (indent * 4)
        if value is None:
            story.append(Paragraph(f"{pad}• not available",
                                   styles["bullet"]))
        elif isinstance(value, str):
            style = styles["body"] if indent == 0 else styles["bullet"]
            prefix = "" if indent == 0 else f"{pad}• "
            story.append(Paragraph(prefix + esc(value), style))
        elif isinstance(value, (int, float, bool)):
            story.append(Paragraph(f"{pad}• {esc(value)}",
                                   styles["bullet"]))
        elif isinstance(value, list):
            if not value:
                story.append(Paragraph(f"{pad}• none", styles["bullet"]))
            for item in value:
                if isinstance(item, (dict, list)):
                    emit(item, indent)
                else:
                    story.append(Paragraph(f"{pad}• {esc(item)}",
                                           styles["bullet"]))
        elif isinstance(value, dict):
            for key, item in value.items():
                label = esc(str(key).replace("_", " "))
                if isinstance(item, (dict, list)):
                    story.append(Paragraph(f"{pad}• <b>{label}</b>:",
                                           styles["bullet"]))
                    emit(item, indent + 1)
                else:
                    story.append(Paragraph(
                        f"{pad}• <b>{label}</b>: {esc(item)}",
                        styles["bullet"]))
        else:
            story.append(Paragraph(f"{pad}• {esc(value)}",
                                   styles["bullet"]))

    # ----------------------------------------------- specialised section views
    def emit_evidence_table(rows: Any) -> bool:
        if not (isinstance(rows, list) and rows
                and isinstance(rows[0], dict) and "evidence_id" in rows[0]):
            return False
        story.append(data_table(
            ["Evidence", "File", "Acquired", "OCR conf.", "Integrity"],
            [[r.get("evidence_id", ""), r.get("file_name", ""),
              str(r.get("upload_time", ""))[:19],
              (f"{float(r.get('ocr_confidence') or 0) * 100:.0f}%"
               if r.get("ocr_confidence") is not None else "n/a"),
              "VERIFIED" if r.get("hash_verified") else "FAILED"]
             for r in rows],
            widths=[30 * mm, 52 * mm, 34 * mm, 20 * mm, 22 * mm]))
        story.append(Spacer(1, 3))
        story.append(Paragraph(
            "SHA-256 digests for each item are listed in the Appendix "
            "(chain of custody).", styles["subtitle"]))
        return True

    def emit_predictions_table(section: Any) -> bool:
        rows = (section or {}).get("predictions") if isinstance(section, dict) \
            else None
        if not rows:
            return False
        story.append(data_table(
            ["Indicator", "Verdict", "Risk", "Confidence", "Source model"],
            [[r.get("indicator", ""), str(r.get("verdict", "")).upper(),
              str(r.get("risk_score", "n/a")),
              (f"{float(r.get('confidence') or 0) * 100:.0f}%"
               if r.get("confidence") is not None else "n/a"),
              r.get("source", "")]
             for r in rows],
            widths=[58 * mm, 22 * mm, 14 * mm, 22 * mm, 42 * mm]))
        # The table gives the verdict; these paragraphs give the grounds for
        # it. Only flagged indicators are expanded - a clean URL needs no
        # justification and expanding every one would bury the findings.
        for row in rows:
            if str(row.get("verdict", "")).lower() not in ("malicious", "suspicious",
                                                           "phishing"):
                continue
            facts = _prediction_facts(row)
            reasons = [str(r) for r in (row.get("reasons") or []) if str(r).strip()]
            if not facts and not reasons:
                continue
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<b>{_esc(row.get('indicator', ''))}</b>", styles["body"]))
            if facts:
                story.append(Paragraph(
                    " &middot; ".join(_esc(f) for f in facts), styles["subtitle"]))
            for reason in reasons:
                story.append(Paragraph(f"&bull; {_esc(reason)}", styles["subtitle"]))
        remainder = {k: v for k, v in section.items() if k != "predictions"}
        if remainder:
            story.append(Spacer(1, 3))
            emit(remainder)
        return True

    # ------------------------------------------------------------- body build
    for key, title in SECTION_TITLES:
        if key not in sections:
            continue
        story.append(Paragraph(title, styles["h2"]))
        value = sections.get(key)
        if key == "evidence_summary" and emit_evidence_table(value):
            continue
        if key == "model_predictions" and emit_predictions_table(value):
            continue
        if key == "report_provenance" and isinstance(value, dict):
            hashes = value.get("source_artifact_hashes") or {}
            meta = {k: v for k, v in value.items()
                    if k != "source_artifact_hashes"}
            emit(meta)
            if hashes:
                story.append(Spacer(1, 2))
                story.append(Paragraph("<b>Source artifact digests "
                                       "(SHA-256):</b>", styles["body"]))
                for name, digest in hashes.items():
                    story.append(Paragraph(f"{esc(name)}: {esc(digest)}",
                                           styles["mono"]))
            continue
        emit(value)

    # -------------------------------------------------------- signature block
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor(RULE)))
    story.append(Spacer(1, 8))
    sign = Table(
        [["Prepared by (system)", "Reviewed by (investigator)"],
         ["Cybercrime Investigation Intelligence Engine\n"
          "Automated Phase-2 reporting module", ""],
         ["", ""],
         ["Date:", "Date:                    Signature:"]],
        colWidths=[87 * mm, 87 * mm])
    sign.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
        ("LINEABOVE", (0, 3), (-1, 3), 0.4, colors.HexColor(MUTED)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sign)

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"CIIS Investigation Report {case_id}",
        author="Cybercrime Investigation Intelligence Engine",
        subject=report_id,
    )
    document.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
