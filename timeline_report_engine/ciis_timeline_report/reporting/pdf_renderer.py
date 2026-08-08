"""Native PDF renderer for the Module-7 investigation report.

Ported from the retired standalone report-generator prototype (since removed)
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
from typing import Any, Dict, List, Optional, Sequence

from . import pdf_charts

try:  # reportlab is an optional dependency (installed by dev.sh setup)
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas as _BaseCanvas
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.tableofcontents import TableOfContents

    _REPORTLAB = True
except ImportError:  # pragma: no cover - environment-dependent
    _REPORTLAB = False

ACCENT = "#14532d"
MUTED = "#4a5568"
RULE = "#cbd5e0"

#: Handling caveat printed on the cover and in the header of every page.
#: A forensic report circulates outside the unit that produced it, so the
#: constraint has to travel with the paper, not with the covering email.
HANDLING = "RESTRICTED - LAW ENFORCEMENT SENSITIVE"

#: The issuing body, printed on the cover and in the running header.
ISSUING_BODY = "Cybercrime Investigation Intelligence System"

#: Section rendering order and display titles. Imported from the service so the
#: PDF, the Markdown and the stored JSON cannot present sections in different
#: orders - there is one definition, in ``service.SECTION_ORDER``.
def _section_titles() -> List[tuple]:
    from .service import SECTION_ORDER

    return list(SECTION_ORDER)


def _esc(value: Any) -> str:
    """Escape text for ReportLab's mini-HTML paragraph markup.

    Model reasons contain ``&`` and quoted brand names, which would otherwise
    be parsed as markup and abort the render.
    """
    return (str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def renderable(text: str) -> bool:
    """True when the standard-14 fonts can actually draw this string.

    Those fonts cover Latin-1 and nothing else. Devanagari passed to them is
    not rejected - it is silently drawn as placeholder boxes, so the Nepali
    title of the Act came out as ``IIIIIIIII (IIIIIIIIIIII)``. On a legal
    document that reads as corruption, which is worse than not printing it.

    Embedding a Devanagari face (Noto Sans Devanagari, OFL) would fix it
    properly and is the right eventual answer. Falling back to a font that
    merely happens to be installed on the machine doing the rendering is not:
    the same report would then look different depending on where it was
    produced, which is exactly what an evidentiary artifact must not do.
    """
    try:
        text.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


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


def _pretty(value: Any) -> str:
    """Render a scalar the way a reader expects to see it on paper.

    Booleans as yes/no rather than Python's ``True``; whole floats without a
    stray ``.0``; ``None`` as an explicit "not available" so a blank cell can
    never be mistaken for a measured zero.
    """
    if value is None:
        return "not available"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.2f}"
    if isinstance(value, list):
        return ", ".join(_pretty(v) for v in value) if value else "none"
    return str(value)


def _pct(value: Any) -> str:
    """A 0–1 fraction as a percentage; anything else passed through."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _short_ts(value: Any) -> str:
    """Trim an ISO timestamp to minutes — seconds never matter in a table."""
    text = str(value or "")
    return text[:16].replace("T", " ") if text else "—"


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

    # ASCII only: this line carries the identifiers a reader copies out of
    # the PDF, and the standard-14 fonts ship no ToUnicode map, so a
    # decorative separator extracts as a replacement char in some tools.
    footer_text = f"{report_id}  |  CIIS Investigation Report  |  {case_id}"

    class _NumberedCanvas(_BaseCanvas):
        """Two-pass canvas so every footer can say 'Page X of Y'.

        Also stamps the running header. Both are drawn on the second pass,
        once the total page count is known.
        """

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
                # The cover carries its own banner; a second one would just
                # repeat itself half an inch higher.
                if self._pageNumber > 1:
                    self._draw_header()
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_header(self) -> None:
            self.setFont("Helvetica-Bold", 6.5)
            self.setFillColor(colors.HexColor("#991b1b"))
            self.drawString(18 * mm, A4[1] - 11 * mm, HANDLING)
            self.setFont("Helvetica", 6.5)
            self.setFillColor(colors.HexColor(MUTED))
            self.drawRightString(A4[0] - 18 * mm, A4[1] - 11 * mm,
                                 f"{ISSUING_BODY}  |  Case {case_id}")
            self.setStrokeColor(colors.HexColor(RULE))
            self.setLineWidth(0.4)
            self.line(18 * mm, A4[1] - 13 * mm, A4[0] - 18 * mm, A4[1] - 13 * mm)

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

    class _ReportDoc(SimpleDocTemplate):
        """Feeds section headings to the table of contents as they are laid out.

        The TOC needs real page numbers, which are only known once the story
        has been placed - hence ``multiBuild``, which lays out twice and uses
        the first pass to resolve them.
        """

        def afterFlowable(self, flowable: Any) -> None:  # noqa: N802
            level = getattr(flowable, "_toc_level", None)
            if level is not None:
                self.notify("TOCEntry",
                            (level, flowable.getPlainText(), self.page))

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "r_title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=17, leading=21, textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT, spaceAfter=2),
        "subtitle": ParagraphStyle(
            "r_subtitle", parent=base["Normal"], fontSize=9, leading=13,
            textColor=colors.HexColor(MUTED)),
        "banner": ParagraphStyle(
            "r_banner", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=10, leading=14, alignment=TA_CENTER,
            textColor=colors.HexColor("#991b1b"),
            borderWidth=0.9, borderColor=colors.HexColor("#991b1b"),
            borderPadding=5),
        "h1": ParagraphStyle(
            "r_h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=13.5, leading=18, textColor=colors.HexColor("#111827"),
            spaceBefore=0, spaceAfter=2),
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
        "h3": ParagraphStyle(
            "r_h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=9.5, leading=13, textColor=colors.HexColor("#111827"),
            spaceBefore=6, spaceAfter=1),
        "caveat": ParagraphStyle(
            "r_caveat", parent=base["Normal"], fontSize=8, leading=11.5,
            textColor=colors.HexColor("#374151"),
            backColor=colors.HexColor("#f8fafc"),
            borderWidth=0.6, borderColor=colors.HexColor(RULE),
            borderPadding=6, spaceBefore=4),
        "end": ParagraphStyle(
            "r_end", parent=base["Normal"], fontSize=8, leading=11,
            alignment=TA_CENTER, textColor=colors.HexColor(MUTED)),
        # The opening statement of a section carries the finding; setting it
        # slightly larger stops it reading as the first of N equal bullets.
        "lead": ParagraphStyle(
            "r_lead", parent=base["Normal"], fontSize=9.8, leading=14.5,
            textColor=colors.HexColor("#111827")),
        "metric": ParagraphStyle(
            "r_metric", parent=base["Normal"], fontSize=14, leading=17,
            alignment=TA_CENTER, textColor=colors.HexColor(ACCENT)),
        "metric_label": ParagraphStyle(
            "r_metric_label", parent=base["Normal"], fontSize=6.2, leading=8,
            alignment=TA_CENTER, textColor=colors.HexColor(MUTED)),
        "caption": ParagraphStyle(
            "r_caption", parent=base["Normal"], fontSize=7, leading=9.5,
            textColor=colors.HexColor(MUTED)),
        "cell": ParagraphStyle(
            "r_cell", parent=base["Normal"], fontSize=8, leading=11,
            textColor=colors.HexColor("#1f2937")),
        "cell_mono": ParagraphStyle(
            "r_cell_mono", parent=base["Normal"], fontName="Courier",
            fontSize=7.2, leading=10, textColor=colors.HexColor("#1f2937")),
    }

    def esc(value: Any) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    story: List[Any] = []

    # -------------------------------------------------------------- cover page
    story.append(Spacer(1, 22 * mm))
    story.append(Paragraph(HANDLING, styles["banner"]))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph(ISSUING_BODY.upper(), styles["subtitle"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Forensic Investigation Report", styles["title"]))
    story.append(Spacer(1, 1.5 * mm))
    story.append(HRFlowable(width="100%", thickness=1.1,
                            color=colors.HexColor(ACCENT)))
    story.append(Spacer(1, 8 * mm))

    # Document-control block: what this document is, which case it belongs to,
    # and which revision the reader is holding.
    control_rows = [
        ["Case reference", case_id],
        ["Report reference", report_id],
        ["Report version", f"v{report_version}"],
        ["Date of issue (UTC)", generated_at],
        ["Status", "Final - machine generated"],
        ["Prepared by", f"{ISSUING_BODY}, automated analysis pipeline"],
        ["Handling", HANDLING.title()],
    ]
    control = Table(control_rows, colWidths=[45 * mm, 129 * mm])
    control.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(MUTED)),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor(RULE)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(control)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        "<b>Basis of this report.</b> Every statement is templated over a "
        "stored forensic finding; the generator has no free-text capability "
        "and cannot introduce a fact the analysis did not compute. Where an "
        "input was unavailable the report says so explicitly rather than "
        "inferring. Section 18, Report Provenance &amp; Integrity, lists the "
        "SHA-256 digest of every source artifact, so this document can be "
        "tied back to the exact evidence state it was produced from.",
        styles["body"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "<b>Distribution.</b> This report contains material relating to an "
        "active investigation. Onward disclosure is restricted to persons "
        "authorised by the case officer.", styles["body"]))
    story.append(PageBreak())

    # ---------------------------------------------------------------- contents
    story.append(Paragraph("Contents", styles["h1"]))
    story.append(Spacer(1, 3 * mm))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle(
        "toc0", fontName="Helvetica", fontSize=9.5, leading=16,
        leftIndent=0, firstLineIndent=0,
        textColor=colors.HexColor("#1f2937"))]
    story.append(toc)
    story.append(PageBreak())

    # ------------------------------------------------------------ table helper
    def data_table(headers: List[str], rows: List[List[str]],
                   widths: Optional[List[float]] = None,
                   mono_cols: Sequence[int] = ()) -> Table:
        """A repeating-header data table.

        Long tables are the normal case in this report (36 correlation pairs,
        every evidence item), so the header repeats on each page — a table
        whose headings are three pages back is unreadable — and rows are
        banded, which is what stops the eye losing its place when scanning
        across a wide row. Digest and identifier columns are set in Courier
        via ``mono_cols`` so characters align and a transposition is visible.
        """
        wrapped = [[Paragraph(f"<b>{esc(h)}</b>", styles["cell"])
                    for h in headers]]
        for row in rows:
            wrapped.append([
                Paragraph(esc(cell),
                          styles["cell_mono"] if i in mono_cols else styles["cell"])
                for i, cell in enumerate(row)])
        table = Table(wrapped, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0fdf4")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor(RULE)),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        # Zebra banding, applied to body rows only.
        for i in range(1, len(wrapped)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#fafbfc")))
        table.setStyle(TableStyle(style))
        return table

    # ------------------------------------------------------- layout helpers
    def metric_strip(pairs: List[tuple]) -> Optional[Table]:
        """A row of KPI cells: bold value over a small caption.

        Headline counts were previously bullets ("• pair count: 36"), which
        buries the one number a reader wants at a glance under the same
        typography as everything else.
        """
        cells = [p for p in pairs if p[1] is not None]
        if not cells:
            return None
        value_row = [Paragraph(f"<b>{esc(v)}</b>", styles["metric"])
                     for _, v in cells]
        label_row = [Paragraph(esc(label).upper(), styles["metric_label"])
                     for label, _ in cells]
        col = (174 * mm) / len(cells)
        table = Table([value_row, label_row], colWidths=[col] * len(cells))
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("LINEBELOW", (0, 1), (-1, 1), 0.8, colors.HexColor(ACCENT)),
            ("LINEBEFORE", (1, 0), (-1, -1), 0.4, colors.HexColor(RULE)),
        ]))
        return table

    def kv_table(data: Dict[str, Any],
                 skip: Sequence[str] = ()) -> Optional[Table]:
        """Two-column definition table for a flat mapping."""
        rows = [(k, v) for k, v in data.items()
                if k not in skip and not isinstance(v, (dict, list))]
        if not rows:
            return None
        wrapped = [[Paragraph(f"<b>{esc(str(k).replace('_', ' ').capitalize())}</b>",
                              styles["body"]),
                    Paragraph(esc(_pretty(v)), styles["body"])]
                   for k, v in rows]
        table = Table(wrapped, colWidths=[54 * mm, 120 * mm])
        table.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor(RULE)),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return table

    def numbered_list(items: Sequence[Any], lead: bool = False) -> None:
        """An ordered list of statements, numbered so they can be cited."""
        for i, item in enumerate(items, 1):
            text = _pretty(item)
            if not str(text).strip():
                continue
            style = styles["lead"] if (lead and i == 1) else styles["body"]
            story.append(Paragraph(
                f"<b>{i}.</b>&nbsp;&nbsp;{esc(text)}", style))
            story.append(Spacer(1, 3))

    def chart(drawing: Any, caption: str = "") -> None:
        """Place a chart, with its caption, keeping the two together."""
        if drawing is None:
            return
        block = [Spacer(1, 4), drawing]
        if caption:
            block.append(Spacer(1, 1))
            block.append(Paragraph(esc(caption), styles["caption"]))
        block.append(Spacer(1, 5))
        story.append(KeepTogether(block))

    def subhead(text: str) -> None:
        story.append(Paragraph(esc(text), styles["h3"]))

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

    def emit_statement_list(section: Any) -> bool:
        """Executive summary / conclusion / recommendations: numbered prose."""
        if not (isinstance(section, list) and section
                and all(not isinstance(i, (dict, list)) for i in section)):
            return False
        numbered_list(section, lead=True)
        return True

    def emit_flat_mapping(section: Any) -> bool:
        """A flat dict as a definition table instead of a bullet run."""
        if not isinstance(section, dict):
            return False
        table = kv_table(section)
        nested = {k: v for k, v in section.items() if isinstance(v, (dict, list))}
        if table is None and not nested:
            return False
        if table is not None:
            story.append(table)
        for key, value in nested.items():
            story.append(Spacer(1, 5))
            subhead(str(key).replace("_", " ").capitalize())
            if isinstance(value, list) and all(
                    not isinstance(i, (dict, list)) for i in value):
                for item in value:
                    story.append(Paragraph(f"&bull; {esc(_pretty(item))}",
                                           styles["bullet"]))
            else:
                emit(value)
        return True

    def emit_timeline(section: Any) -> bool:
        """Timeline: the stage ribbon first, then the milestones that made it."""
        if not isinstance(section, dict):
            return False
        if section.get("summary"):
            story.append(Paragraph(esc(section["summary"]), styles["lead"]))
            story.append(Spacer(1, 4))

        milestones = section.get("milestones") or []
        stages = section.get("stage_progression") or []
        if stages:
            # No per-stage event count exists in the data, so the ribbon shows
            # order and nothing else. Printing a count the engine never
            # computed would be a fabricated figure in a forensic document.
            chart(
                pdf_charts.timeline_strip(
                    [(str(s).replace("_", " "), None) for s in stages]),
                "Order in which the engine observed each stage of the attack.",
            )
        if section.get("progression_consistent") is not None:
            story.append(Paragraph(
                "Stage order is "
                + ("consistent with a typical scam progression."
                   if section["progression_consistent"]
                   else "OUT OF ORDER against a typical scam progression, "
                        "which can indicate multiple actors or a re-contact."),
                styles["subtitle"]))
            story.append(Spacer(1, 5))

        if milestones and isinstance(milestones[0], dict):
            subhead("Milestone events")
            story.append(data_table(
                ["When", "What happened"],
                [[_short_ts(m.get("timestamp")),
                  m.get("description") or m.get("event_type", "")]
                 for m in milestones],
                widths=[36 * mm, 138 * mm]))
            story.append(Spacer(1, 5))

        critical = section.get("critical_events") or []
        if critical and isinstance(critical[0], dict):
            subhead("Critical events")
            story.append(Paragraph(
                "Moments involving an OTP or a financial transfer — the points "
                "at which money or account control actually moved.",
                styles["caption"]))
            story.append(Spacer(1, 3))
            story.append(data_table(
                ["When", "Evidence", "Why it is critical"],
                [[_short_ts(c.get("timestamp")),
                  str(c.get("evidence_id", "")),
                  "; ".join(str(r) for r in (c.get("reasons") or []))
                  or str(c.get("description", ""))]
                 for c in critical],
                widths=[30 * mm, 26 * mm, 118 * mm]))
            story.append(Spacer(1, 4))

        # Anything the engine adds to this section later still reaches paper.
        handled = {"summary", "stage_progression", "progression_consistent",
                   "milestones", "critical_events"}
        rest = {k: v for k, v in section.items() if k not in handled}
        if rest:
            table = kv_table(rest)
            if table is not None:
                story.append(table)
            for key, value in rest.items():
                if isinstance(value, (dict, list)):
                    subhead(str(key).replace("_", " ").capitalize())
                    emit(value)
        return True

    def emit_correlation(section: Any) -> bool:
        """Correlation: counts, the strength distribution, then the pairs.

        Previously each pair emitted four sibling bullets (pair, strength,
        confidence, then a paragraph-long explanation), so thirty-six pairs
        became an unreadable column of a hundred and forty bullets. The
        ranking is the finding, so it becomes a sorted table.
        """
        if not isinstance(section, dict) or "top_relationships" not in section:
            return False

        strip = metric_strip([
            ("Pairs examined", section.get("pair_count")),
            ("Related pairs", section.get("related_pair_count")),
            ("Strongest link",
             _pct(max((r.get("confidence") or 0)
                      for r in section.get("top_relationships") or [{}]))
             if section.get("top_relationships") else None),
        ])
        if strip is not None:
            story.append(strip)
            story.append(Spacer(1, 6))

        dist = section.get("strength_distribution") or {}
        if dist:
            order = ["VERY_STRONG", "STRONG", "MEDIUM", "WEAK"]
            rows = [(k.replace("_", " ").title(), dist[k], pdf_charts.band_color(k))
                    for k in order if k in dist]
            rows += [(k.replace("_", " ").title(), v, pdf_charts.band_color(k))
                     for k, v in dist.items() if k not in order]
            chart(pdf_charts.vbar_chart(rows),
                  "How many evidence pairs fell into each strength band.")

        pairs = section.get("top_relationships") or []
        if pairs:
            subhead("Strongest relationships")
            story.append(data_table(
                ["Evidence pair", "Strength", "Confidence"],
                [[str(p.get("pair", "")),
                  str(p.get("strength", "")).replace("_", " "),
                  _pct(p.get("confidence"))]
                 for p in pairs],
                widths=[100 * mm, 40 * mm, 34 * mm]))
            # The explanation is the evidence for the row above it, so it is
            # kept as prose beneath the table rather than crammed into a cell
            # where it would force a column three lines deep.
            explained = [p for p in pairs if p.get("explanation")]
            if explained:
                story.append(Spacer(1, 6))
                subhead("Why each pair is linked")
                for p in explained:
                    story.append(KeepTogether([
                        Paragraph(f"<b>{esc(p.get('pair', ''))}</b> "
                                  f"({esc(_pct(p.get('confidence')))})",
                                  styles["body"]),
                        Paragraph(esc(p["explanation"]), styles["subtitle"]),
                        Spacer(1, 5),
                    ]))
        remainder = {k: v for k, v in section.items()
                     if k not in ("pair_count", "related_pair_count",
                                  "strength_distribution", "top_relationships")}
        if remainder:
            emit(remainder)
        return True

    def emit_cross_case(section: Any) -> bool:
        if not isinstance(section, dict) or "links" not in section:
            return False
        links = section.get("links") or []
        if not links:
            story.append(Paragraph(
                "This case shares no identifiers with any other case held by "
                "the engine.", styles["body"]))
            return True
        story.append(Paragraph(
            f"Identifiers from this case also appear in "
            f"{esc(section.get('related_case_count', len(links)))} other "
            f"case(s). A shared identifier is a lead, not proof the cases are "
            f"the same operation.", styles["body"]))
        story.append(Spacer(1, 4))
        story.append(data_table(
            ["Related case", "Strength", "Confidence", "Shared identifiers"],
            [[str(l.get("other_case_id", "")),
              str(l.get("relationship_strength", "")).replace("_", " "),
              _pct(l.get("match_confidence")),
              str(len(l.get("matched_entities") or []))]
             for l in links],
            widths=[54 * mm, 34 * mm, 30 * mm, 56 * mm]))
        for link in links:
            entities = link.get("matched_entities") or []
            story.append(Spacer(1, 6))
            subhead(f"Shared with {link.get('other_case_id', '')}")
            if link.get("match_reason"):
                story.append(Paragraph(esc(link["match_reason"]),
                                       styles["subtitle"]))
                story.append(Spacer(1, 3))
            if entities:
                # Both sides' evidence ids are listed: the point of a
                # cross-case link is being able to pull the exact exhibit in
                # the other case, which a count alone does not let you do.
                # Specificity is only present on some artifact versions; an
                # all-dashes column just makes the reader hunt for a meaning.
                has_spec = any(e.get("specificity") is not None for e in entities)
                headers = ["Type", "Value"] + (["Spec."] if has_spec else []) \
                    + ["This case", "Other case"]
                widths = ([26 * mm, 56 * mm] + ([14 * mm] if has_spec else [])
                          + ([39 * mm, 39 * mm] if has_spec
                             else [46 * mm, 46 * mm]))
                story.append(data_table(
                    headers,
                    [[str(e.get("entity_type", "")).replace("_", " "),
                      str(e.get("value", ""))]
                     + ([f"{float(e['specificity']):.2f}"
                         if e.get("specificity") is not None else "—"]
                        if has_spec else [])
                     + [", ".join(str(i) for i in (e.get("this_evidence_ids") or [])),
                        ", ".join(str(i) for i in (e.get("other_evidence_ids") or []))]
                     for e in entities],
                    widths=widths))
            rest = kv_table(link, skip=("other_case_id", "relationship_strength",
                                        "match_confidence", "match_reason"))
            if rest is not None:
                story.append(Spacer(1, 3))
                story.append(rest)
        remainder = {k: v for k, v in section.items()
                     if k not in ("links", "related_case_count")}
        if remainder:
            story.append(Spacer(1, 4))
            emit(remainder)
        return True

    def emit_campaigns(section: Any) -> bool:
        if not isinstance(section, dict) or "campaigns" not in section:
            return False
        campaigns = section.get("campaigns") or []
        strip = metric_strip([
            ("Campaigns detected", section.get("campaign_count", len(campaigns))),
            ("Unclustered items", len(section.get("unclustered_evidence") or [])),
        ])
        if strip is not None:
            story.append(strip)
            story.append(Spacer(1, 6))
        if not campaigns:
            story.append(Paragraph(
                "The engine did not cluster this case's evidence into a "
                "coordinated campaign.", styles["body"]))
            return True

        for campaign in campaigns:
            members = campaign.get("members") or []
            # `confidence` here is a 0-1 fraction; older artifacts used
            # `campaign_confidence`. Accept either rather than printing n/a.
            confidence = campaign.get("confidence")
            if confidence is None:
                confidence = campaign.get("campaign_confidence")
            block: List[Any] = [
                Paragraph(f"{esc(campaign.get('campaign_id', 'Campaign'))} "
                          f"&ndash; {len(members)} item(s), confidence "
                          f"{esc(_pct(confidence))}", styles["h3"]),
            ]
            if campaign.get("summary"):
                block.append(Paragraph(esc(campaign["summary"]), styles["body"]))
            block.append(Spacer(1, 3))
            story.append(KeepTogether(block))

            signature = campaign.get("signature") or []
            if signature:
                story.append(data_table(
                    ["Shared signature"],
                    [[str(s)] for s in signature],
                    widths=[174 * mm]))
                story.append(Spacer(1, 3))
            if members:
                story.append(Paragraph(
                    "<b>Members.</b> " + esc(", ".join(str(m) for m in members)),
                    styles["subtitle"]))
            memberships = campaign.get("memberships") or []
            if memberships:
                story.append(Spacer(1, 3))
                story.append(data_table(
                    ["Evidence", "Why it belongs to this campaign"],
                    [[str(m.get("evidence_id", "")),
                      m.get("membership_explanation")
                      or "; ".join(str(r) for r in (m.get("link_reasons") or []))]
                     for m in memberships],
                    widths=[34 * mm, 140 * mm]))
            leftover = kv_table(campaign, skip=("campaign_id", "members",
                                                "confidence",
                                                "campaign_confidence",
                                                "signature", "summary"))
            if leftover is not None:
                story.append(Spacer(1, 3))
                story.append(leftover)
            story.append(Spacer(1, 7))

        unclustered = section.get("unclustered_evidence") or []
        if unclustered:
            subhead("Not clustered into any campaign")
            story.append(Paragraph(
                esc(", ".join(str(u) for u in unclustered)), styles["subtitle"]))
        return True

    def emit_suspects(section: Any) -> bool:
        """Suspects ranked, charted, then justified — never a bullet dump."""
        if not (isinstance(section, list) and section
                and isinstance(section[0], dict)
                and "identity" in section[0]
                and "confidence_score" in section[0]):
            return False

        def split_identity(value: Any) -> tuple:
            """`khalti_ids:+977…` -> ("khalti ids", "+977…")."""
            text = str(value or "")
            kind, sep, ident = text.partition(":")
            return ((kind.replace("_", " "), ident) if sep else ("", text))

        ranked = sorted(section,
                        key=lambda s: float(s.get("confidence_score") or 0),
                        reverse=True)
        chart(
            pdf_charts.hbar_chart(
                [(split_identity(s.get("identity"))[1],
                  float(s.get("confidence_score") or 0),
                  pdf_charts.band_color(
                      s.get("risk_level") or s.get("confidence_level") or "medium"))
                 for s in ranked[:12]],
                max_value=100.0, label_w_mm=58),
            "How strongly each identifier is connected to this case, out of "
            "100. This measures strength of association with the evidence; it "
            "is not a finding of guilt.",
        )
        story.append(data_table(
            ["Identifier", "Type", "Risk", "Confidence", "Score", "Appears in"],
            [[split_identity(s.get("identity"))[1],
              split_identity(s.get("identity"))[0],
              str(s.get("risk_level", "")),
              str(s.get("confidence_level", "")),
              _pretty(s.get("confidence_score")),
              ", ".join(str(i) for i in (s.get("evidence_ids") or []))]
             for s in ranked],
            widths=[46 * mm, 24 * mm, 18 * mm, 22 * mm, 16 * mm, 48 * mm]))

        explained = [s for s in ranked if s.get("explanation")]
        if explained:
            story.append(Spacer(1, 6))
            subhead("Basis for each ranked identifier")
            for s in explained:
                story.append(KeepTogether([
                    Paragraph(
                        f"<b>{esc(split_identity(s.get('identity'))[1])}</b> "
                        f"({esc(s.get('suspect_id', ''))})", styles["body"]),
                    Paragraph(esc(s["explanation"]), styles["subtitle"]),
                    Spacer(1, 5),
                ]))
        return True

    def emit_threat_intel(section: Any) -> bool:
        if not isinstance(section, dict) or "indicators_checked" not in section:
            return False
        strip = metric_strip([
            ("Indicators checked", _pretty(section.get("indicators_checked"))),
            ("Malicious", _pretty(section.get("malicious_indicators"))),
            ("Suspicious", _pretty(section.get("suspicious_indicators"))),
            ("Items affected", _pretty(section.get("evidence_with_threats"))),
        ])
        if strip is not None:
            story.append(strip)
            story.append(Spacer(1, 6))
        malicious = float(section.get("malicious_indicators") or 0)
        suspicious = float(section.get("suspicious_indicators") or 0)
        checked = float(section.get("indicators_checked") or 0)
        clean = max(0.0, checked - malicious - suspicious)
        chart(
            pdf_charts.stacked_share_bar([
                ("Malicious", malicious, pdf_charts.band_color("bad")),
                ("Suspicious", suspicious, pdf_charts.band_color("high")),
                ("Clean", clean, pdf_charts.band_color("good")),
            ]),
            "Verdicts returned for every indicator the engine checked.",
        )
        rest = kv_table(section, skip=("indicators_checked",
                                       "malicious_indicators",
                                       "suspicious_indicators",
                                       "evidence_with_threats"))
        if rest is not None:
            story.append(rest)
        return True

    def emit_quality(section: Any) -> bool:
        if not isinstance(section, dict) or "mean_evidence_confidence" not in section:
            return False
        strip = metric_strip([
            ("Mean confidence", _pretty(section.get("mean_evidence_confidence"))),
            ("Mean image quality", _pretty(section.get("mean_image_quality"))),
            ("Mean forgery score", _pretty(section.get("mean_forgery_score"))),
            ("Worst forgery score", _pretty(section.get("max_forgery_score"))),
        ])
        if strip is not None:
            story.append(strip)
            story.append(Spacer(1, 5))
        worst = section.get("max_forgery_score")
        if isinstance(worst, (int, float)) and float(worst) >= 50:
            story.append(Paragraph(
                f"<b>Attention.</b> The worst forgery score in this case is "
                f"{esc(_pretty(worst))}/100, at or above the threshold the "
                f"engine treats as possible tampering. The affected item "
                f"should be examined manually before it is relied upon.",
                styles["caveat"]))
            story.append(Spacer(1, 4))
        rest = kv_table(section, skip=("mean_evidence_confidence",
                                       "mean_image_quality",
                                       "mean_forgery_score",
                                       "max_forgery_score"))
        if rest is not None:
            story.append(rest)
        return True

    def emit_dict_list(section: Any, title_hint: str = "") -> bool:
        """A uniform list of flat dicts as one table with shared columns.

        Columns come from the scalar fields. Fields holding a list (notes,
        reasons) will not fit a cell, so they are printed under the table
        keyed by the row they belong to — dropping them would lose findings
        such as the EXIF consistency notes.
        """
        if not (isinstance(section, list) and section
                and all(isinstance(r, dict) for r in section)):
            return False
        keys: List[str] = []
        list_keys: List[str] = []
        for row in section:
            for k, v in row.items():
                if isinstance(v, dict):
                    return False  # nested objects need a bespoke layout
                if isinstance(v, list):
                    if k not in list_keys:
                        list_keys.append(k)
                elif k not in keys:
                    keys.append(k)
        if not keys:
            return False

        # A paragraph-length field (an explanation) cannot share a row with
        # short columns: it forces the whole table six lines deep and the
        # short values drift apart. Those fields are printed below instead.
        def longest(key: str) -> int:
            return max((len(str(r.get(key) or "")) for r in section), default=0)

        prose_keys = [k for k in keys if longest(k) > 90]
        keys = [k for k in keys if k not in prose_keys]
        if not keys or len(keys) > 7:
            return False

        # The first column is usually the identifier; use it to key the notes.
        id_key = keys[0]
        story.append(data_table(
            [k.replace("_", " ").capitalize() for k in keys],
            [[_pretty(row.get(k)) for k in keys] for row in section]))

        for list_key in list_keys:
            entries = [(row.get(id_key), row.get(list_key) or [])
                       for row in section if row.get(list_key)]
            if not entries:
                continue
            story.append(Spacer(1, 5))
            subhead(str(list_key).replace("_", " ").capitalize())
            for row_id, items in entries:
                story.append(Paragraph(
                    f"<b>{esc(_pretty(row_id))}</b> &mdash; "
                    + esc("; ".join(_pretty(i) for i in items)),
                    styles["subtitle"]))
                story.append(Spacer(1, 2))

        for prose_key in prose_keys:
            entries = [(row.get(id_key), row.get(prose_key))
                       for row in section if row.get(prose_key)]
            if not entries:
                continue
            story.append(Spacer(1, 5))
            subhead(str(prose_key).replace("_", " ").capitalize())
            for row_id, text in entries:
                story.append(KeepTogether([
                    Paragraph(f"<b>{esc(_pretty(row_id))}</b>", styles["body"]),
                    Paragraph(esc(_pretty(text)), styles["subtitle"]),
                    Spacer(1, 4),
                ]))
        return True

    def emit_statistics(section: Any) -> bool:
        """Grouped counters as one table per group, not nested bullets."""
        if not isinstance(section, dict):
            return False
        groups = {k: v for k, v in section.items() if isinstance(v, dict) and v}
        if not groups:
            return False
        flat = kv_table(section)
        if flat is not None:
            story.append(flat)
            story.append(Spacer(1, 5))
        for name, group in groups.items():
            subhead(str(name).replace("_", " ").capitalize())
            scalars = {k: v for k, v in group.items()
                       if not isinstance(v, (dict, list))}
            if scalars:
                story.append(data_table(
                    ["Measure", "Value"],
                    [[k.replace("_", " ").capitalize(), _pretty(v)]
                     for k, v in scalars.items()],
                    widths=[110 * mm, 64 * mm]))
                story.append(Spacer(1, 5))
            nested = {k: v for k, v in group.items() if isinstance(v, (dict, list))}
            for key, value in nested.items():
                story.append(Paragraph(
                    f"<b>{esc(str(key).replace('_', ' ').capitalize())}</b>",
                    styles["body"]))
                emit(value, 1)
        return True

    def emit_appendix(section: Any) -> bool:
        if not isinstance(section, dict):
            return False
        custody = section.get("chain_of_custody")
        if isinstance(custody, list) and custody and isinstance(custody[0], dict):
            subhead("Chain of custody")
            core = ("evidence_id", "file_name", "upload_time", "sha256", "hash")
            # Columns follow what this artifact actually carries — older
            # exports include a file name, current ones do not, and an empty
            # column in a custody table invites the reader to wonder what is
            # missing. The digest is the evidentiary heart of the section, so
            # it gets a full-width line per item instead of a column that
            # would wrap a hash mid-string.
            has_file = any(c.get("file_name") for c in custody)
            headers = ["Evidence"] + (["File"] if has_file else []) \
                + ["Acquired", "Status"]
            widths = ([28 * mm] + ([74 * mm] if has_file else [])
                      + ([34 * mm, 38 * mm] if has_file else [98 * mm, 48 * mm]))
            story.append(data_table(
                headers,
                [[str(c.get("evidence_id", ""))]
                 + ([str(c.get("file_name", ""))] if has_file else [])
                 + [_short_ts(c.get("upload_time")), _pretty(c.get("status", ""))]
                 for c in custody],
                widths=widths))
            story.append(Spacer(1, 4))
            subhead("Acquisition digests (SHA-256)")
            for c in custody:
                digest = c.get("sha256") or c.get("hash")
                if not digest:
                    continue
                story.append(Paragraph(
                    f"{esc(c.get('evidence_id', ''))}: {esc(digest)}",
                    styles["mono"]))
            extra_keys = [k for c in custody for k in c
                          if k not in core and k != "status"]
            if extra_keys:
                story.append(Spacer(1, 4))
                for c in custody:
                    leftover = {k: v for k, v in c.items()
                                if k not in core and k != "status"}
                    if leftover:
                        story.append(Paragraph(
                            f"<b>{esc(c.get('evidence_id', ''))}</b> &mdash; "
                            + esc("; ".join(f"{k.replace('_', ' ')}: {_pretty(v)}"
                                            for k, v in leftover.items())),
                            styles["subtitle"]))
            story.append(Spacer(1, 5))
        rest = kv_table(section, skip=("chain_of_custody",))
        if rest is not None:
            story.append(rest)
        other = {k: v for k, v in section.items()
                 if k != "chain_of_custody" and isinstance(v, (dict, list))}
        for key, value in other.items():
            story.append(Spacer(1, 4))
            subhead(str(key).replace("_", " ").capitalize())
            emit(value)
        return True

    def emit_legal_basis(section: Any) -> bool:
        """Statutory basis: each provision as a titled block, not a bullet dump.

        The distinction between one section of the Act and the next is the whole
        point of this part of the report, so it gets headings and a boxed
        caveat rather than the generic key/value rendering.
        """
        if not isinstance(section, dict) or "provisions" not in section:
            return False

        if section.get("summary"):
            story.append(Paragraph(esc(section["summary"]), styles["body"]))
            story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<b>Statute:</b> {esc(section.get('statute', 'not available'))} "
            f"&nbsp;|&nbsp; <b>Jurisdiction:</b> "
            f"{esc(section.get('jurisdiction', 'not available'))}",
            styles["subtitle"]))
        # Which language text governs is not a footnote in a filing. The note
        # names the Act in Devanagari, which this PDF cannot draw, so the
        # printed form points at the sources instead of showing boxes. The
        # Markdown and JSON exports carry the Nepali title in full.
        note = section.get("language_note")
        if note and not renderable(note):
            note = ("Cited from the English text of the Act. The Nepali text is "
                    "authoritative where the two differ; verify any provision "
                    "against the Nepali gazette copy in samples/legal_corpus/ "
                    "before relying on it in a filing. (The Nepali title is "
                    "given in the Markdown and JSON versions of this report; "
                    "this PDF uses a Latin-only font set.)")
        if note:
            story.append(Paragraph(esc(note), styles["subtitle"]))
        story.append(Spacer(1, 6))

        for provision in section.get("provisions") or []:
            block: List[Any] = [
                Paragraph(
                    f"Section {esc(provision['section'])} &ndash; "
                    f"{esc(provision['title'])}", styles["h3"]),
                Paragraph(esc(provision["citation"]), styles["subtitle"]),
                Spacer(1, 3),
                Paragraph(f"<b>Conduct.</b> {esc(provision['conduct'])}",
                          styles["body"]),
                Paragraph(f"<b>Penalty.</b> {esc(provision['penalty'])}",
                          styles["body"]),
                Paragraph(f"<b>Why this is engaged.</b> {esc(provision['basis'])}",
                          styles["body"]),
            ]
            if provision.get("evidence_ids"):
                block.append(Paragraph(
                    f"<b>Evidence.</b> {esc(', '.join(provision['evidence_ids']))}",
                    styles["subtitle"]))
            block.append(Spacer(1, 8))
            # A provision split across a page break reads as two half-findings.
            story.append(KeepTogether(block))

        if section.get("caveat"):
            story.append(Spacer(1, 2))
            story.append(Paragraph(esc(section["caveat"]), styles["caveat"]))
        return True

    # ------------------------------------------------------------- body build
    #
    # Sections are numbered so the report can be cited precisely — "see 6.2"
    # is how an investigator, a prosecutor or a defence expert refers to a
    # finding, and an unnumbered document cannot be cross-referenced at all.
    number = 0
    for key, title in _section_titles():
        if key not in sections:
            continue
        number += 1
        heading = Paragraph(f"{number}. {title}", styles["h2"])
        heading._toc_level = 0  # picked up by _ReportDoc.afterFlowable
        story.append(heading)
        value = sections.get(key)

        # Every section gets a layout chosen for the shape of its data. The
        # generic `emit` below is the fallback for anything a renderer
        # declines, so an unexpected shape degrades to bullets rather than
        # failing — but nothing routinely reaches it any more.
        specialised = {
            "executive_summary": emit_statement_list,
            "scope_and_methodology": emit_flat_mapping,
            "case_overview": emit_flat_mapping,
            "evidence_summary": emit_evidence_table,
            "timeline_analysis": emit_timeline,
            "correlation_analysis": emit_correlation,
            "cross_case_correlation": emit_cross_case,
            "campaign_analysis": emit_campaigns,
            "suspect_assessment": emit_suspects,
            "threat_intelligence_summary": emit_threat_intel,
            "model_predictions": emit_predictions_table,
            "evidence_quality_summary": emit_quality,
            "metadata_summary": emit_dict_list,
            "investigation_statistics": emit_statistics,
            "confidence_analysis": emit_dict_list,
            "investigation_conclusion": emit_statement_list,
            "legal_basis": emit_legal_basis,
            "recommendations": emit_statement_list,
            "appendix": emit_appendix,
        }
        renderer = specialised.get(key)
        if renderer is not None:
            try:
                if renderer(value):
                    continue
            except Exception:  # noqa: BLE001
                # A malformed section must not cost the reader the whole
                # report; fall through to the generic rendering instead.
                pass
        if key in ("confidence_analysis", "metadata_summary") \
                and emit_statement_list(value):
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

    # ------------------------------------------------- limitations & signature
    #
    # A forensic report states what it cannot support as plainly as what it
    # can. Without this, a reader can mistake a correlation score for a
    # finding of fact, which is exactly the error that discredits a report
    # under cross-examination.
    number += 1
    limits_heading = Paragraph(f"{number}. Statement of Limitations",
                               styles["h2"])
    limits_heading._toc_level = 0
    story.append(limits_heading)
    for line in (
        "This report is produced by automated analysis of the material "
        "submitted to the case. It does not constitute an opinion on guilt, "
        "and no conclusion here should be read as attributing an offence to a "
        "named person.",
        "Correlation confidence expresses how strongly two items of evidence "
        "share identifying features. It is a measure of association, not of "
        "causation, and not of identity.",
        "Suspect scores rank identity anchors observed in the evidence by how "
        "strongly the material connects them to the case. An anchor is not a "
        "suspect in law until corroborated by investigation.",
        "Timestamps resolved from the content of an exhibit carry the "
        "reliability of that content. Where no timestamp could be recovered, "
        "the acquisition time is used and is labelled as such.",
        "The analysis reflects the evidence held at the date of issue. "
        "Material submitted later may change any finding in this report.",
    ):
        story.append(Paragraph(f"&bull; {line}", styles["bullet"]))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor(RULE)))
    story.append(Spacer(1, 8))
    sign = Table(
        [["Prepared by (system)", "Reviewed by (investigating officer)"],
         [f"{ISSUING_BODY}\nAutomated analysis pipeline", ""],
         ["", ""],
         [f"Report reference: {report_id}",
          "Name:                                        "],
         [f"Date of issue: {generated_at[:10]}",
          "Signature:                          Date:            "]],
        colWidths=[87 * mm, 87 * mm])
    sign.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
        ("LINEABOVE", (0, 3), (-1, 3), 0.4, colors.HexColor(MUTED)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(KeepTogether(sign))

    # Tells the reader nothing is missing from the copy in their hands.
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"- End of report | {report_id} -", styles["end"]))

    buffer = io.BytesIO()
    document = _ReportDoc(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"CIIS Investigation Report {case_id}",
        author=ISSUING_BODY,
        subject=f"Forensic investigation report {report_id} for case {case_id}",
    )
    # Two passes: the first resolves the page number of every heading, the
    # second lays the document out again with a populated contents page.
    document.multiBuild(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
