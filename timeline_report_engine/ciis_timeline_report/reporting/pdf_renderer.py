"""Native PDF renderer for the Module-7 investigation report.

Ported from the retired standalone report-generator prototype (since removed)
and rebuilt against the integrated report's ``sections`` model. The prototype's
two evidentiary features are preserved:

* every page carries a footer with the report ID and "Page X of Y", and
* the report embeds an evidence-set SHA-256 control value, while the canonical
  JSON companion retains the complete source-artifact hash register.

Rendering is strictly template-over-data: every paragraph is produced from a
concrete value in ``sections``; there is no free-text generation. If
``reportlab`` is not installed the caller receives ``None`` and the pipeline
continues (Markdown + JSON remain the canonical artifacts).
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional

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
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.graphics.charts.piecharts import Pie

    _REPORTLAB = True
except ImportError:  # pragma: no cover - environment-dependent
    _REPORTLAB = False

ACCENT = "#14532d"
MUTED = "#4a5568"
RULE = "#cbd5e0"
COVER_DARK = "#123c2a"
COVER_GOLD = "#d6b45f"
BODY_FONT = "Times-Roman"
BODY_FONT_BOLD = "Times-Bold"

# Investigator-facing PDF sections. The JSON and Markdown retain the complete
# machine-readable module contract; the PDF groups those data around the
# decisions an investigating officer needs to make.
PDF_SECTION_TITLES = (
    "Executive Brief",
    "Evidence Register and Integrity",
    "Reconstructed Incident Chronology",
    "Analytical Findings",
    "Statutory and Regulatory Screening",
    "Investigator Action Plan",
    "Methodology, Limitations and Conclusion",
    "Report Control and Review Certification",
)

#: Handling caveat printed on the cover and in the header of every page.
#: A forensic report circulates outside the unit that produced it, so the
#: constraint has to travel with the paper, not with the covering email.
HANDLING = "RESTRICTED - LAW ENFORCEMENT SENSITIVE"

#: The issuing body, printed on the cover and in the running header.
SYSTEM_NAME = (
    "Cybercrime Investigation Intelligent Engine using Digital Evidence Correlation"
)
ISSUING_BODY = "Cybercrime Investigation Intelligent Engine"

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


def _short(value: Any, limit: int = 180) -> str:
    """Compact prose for a table cell without cutting a word in half."""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0] + "..."


def _signal_summary(reasons: Any, limit: int = 230) -> str:
    """Turn engine-style critical reasons into investigator-readable signals."""
    cleaned: List[str] = []
    for reason in reasons or []:
        for part in str(reason).split(";"):
            label, separator, value = part.strip().partition(":")
            label = label.removeprefix("contains ").replace(
                " entity/entities", ""
            ).replace("_", " ").strip().title()
            phrase = f"{label}: {value.strip()}" if separator else label
            if phrase and phrase not in cleaned:
                cleaned.append(phrase)
    return _short("; ".join(cleaned) or "No recorded reason", limit)


def _relationship_basis(value: Any, limit: int = 145) -> str:
    """Remove pair/rating repetition already represented by adjacent columns."""
    text = " ".join(str(value or "").split())
    marker = "Both items "
    if marker in text:
        text = marker + text.split(marker, 1)[1]
    return _short(text, limit)


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


#: Figure palette. Distinct in colour *and* in order, so a chart survives
#: being printed in greyscale — which is how a case file usually travels.
_FIGURE_COLORS = ("#1a5c3a", "#2f7d5c", "#5aa17f", "#8cc0a6", "#b9d9c8", "#d8e8df")


def _figure_caption_style(styles) -> Any:
    """Caption style for a figure, reusing the document's caveat styling."""
    return styles["caveat"]


def _bar_figure(
    pairs: List[tuple],
    *,
    width: float,
    value_label: str = "",
    max_bars: int = 8,
) -> Optional[Any]:
    """A horizontal bar figure for ``(label, value)`` pairs.

    Horizontal rather than vertical because the labels here are words -
    "Timeline criticality", "esewa_ids" - and vertical bars would either
    clip them or turn them on their side. Returns ``None`` when there is
    nothing to plot, so a caller can skip the whole figure block.
    """
    usable = [(str(label), float(value)) for label, value in pairs
              if isinstance(value, (int, float)) and float(value) > 0]
    if not usable:
        return None
    usable = usable[:max_bars]

    row_height = 13
    chart_height = max(46, row_height * len(usable))
    drawing = Drawing(width, chart_height + 24)

    chart = HorizontalBarChart()
    chart.x = 96
    chart.y = 8
    chart.height = chart_height
    # Every bar prints its own value past its tip, so the plot has to stop
    # short of the page edge by more than the longest of those labels -
    # otherwise a full-width bar pushes "100.0" off the paper.
    chart.width = max(80, width - chart.x - 52)
    chart.data = [[value for _, value in usable]]
    # Bars read top-to-bottom in the order given; reportlab plots the first
    # datum at the bottom, so the list is reversed to match the reading order.
    chart.data = [list(reversed(chart.data[0]))]
    chart.categoryAxis.categoryNames = [label for label, _ in reversed(usable)]
    chart.categoryAxis.labels.fontName = BODY_FONT
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.dx = -4
    chart.categoryAxis.labels.boxAnchor = "e"
    chart.categoryAxis.strokeColor = colors.HexColor(RULE)
    chart.valueAxis.valueMin = 0
    # The axis itself is dead ink here: each bar is labelled with its exact
    # value, so a second, coarser reading of the same number only adds rules
    # and tick marks across the foot of the figure.
    chart.valueAxis.visible = 0
    chart.barSpacing = 2
    chart.barWidth = 7
    chart.bars[0].fillColor = colors.HexColor(_FIGURE_COLORS[1])
    chart.bars[0].strokeColor = colors.HexColor(_FIGURE_COLORS[0])
    chart.bars[0].strokeWidth = 0.4
    # Print each bar's value at its tip: a reader citing this report needs the
    # figure, not an estimate off an axis.
    chart.barLabels.fontName = BODY_FONT
    chart.barLabels.fontSize = 7
    chart.barLabelFormat = "%0.1f" if any(
        abs(v - round(v)) > 0.05 for _, v in usable
    ) else "%d"
    chart.barLabels.dx = 7
    drawing.add(chart)

    if value_label:
        drawing.add(String(
            chart.x, chart_height + 15, value_label,
            fontName=BODY_FONT, fontSize=7,
            fillColor=colors.HexColor(MUTED),
        ))
    return drawing


def _pie_figure(pairs: List[tuple], *, width: float) -> Optional[Any]:
    """A labelled pie for ``(label, count)`` pairs; ``None`` when empty."""
    usable = [(str(label), float(value)) for label, value in pairs
              if isinstance(value, (int, float)) and float(value) > 0]
    if not usable:
        return None

    total = sum(value for _, value in usable)
    drawing = Drawing(width, 128)
    pie = Pie()
    pie.x = 12
    pie.y = 10
    pie.width = 108
    pie.height = 108
    pie.data = [value for _, value in usable]
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 0.75
    for index in range(len(usable)):
        pie.slices[index].fillColor = colors.HexColor(
            _FIGURE_COLORS[index % len(_FIGURE_COLORS)]
        )
    drawing.add(pie)

    # A legend beside the pie rather than labels on the slices: slice labels
    # collide as soon as one share is small, and these shares often are.
    legend_x = 138
    legend_y = 108
    for index, (label, value) in enumerate(usable):
        share = (value / total * 100) if total else 0
        drawing.add(String(
            legend_x, legend_y - index * 12,
            f"{label}: {value:g} ({share:.0f}%)",
            fontName=BODY_FONT, fontSize=7.5,
            fillColor=colors.HexColor("#1a202c"),
        ))
    return drawing


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
            self.setFont(BODY_FONT_BOLD, 7)
            self.setFillColor(colors.HexColor("#991b1b"))
            self.drawString(18 * mm, A4[1] - 11 * mm, HANDLING)
            self.setFont(BODY_FONT, 7)
            self.setFillColor(colors.HexColor(MUTED))
            self.drawRightString(A4[0] - 18 * mm, A4[1] - 11 * mm,
                                 f"{ISSUING_BODY}  |  Case {case_id}")
            self.setStrokeColor(colors.HexColor(RULE))
            self.setLineWidth(0.4)
            self.line(18 * mm, A4[1] - 13 * mm, A4[0] - 18 * mm, A4[1] - 13 * mm)

        def _draw_footer(self, total: int) -> None:
            self.setFont(BODY_FONT, 8)
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
            "r_title", parent=base["Title"], fontName=BODY_FONT_BOLD,
            fontSize=17, leading=21, textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT, spaceAfter=2),
        "cover_system": ParagraphStyle(
            "r_cover_system", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=8.2, leading=10.5, textColor=colors.white,
            spaceAfter=0),
        "cover_title": ParagraphStyle(
            "r_cover_title", parent=base["Title"], fontName=BODY_FONT_BOLD,
            fontSize=21, leading=23, textColor=colors.white,
            alignment=TA_LEFT, spaceAfter=0),
        "cover_label": ParagraphStyle(
            "r_cover_label", parent=base["Normal"], fontName=BODY_FONT_BOLD,
            fontSize=7.5, leading=10, textColor=colors.HexColor("#d1fae5")),
        "cover_case": ParagraphStyle(
            "r_cover_case", parent=base["Normal"], fontName=BODY_FONT_BOLD,
            fontSize=11, leading=14, textColor=colors.white),
        "cover_report": ParagraphStyle(
            "r_cover_report", parent=base["Normal"], fontName=BODY_FONT_BOLD,
            fontSize=8.5, leading=11, textColor=colors.white),
        "subtitle": ParagraphStyle(
            "r_subtitle", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=9.4, leading=13,
            textColor=colors.HexColor(MUTED)),
        "banner": ParagraphStyle(
            "r_banner", parent=base["Normal"], fontName=BODY_FONT_BOLD,
            fontSize=10, leading=14, alignment=TA_CENTER,
            textColor=colors.HexColor("#991b1b"),
            borderWidth=0.9, borderColor=colors.HexColor("#991b1b"),
            borderPadding=5),
        "h1": ParagraphStyle(
            "r_h1", parent=base["Heading1"], fontName=BODY_FONT_BOLD,
            fontSize=13.5, leading=18, textColor=colors.HexColor("#111827"),
            spaceBefore=0, spaceAfter=2),
        "h2": ParagraphStyle(
            "r_h2", parent=base["Heading2"], fontName=BODY_FONT_BOLD,
            fontSize=11.5, leading=15, textColor=colors.HexColor(ACCENT),
            spaceBefore=12, spaceAfter=4),
        "body": ParagraphStyle(
            "r_body", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=9.5, leading=13.5,
            textColor=colors.HexColor("#1f2937")),
        "table": ParagraphStyle(
            "r_table", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=8.4, leading=10.6,
            textColor=colors.HexColor("#1f2937"), splitLongWords=True),
        "compact_table": ParagraphStyle(
            "r_compact_table", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=7.6, leading=9,
            textColor=colors.HexColor("#1f2937"), splitLongWords=True),
        "bullet": ParagraphStyle(
            "r_bullet", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=9.5, leading=13.5,
            leftIndent=10, bulletIndent=2,
            textColor=colors.HexColor("#1f2937")),
        "mono": ParagraphStyle(
            "r_mono", parent=base["Normal"], fontName="Courier", fontSize=7.5,
            leading=10.5, textColor=colors.HexColor("#374151")),
        "h3": ParagraphStyle(
            "r_h3", parent=base["Heading3"], fontName=BODY_FONT_BOLD,
            fontSize=9.5, leading=13, textColor=colors.HexColor("#111827"),
            spaceBefore=6, spaceAfter=1),
        "caveat": ParagraphStyle(
            "r_caveat", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=8.5, leading=11.5,
            textColor=colors.HexColor("#374151"),
            backColor=colors.HexColor("#f8fafc"),
            borderWidth=0.6, borderColor=colors.HexColor(RULE),
            borderPadding=6, spaceBefore=4),
        "end": ParagraphStyle(
            "r_end", parent=base["Normal"], fontName=BODY_FONT,
            fontSize=8, leading=11,
            alignment=TA_CENTER, textColor=colors.HexColor(MUTED)),
    }

    def esc(value: Any) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    story: List[Any] = []

    # -------------------------------------------------------------- cover page
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph(HANDLING, styles["banner"]))
    story.append(Spacer(1, 10 * mm))
    cover_left = [
        Paragraph(SYSTEM_NAME.upper(), styles["cover_system"]),
        Spacer(1, 5 * mm),
        Paragraph("Digital Evidence<br/>Investigation Report", styles["cover_title"]),
        Spacer(1, 4 * mm),
        Paragraph("EVIDENCE EXAMINATION  |  CORRELATION  |  CHRONOLOGY", styles["cover_label"]),
    ]
    cover_right = [
        Paragraph("CASE FILE", styles["cover_label"]),
        Spacer(1, 4 * mm),
        Paragraph(esc(case_id), styles["cover_case"]),
        Spacer(1, 10 * mm),
        Paragraph("REPORT", styles["cover_label"]),
        Paragraph(esc(report_id), styles["cover_report"]),
    ]
    cover = Table([[cover_left, cover_right]], colWidths=[119 * mm, 55 * mm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(COVER_DARK)),
        ("LINEBEFORE", (1, 0), (1, 0), 1.2, colors.HexColor(COVER_GOLD)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(ACCENT)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 5 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * mm),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cover)
    story.append(Spacer(1, 8 * mm))

    # Document-control block: what this document is, which case it belongs to,
    # and which revision the reader is holding.
    control_rows = [
        ["Case reference", case_id],
        ["Report reference", report_id],
        ["Report version", f"v{report_version}"],
        ["Date of issue (UTC)", generated_at[:19].replace("T", " ")],
        ["Status", "Automated analytical draft - investigator review required"],
        ["Prepared by", f"{ISSUING_BODY}, automated analysis pipeline"],
        ["Handling", HANDLING.title()],
    ]
    control = Table(control_rows, colWidths=[45 * mm, 129 * mm])
    control.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), BODY_FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), BODY_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(MUTED)),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdf4")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(RULE)),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor(RULE)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(control)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        "<b>Basis of this report.</b> Every statement is templated over a "
        "stored forensic finding; the generator has no free-text capability. "
        "The accuracy of those findings still depends on source quality and "
        "upstream extraction, and requires investigator review. Where an "
        "input was unavailable the report says so explicitly. The report-control "
        "section records an evidence-set digest; the full source-artifact hash "
        "register remains in the stored JSON companion.",
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
        "toc0", fontName=BODY_FONT, fontSize=10, leading=16,
        leftIndent=0, firstLineIndent=0,
        textColor=colors.HexColor("#1f2937"))]
    story.append(toc)
    story.append(PageBreak())

    # ------------------------------------------------------------ table helper
    def data_table(headers: List[str], rows: List[List[str]],
                   widths: Optional[List[float]] = None,
                   *, compact: bool = False) -> Table:
        cell_style = styles["compact_table"] if compact else styles["table"]
        vertical_padding = 2 if compact else 3
        wrapped = [[Paragraph(f"<b>{esc(h)}</b>", cell_style)
                    for h in headers]]
        for row in rows:
            wrapped.append([Paragraph(esc(cell), cell_style)
                            for cell in row])
        table = Table(wrapped, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0fdf4")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor(RULE)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), vertical_padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), vertical_padding),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return table

    def paired_metrics(entries: List[List[str]]) -> Table:
        """Lay summary measures across the page instead of down a long list."""
        rows: List[List[str]] = []
        for index in range(0, len(entries), 2):
            left = entries[index]
            right = entries[index + 1] if index + 1 < len(entries) else ["", ""]
            rows.append([left[0], left[1], right[0], right[1]])
        return data_table(
            ["Measure", "Result", "Measure", "Result"],
            rows,
            widths=[49 * mm, 31 * mm, 49 * mm, 32 * mm],
        )

    # ------------------------------------------------- generic value rendering
    def emit(value: Any, indent: int = 0) -> None:
        pad = "&nbsp;" * (indent * 4)
        if value is None:
            story.append(Paragraph(f"{pad}&bull; not available",
                                   styles["bullet"]))
        elif isinstance(value, str):
            style = styles["body"] if indent == 0 else styles["bullet"]
            prefix = "" if indent == 0 else f"{pad}&bull; "
            story.append(Paragraph(prefix + esc(value), style))
        elif isinstance(value, (int, float, bool)):
            story.append(Paragraph(f"{pad}&bull; {esc(value)}",
                                   styles["bullet"]))
        elif isinstance(value, list):
            if not value:
                story.append(Paragraph(f"{pad}&bull; none", styles["bullet"]))
            for item in value:
                if isinstance(item, (dict, list)):
                    emit(item, indent)
                else:
                    story.append(Paragraph(f"{pad}&bull; {esc(item)}",
                                           styles["bullet"]))
        elif isinstance(value, dict):
            for key, item in value.items():
                label = esc(str(key).replace("_", " "))
                if isinstance(item, (dict, list)):
                    story.append(Paragraph(f"{pad}&bull; <b>{label}</b>:",
                                           styles["bullet"]))
                    emit(item, indent + 1)
                else:
                    story.append(Paragraph(
                        f"{pad}&bull; <b>{label}</b>: {esc(item)}",
                        styles["bullet"]))
        else:
            story.append(Paragraph(f"{pad}&bull; {esc(value)}",
                                   styles["bullet"]))

    # ----------------------------------------------- specialised section views
    def emit_numbered_table(
        section: Any, label: str, *, compact: bool = False,
        full_width: bool = False,
    ) -> bool:
        if not isinstance(section, list):
            return False
        story.append(data_table(
            ["#", label],
            [[str(index), str(item)] for index, item in enumerate(section, start=1)],
            widths=[12 * mm, (162 if full_width else 149) * mm],
            compact=compact,
        ))
        return True

    def emit_case_overview(section: Any) -> bool:
        if not isinstance(section, dict) or "case_id" not in section:
            return False
        story.append(data_table(
            ["Case field", "Recorded value"],
            [[str(key).replace("_", " ").title(), value]
             for key, value in section.items()],
            widths=[47 * mm, 114 * mm],
        ))
        return True

    def emit_scope_table(section: Any) -> bool:
        if not isinstance(section, dict) or "methodology" not in section:
            return False
        story.append(Paragraph(
            "How this report was produced. Every figure in the sections above "
            "is read back out of the stored outputs named below - none of it is "
            "written by hand and none of it is free-text generated, so the same "
            "evidence re-analysed yields the same report.",
            styles["body"],
        ))
        story.append(Spacer(1, 4))
        story.append(data_table(
            ["Scope", "Recorded basis"],
            [["What this run set out to do",
              section.get("objective", "not available")],
             ["What it covered",
              section.get("evidence_scope", "not available")],
             ["Repeatability",
              section.get("reproducibility", "not available")]],
            widths=[40 * mm, 121 * mm],
        ))
        # Each stage is stored as "Phase 1 - Acquisition & OCR: <what it did>".
        # Numbering the rows and lifting the phase out of the sentence shows
        # the pipeline order that the prose only implied.
        methods = []
        for index, method in enumerate(section.get("methodology") or [], start=1):
            stage, separator, detail = str(method).partition(":")
            phased = re.match(r"^Phase\s+(\d+)\s*-\s*(.*)$", stage.strip(), re.I)
            if phased:
                stage = f"{phased.group(2).strip()} (Phase {phased.group(1)})"
            text = (detail.strip() if separator else str(method)).strip()
            # The engine writes the stage as one sentence, so the half after
            # the colon starts lowercase. In its own column it reads as a
            # fragment, so only the first letter is lifted - acronyms such as
            # "metadata/EXIF" and the wording itself are left alone.
            if text[:1].islower():
                text = text[0].upper() + text[1:]
            methods.append([str(index), stage.strip(), text])
        if methods:
            story.append(Spacer(1, 5))
            story.append(Paragraph(
                "Processing stages, in the order they ran", styles["h3"]))
            story.append(Paragraph(
                "Each stage reads the previous stage's stored output, so a "
                "failure anywhere upstream is visible rather than silently "
                "filled in.", styles["subtitle"]))
            story.append(Spacer(1, 3))
            story.append(data_table(
                ["#", "Stage", "What it did, and where the output is stored"],
                methods,
                widths=[8 * mm, 45 * mm, 108 * mm],
            ))
        return True

    def emit_metadata_table(section: Any) -> bool:
        if not (isinstance(section, list) and section
                and isinstance(section[0], dict) and "evidence_id" in section[0]):
            return False
        story.append(data_table(
            ["Evidence", "EXIF", "Device", "Software", "Consistency notes"],
            [[row.get("evidence_id", ""),
              "yes" if row.get("has_exif") else "no",
              row.get("device", ""), row.get("software", ""),
              ", ".join(row.get("consistency_notes") or [])]
             for row in section],
            widths=[28 * mm, 14 * mm, 36 * mm, 36 * mm, 47 * mm],
        ))
        return True

    def emit_confidence_table(section: Any) -> bool:
        if not (isinstance(section, list) and section
                and isinstance(section[0], dict) and "evidence_id" in section[0]):
            return False
        story.append(data_table(
            ["Evidence", "Score", "Level", "Computed explanation"],
            [[row.get("evidence_id", ""), row.get("score", ""),
              row.get("level", ""), row.get("explanation", "")]
             for row in section],
            widths=[30 * mm, 17 * mm, 24 * mm, 90 * mm],
        ))
        return True

    def emit_evidence_table(rows: Any) -> bool:
        if not (isinstance(rows, list) and rows
                and isinstance(rows[0], dict) and "evidence_id" in rows[0]):
            return False
        story.append(data_table(
            ["Evidence", "File", "Acquired (UTC)", "OCR", "Evidence confidence", "Entities", "Integrity"],
            [[r.get("evidence_id", ""), r.get("file_name", ""),
              str(r.get("upload_time", ""))[:19].replace("T", " "),
              (f"{float(r.get('ocr_confidence') or 0) * 100:.0f}%"
               if r.get("ocr_confidence") is not None else "n/a"),
              (f"{float(r.get('evidence_confidence_score')):.1f}/100"
               if isinstance(r.get("evidence_confidence_score"), (int, float))
               else "n/a"),
              str(r.get("entity_count", 0)),
              "VERIFIED" if r.get("hash_verified") else "FAILED"]
             for r in rows],
            widths=[23 * mm, 37 * mm, 29 * mm, 12 * mm, 25 * mm, 13 * mm, 22 * mm],
            compact=True,
        ))
        story.append(Spacer(1, 3))
        story.append(Paragraph(
            "Integrity means the stored file matched its recorded SHA-256 "
            "digest at verification time; it does not establish that the "
            "content itself is true. Full item digests remain in the stored "
            "machine-readable evidence register.", styles["subtitle"]))
        return True

    def emit_timeline_table(section: Any) -> bool:
        """Separate incident chronology from evidence-intake provenance."""
        if not isinstance(section, dict) or "chronological_events" not in section:
            return False

        quality = section.get("timestamp_quality") or {}
        event_count = int(quality.get("event_count", 0))
        acquisition_count = int(quality.get("acquisition_fallback_count", 0))
        unresolved_count = int(quality.get("unresolved_count", 0))
        event_time_count = max(0, event_count - acquisition_count - unresolved_count)
        inferred_event_count = max(
            0, int(quality.get("inferred_count", 0)) - acquisition_count
        )
        recorded_event_count = max(0, event_time_count - inferred_event_count)
        story.append(data_table(
            ["Records", "Event time", "Recorded", "Inferred", "Acquisition", "Unresolved"],
            [[
                str(event_count),
                str(event_time_count),
                str(recorded_event_count),
                str(inferred_event_count),
                str(acquisition_count),
                str(unresolved_count),
            ]],
            widths=[25 * mm, 27 * mm, 27 * mm, 27 * mm, 30 * mm, 25 * mm],
        ))
        story.append(Spacer(1, 5))

        if quality.get("reliability_note"):
            story.append(Paragraph(
                esc(quality["reliability_note"]), styles["caveat"]
            ))
            story.append(Spacer(1, 5))

        all_rows = section.get("chronological_events") or []
        event_rows = section.get("event_time_events")
        if event_rows is None:
            event_rows = [
                row for row in all_rows
                if row.get("timestamp") not in ("", "unresolved")
                and row.get("timestamp_source") != "upload_time_fallback"
            ]
        acquisition_rows = section.get("acquisition_records")
        if acquisition_rows is None:
            acquisition_rows = [
                row for row in all_rows
                if row.get("timestamp_source") == "upload_time_fallback"
            ]
        unresolved_rows = section.get("unresolved_records")
        if unresolved_rows is None:
            unresolved_rows = [
                row for row in all_rows
                if row.get("timestamp") in ("", "unresolved")
            ]

        story.append(Paragraph("Incident events", styles["h3"]))
        if event_rows:
            story.append(data_table(
                ["Event time (UTC)", "Evidence", "Finding", "Time basis"],
                [[
                    str(row.get("timestamp", "unresolved"))[:19].replace("T", " "),
                    row.get("evidence_id", ""),
                    row.get("description") or row.get("file_name", ""),
                    (
                        ("Inferred" if row.get("timestamp_inferred") else "Recorded")
                        + " - "
                        + str(row.get("timestamp_confidence", "unknown"))
                        + " confidence; "
                        + str(row.get("timestamp_source", "")).replace("_", " ")
                    ),
                ] for row in event_rows],
                widths=[33 * mm, 26 * mm, 67 * mm, 35 * mm],
            ))
        else:
            story.append(Paragraph(
                "No evidence-derived event time was available. The report does "
                "not infer an incident sequence from upload activity.",
                styles["caveat"],
            ))

        if acquisition_rows:
            story.append(Spacer(1, 7))
            story.append(Paragraph(
                "Evidence acquisition records - not incident events", styles["h3"]))
            story.append(Paragraph(
                "These times record when CIIS received an exhibit. They are "
                "retained for provenance and excluded from attack duration and "
                "stage ordering.", styles["subtitle"]))
            story.append(Spacer(1, 3))
            story.append(data_table(
                ["Acquired (UTC)", "Evidence", "File"],
                [[
                    str(row.get("timestamp", ""))[:19].replace("T", " "),
                    row.get("evidence_id", ""),
                    row.get("file_name", ""),
                ] for row in acquisition_rows],
                widths=[42 * mm, 31 * mm, 88 * mm],
            ))

        if unresolved_rows:
            story.append(Spacer(1, 7))
            story.append(Paragraph("Records requiring timestamp review", styles["h3"]))
            story.append(data_table(
                ["Evidence", "File", "Status"],
                [[row.get("evidence_id", ""), row.get("file_name", ""),
                  "No usable event or acquisition timestamp"]
                 for row in unresolved_rows],
                widths=[31 * mm, 70 * mm, 60 * mm],
            ))

        story.append(Spacer(1, 7))
        order = section.get("stage_progression") or []
        story.append(Paragraph("Attack-stage assessment", styles["h3"]))
        if section.get("progression_assessable") and order:
            story.append(Paragraph(
                "<b>Observed order:</b> " + esc(" -> ".join(order)),
                styles["body"],
            ))
            story.append(Paragraph(
                "<b>Matches configured reference sequence:</b> "
                + ("yes" if section.get("progression_consistent") else "no"),
                styles["subtitle"],
            ))
        else:
            story.append(Paragraph(
                "The evidence supports stage labels, but the full stage order "
                "cannot be established because one or more stage-bearing items "
                "has acquisition time only. Stage labels must not be read as a "
                "complete chronological sequence.",
                styles["caveat"],
            ))

        critical = [
            event for event in (section.get("critical_events") or [])
            if event.get("timestamp_source") != "upload_time_fallback"
        ]
        if critical:
            story.append(Spacer(1, 7))
            story.append(Paragraph("Priority event review", styles["h3"]))
            story.append(data_table(
                ["Evidence", "Recorded time", "Recorded evidential signals"],
                [[
                    event.get("evidence_id", "unknown"),
                    str(event.get("timestamp", "unresolved"))[:19].replace("T", " "),
                    _signal_summary(event.get("reasons")),
                ] for event in critical],
                widths=[29 * mm, 38 * mm, 94 * mm],
            ))
        return True

    def emit_correlation_table(section: Any) -> bool:
        """Correlated pairs, one block each with its factors itemised.

        The flat table this replaced had to squeeze the whole explanation
        paragraph into a 79mm column, so it was truncated at 145 characters and
        the later factors of a strong pair were simply cut off the page. Giving
        each pair its own factor table prints all of them, and puts the
        arithmetic - each factor's points, their total, the resulting
        confidence - where the reader can follow it.
        """
        if not isinstance(section, dict) or "top_relationships" not in section:
            return False
        story.append(Paragraph(
            f"{section.get('related_pair_count', 0)} of "
            f"{section.get('pair_count', 0)} analysed pairs met a configured "
            "relationship threshold. Association is not causation or identity.",
            styles["caveat"],
        ))
        rows = section.get("top_relationships") or []
        if not rows:
            return True

        structured = [row for row in rows if row.get("factors")]
        if not structured:
            # Reports stored before the factors were carried through.
            story.append(Spacer(1, 5))
            story.append(data_table(
                ["Evidence pair", "Strength", "Confidence", "Computed basis"],
                [[
                    row.get("pair", ""),
                    str(row.get("strength", "")).replace("_", " ").title(),
                    f"{float(row.get('confidence') or 0):.2f}",
                    _relationship_basis(row.get("explanation", "")),
                ] for row in rows],
                widths=[35 * mm, 29 * mm, 18 * mm, 79 * mm],
            ))
            return True

        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "How to read these: each factor below is worth points - how "
            "identifying that kind of match is, multiplied by how rare the "
            "shared values are across all evidence held. The points add up to "
            "the pair's total weight, and the confidence is that total on a "
            "saturating scale, so several independent factors raise confidence "
            "while no single one reaches certainty alone.",
            styles["body"],
        ))
        story.append(Spacer(1, 4))

        for row in rows:
            factors = row.get("factors") or []
            confidence = float(row.get("confidence") or 0)
            weight = row.get("weight")
            heading = (
                f"{esc(row.get('pair', ''))} &ndash; "
                f"{esc(str(row.get('strength', '')).replace('_', ' ').title())}"
            )
            measures = f"Confidence {confidence:.2f}"
            if weight is not None:
                measures = (f"Total weight {float(weight):.2f} "
                            f"&rarr; confidence {confidence:.2f}")
            if factors:
                measures += f" &nbsp;|&nbsp; {len(factors)} independent factor(s)"

            block: List[Any] = [
                Paragraph(heading, styles["h3"]),
                Paragraph(measures, styles["subtitle"]),
                Spacer(1, 3),
            ]
            if factors:
                block.append(data_table(
                    ["Factor", "Points", "What matched"],
                    [[
                        str(factor.get("label", "")).title(),
                        f"{float(factor.get('contribution') or 0):.2f}",
                        _short(str(factor.get("detail", "")), 150),
                    ] for factor in factors],
                    widths=[34 * mm, 16 * mm, 111 * mm],
                    compact=True,
                ))
            else:
                block.append(Paragraph(
                    esc(_relationship_basis(row.get("explanation", ""), 400)),
                    styles["body"]))
            block.append(Spacer(1, 7))
            # A pair split across a page break reads as two half-findings.
            story.append(KeepTogether(block))
        return True

    def emit_cross_case_table(section: Any) -> bool:
        if not isinstance(section, dict) or "links" not in section:
            return False
        story.append(Paragraph(
            "Automated shared-entity associations require independent "
            "corroboration; common identifiers can link unrelated parties.",
            styles["caveat"],
        ))
        rows = []
        for link in section.get("links") or []:
            matches = link.get("matched_entities") or []
            indicators = [
                f"{match.get('entity_type', '')}:{match.get('value', '')}"
                for match in matches[:4]
            ]
            if len(matches) > 4:
                indicators.append(f"+{len(matches) - 4} more")
            rows.append([
                link.get("other_case_id", ""),
                (
                    str(link.get("relationship_strength", "")).replace("_", " ").title()
                    + " - "
                    + f"{float(link.get('match_confidence') or 0):.2f}"
                ),
                ", ".join(indicators),
            ])
        if rows:
            story.append(Spacer(1, 5))
            story.append(data_table(
                ["Other case", "Rating", "Key matched indicators"],
                rows,
                widths=[37 * mm, 32 * mm, 92 * mm],
            ))
        else:
            story.append(Paragraph("No cross-case associations found.", styles["body"]))
        return True

    def emit_campaign_table(section: Any) -> bool:
        if not isinstance(section, dict) or "campaigns" not in section:
            return False
        story.append(Paragraph(
            "Clusters are candidate groupings produced by configured thresholds; "
            "they do not by themselves establish coordination.",
            styles["caveat"],
        ))
        campaigns = section.get("campaigns") or []
        if campaigns:
            story.append(Spacer(1, 5))
            story.append(data_table(
                ["Candidate cluster", "Evidence", "Conf.", "Shared signature"],
                [[
                    campaign.get("campaign_id", ""),
                    ", ".join(campaign.get("members") or []),
                    f"{float(campaign.get('confidence') or 0):.2f}",
                    ", ".join((campaign.get("signature") or [])[:5]),
                ] for campaign in campaigns],
                widths=[43 * mm, 42 * mm, 16 * mm, 60 * mm],
            ))
        unclustered = section.get("unclustered_evidence") or []
        if unclustered:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                "<b>Unclustered evidence:</b> " + esc(", ".join(unclustered)),
                styles["subtitle"],
            ))
        return True

    def emit_suspect_table(section: Any) -> bool:
        if not (isinstance(section, list) and section
                and isinstance(section[0], dict) and "identity" in section[0]):
            return False
        block = [
            Spacer(1, 7),
            Paragraph("Identity leads", styles["h3"]),
            Paragraph(
                "Identity anchors are investigative leads, not legal attribution. "
                "Verify ownership and role using original exhibits and independent "
                "records. The four highest-ranked leads are shown; the complete "
                "ranked list remains in the stored JSON and frontend.",
                styles["caveat"],
            ),
            Spacer(1, 5),
            data_table(
                ["Identity lead", "Score", "Confidence", "Risk", "Supporting evidence"],
                [[
                    row.get("identity", ""),
                    str(row.get("confidence_score", "")),
                    row.get("confidence_level", ""),
                    row.get("risk_level", ""),
                    ", ".join(row.get("evidence_ids") or []),
                ] for row in section[:4]],
                widths=[46 * mm, 16 * mm, 24 * mm, 18 * mm, 57 * mm],
            ),
        ]
        story.append(KeepTogether(block))
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
        # The table gives the verdict; one compact basis table records why each
        # flagged indicator was rated. Benign indicators need no expanded row.
        flagged_basis = []
        for row in rows:
            if str(row.get("verdict", "")).lower() not in ("malicious", "suspicious",
                                                           "phishing"):
                continue
            facts = _prediction_facts(row)
            reasons = [str(r) for r in (row.get("reasons") or []) if str(r).strip()]
            if not facts and not reasons:
                continue
            basis = facts + reasons
            flagged_basis.append([
                row.get("indicator", ""),
                _short("; ".join(basis), 280),
            ])
        if flagged_basis:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Flagged-indicator basis", styles["h3"]))
            story.append(data_table(
                ["Indicator", "Recorded basis"],
                flagged_basis,
                widths=[52 * mm, 109 * mm],
                compact=True,
            ))
        return True

    def emit_legal_basis(section: Any) -> bool:
        """Statutory basis: each provision as a titled block, not a bullet dump.

        The distinction between one section of the Act and the next is the whole
        point of this part of the report, so it gets headings and a boxed
        caveat rather than the generic key/value rendering.
        """
        if not isinstance(section, dict) or "provisions" not in section:
            return False

        provisions = section.get("provisions") or []
        story.append(Paragraph("What this section is", styles["h3"]))
        story.append(Paragraph(
            f"Provisions the automated findings <i>touch</i> - offences whose "
            f"description matches what the evidence shows. Screening identified "
            f"{len(provisions)} candidate provision(s): this is a shortlist for "
            "investigator and legal review, not a charge and not a finding that "
            "every element of an offence is made out.",
            styles["body"],
        ))
        if section.get("caveat"):
            story.append(Paragraph(esc(section["caveat"]), styles["caveat"]))
        story.append(Spacer(1, 5))
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

        for provision in provisions:
            block: List[Any] = [
                Paragraph(
                    f"Candidate section {esc(provision['section'])} &ndash; "
                    f"{esc(provision['title'])}", styles["h3"]),
                Paragraph(esc(provision["citation"]), styles["subtitle"]),
                Spacer(1, 3),
                # Three plain questions rather than field names: a reader
                # should be able to tell what the offence is, what in this
                # case pointed at it, and what it carries, without decoding
                # "basis" or "conduct" first.
                data_table(
                    ["What was assessed", "Recorded value"],
                    [["What the law covers", provision["conduct"]],
                     ["What in this case pointed here (not proof)",
                      provision["basis"]],
                     ["Maximum penalty on conviction", provision["penalty"]],
                     ["Evidence behind it", ", ".join(
                         provision.get("evidence_ids") or ["none"])]],
                    widths=[45 * mm, 116 * mm],
                ),
            ]
            block.append(Spacer(1, 8))
            # A provision split across a page break reads as two half-findings.
            story.append(KeepTogether(block))

        guidance = section.get("investigative_guidance") or []
        if guidance:
            story.append(Paragraph(
                "Evidentiary and regulatory follow-up", styles["h3"]))
            story.append(Paragraph(
                "Records to preserve and parties to approach while they still "
                "hold the data - not findings that any institution broke a "
                "rule.", styles["subtitle"]))
            story.append(Spacer(1, 5))
            for item in guidance:
                block = [
                    Paragraph(esc(item["title"]), styles["h3"]),
                    Paragraph(esc(item["citation"]), styles["subtitle"]),
                    Spacer(1, 3),
                    data_table(
                        ["What was assessed", "Recorded value"],
                        [["Status", item.get("status", "investigative_follow_up")],
                         ["What the rule expects", item["expectation"]],
                         ["Why it applies here", item["basis"]],
                         ["What to do about it", item["recommended_action"]],
                         ["Who it binds", item["applicability"]],
                         ["Evidence behind it", ", ".join(
                             item.get("evidence_ids") or ["none"])]],
                        widths=[45 * mm, 116 * mm],
                    ),
                ]
                block.append(Spacer(1, 7))
                story.append(KeepTogether(block))

        manual = section.get("manual_review_provisions") or []
        if manual:
            story.append(Paragraph(
                "Provisions requiring manual review", styles["h3"]))
            story.append(Paragraph(
                "The current evidence model does not automatically assess these "
                "provisions:", styles["subtitle"]))
            for item in manual:
                story.append(Paragraph(
                    f"&bull; <b>Section {esc(item['section'])} - "
                    f"{esc(item['title'])}.</b> {esc(item['reason'])}",
                    styles["subtitle"],
                ))
            story.append(Spacer(1, 6))

        sources = section.get("sources") or []
        if sources:
            story.append(Paragraph("Primary sources", styles["h3"]))
            for source in sources:
                source_line = (
                    f"<b>{esc(source['authority'])} - {esc(source['title'])}.</b> "
                    f"{esc(source['url'])} Used for: {esc(source['usage'])}"
                )
                if source.get("note"):
                    source_line += f" Note: {esc(source['note'])}"
                story.append(Paragraph(source_line, styles["subtitle"]))
            story.append(Spacer(1, 4))

        return True

    # ------------------------------------------------------------- body build
    #
    # Sections are numbered so the report can be cited precisely — "see 6.2"
    # is how an investigator, a prosecutor or a defence expert refers to a
    # finding, and an unnumbered document cannot be cross-referenced at all.
    # The JSON retains the complete module-by-module section contract. The PDF
    # is an investigator brief: related outputs are grouped around decisions,
    # with raw diagnostic detail left in the machine-readable twin.
    number = 0
    figure_number = 0

    def major(title: str, *, new_page: bool = True) -> None:
        nonlocal number
        if new_page:
            story.append(PageBreak())
            story.append(Spacer(1, 3 * mm))
        number += 1
        heading = Paragraph(f"{number}. {title}", styles["h2"])
        heading._toc_level = 0
        story.append(heading)

    def subheading(title: str) -> None:
        story.append(Spacer(1, 7))
        story.append(Paragraph(title, styles["h3"]))

    def figure(drawing: Any, caption: str) -> None:
        """Append a chart with a numbered caption.

        Figures restate numbers the tables already carry; they are here so the
        shape of a case - where its evidence clusters, how its links are
        distributed - can be taken in at a glance. Nothing is presented only
        as a picture, so a greyscale print or a screen reader loses no
        finding. A figure that has no data to plot is skipped by its caller.
        """
        nonlocal figure_number
        if drawing is None:
            return
        figure_number += 1
        story.append(KeepTogether([
            Spacer(1, 4),
            drawing,
            Paragraph(f"Figure {figure_number}. {_esc(caption)}",
                      _figure_caption_style(styles)),
            Spacer(1, 4),
        ]))

    def metric_text(key: str, value: Any) -> str:
        if value in (None, ""):
            return "not available"
        if key == "mean_ocr_confidence" and isinstance(value, (int, float)):
            return f"{float(value) * 100:.0f}%"
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return str(value)

    # ---------------------------------------------------------- executive brief
    major(PDF_SECTION_TITLES[0], new_page=False)
    story.append(Paragraph(
        "Purpose: present the material findings, their evidential limits, and "
        "the actions requiring investigator review. Detailed computed outputs "
        "remain available in the accompanying JSON artifact.",
        styles["caveat"],
    ))
    subheading("Case at a glance")
    overview = sections.get("case_overview") or {}
    quality = sections.get("evidence_quality_summary") or {}
    timeline_section = sections.get("timeline_analysis") or {}
    timestamp_quality = (
        timeline_section.get("timestamp_quality") or {}
        if isinstance(timeline_section, dict) else {}
    )
    correlation = sections.get("correlation_analysis") or {}
    cross_case = sections.get("cross_case_correlation") or {}
    evidence_count = int(overview.get("evidence_count", 0) or 0)
    verified = int(quality.get("hash_verified_count", 0) or 0)
    event_time_count = (
        int(timestamp_quality.get("event_count", 0) or 0)
        - int(timestamp_quality.get("acquisition_fallback_count", 0) or 0)
        - int(timestamp_quality.get("unresolved_count", 0) or 0)
    )
    story.append(data_table(
        ["Measure", "Recorded value", "Measure", "Recorded value"],
        [
            ["Case", overview.get("case_id", case_id),
             "Evidence items", str(evidence_count)],
            ["Integrity verified", f"{verified}/{evidence_count}",
             "Evidence-derived event times", str(max(0, event_time_count))],
            ["Related evidence pairs",
             str(correlation.get("related_pair_count", "not available"))
             if isinstance(correlation, dict) else "not available",
             "Candidate linked cases",
             str(cross_case.get("related_case_count", 0))
             if isinstance(cross_case, dict) else "not available"],
        ],
        widths=[34 * mm, 47 * mm, 40 * mm, 40 * mm],
    ))
    statistics = sections.get("investigation_statistics")
    entity_stats = (
        statistics.get("entity_statistics") if isinstance(statistics, dict) else None
    )
    if isinstance(entity_stats, dict) and entity_stats:
        ranked = sorted(
            ((str(k).replace("_", " "), v) for k, v in entity_stats.items()),
            key=lambda item: item[1] if isinstance(item[1], (int, float)) else 0,
            reverse=True,
        )
        figure(
            _bar_figure(ranked, width=174 * mm, value_label="identifiers extracted"),
            "Identifier types recovered from this case's evidence, most "
            "frequent first. Counts are occurrences, not distinct values.",
        )

    subheading("Material findings")
    executive_findings = list(sections.get("executive_summary") or [])
    if (
        isinstance(timeline_section, dict)
        and not timeline_section.get("progression_assessable", False)
    ):
        executive_findings = [
            (
                "Evidence-timed stage order is incomplete because one or more "
                "detected stages has acquisition time only "
                "[timeline_analysis.json]."
                if str(finding).startswith("Keyword-derived stage order:")
                else finding
            )
            for finding in executive_findings
        ]
    emit_numbered_table(executive_findings, "Finding")
    recommendations = sections.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        subheading("Immediate review queue")
        emit_numbered_table(recommendations[:4], "Action")

    # ---------------------------------------------------- evidence and integrity
    major(PDF_SECTION_TITLES[1])
    evidence_rows = sections.get("evidence_summary")
    evidence_rows = evidence_rows if isinstance(evidence_rows, list) else []
    emit_evidence_table(sections.get("evidence_summary"))

    subheading("Quality indicators")
    if isinstance(quality, dict):
        quality_labels = {
            "hash_verified_count": "Hash-verified items",
            "mean_evidence_confidence": "Mean evidence confidence",
            "mean_ocr_confidence": "Mean OCR confidence",
            "mean_image_quality": "Mean image quality",
            "mean_forgery_score": "Mean forgery indicator score",
            "max_forgery_score": "Maximum forgery indicator score",
        }
        story.append(paired_metrics([
            [quality_labels.get(key, key.replace("_", " ").title()),
             metric_text(key, value)]
            for key, value in quality.items()
            if key in quality_labels
        ]))

    confidence = sections.get("confidence_analysis")
    if isinstance(confidence, list) and confidence and "evidence_id" in confidence[0]:
        scores = [
            (row.get("evidence_id", ""), float(row["score"]))
            for row in confidence
            if isinstance(row.get("score"), (int, float))
        ]
        if scores:
            # The chart can only show items Phase 1 actually scored, which is
            # often fewer than the case holds. Saying "each evidence item"
            # while plotting three of eleven misrepresents the coverage, so
            # the caption states both figures.
            plotted = min(len(scores), 12)
            coverage = (
                f"{plotted} of {len(evidence_rows)} evidence item(s)"
                if evidence_rows else f"{plotted} evidence item(s)"
            )
            figure(
                _bar_figure(
                    sorted(scores, key=lambda item: item[1]),
                    width=174 * mm,
                    value_label="confidence score (0-100)",
                    max_bars=12,
                ),
                f"Phase-1 confidence, weakest first, for the {coverage} the "
                "confidence module scored. The weakest are the ones to "
                "corroborate before relying on them.",
            )
        levels: Dict[str, int] = {}
        for row in confidence:
            label = str(row.get("level", "not available")).replace("_", " ").title()
            levels[label] = levels.get(label, 0) + 1
        if scores:
            lowest = min(scores, key=lambda item: item[1])
            highest = max(scores, key=lambda item: item[1])
            subheading("Evidence-confidence profile")
            story.append(paired_metrics([
                ["Items assessed", str(len(confidence))],
                ["Mean score", f"{sum(score for _, score in scores) / len(scores):.1f}/100"],
                ["Lowest score", f"{lowest[1]:.1f}/100 ({lowest[0]})"],
                ["Highest score", f"{highest[1]:.1f}/100 ({highest[0]})"],
                ["Level distribution", ", ".join(f"{name}: {count}" for name, count in levels.items())],
                ["Use", "Prioritisation aid; not proof of authenticity"],
            ]))

    metadata = sections.get("metadata_summary")
    if isinstance(metadata, list) and metadata and "evidence_id" in metadata[0]:
        subheading("Metadata observations")
        with_exif = sum(1 for row in metadata if row.get("has_exif"))
        exceptions = []
        for row in metadata:
            notes = [
                str(note) for note in (row.get("consistency_notes") or [])
                if str(note).strip()
                and "no EXIF metadata" not in str(note)
                and str(note).strip().lower() != "none"
            ]
            if row.get("device") or row.get("software") or notes:
                exceptions.append([
                    row.get("evidence_id", ""),
                    row.get("device", "") or "not recorded",
                    row.get("software", "") or "not recorded",
                    "; ".join(notes) or "none",
                ])
        story.append(data_table(
            ["Items reviewed", "EXIF present", "EXIF absent", "Recorded exceptions"],
            [[str(len(metadata)), str(with_exif), str(len(metadata) - with_exif), str(len(exceptions))]],
            widths=[40 * mm, 40 * mm, 40 * mm, 41 * mm],
        ))
        story.append(Spacer(1, 3))
        story.append(Paragraph(
            "Missing EXIF is common for screenshots and messaging exports; it "
            "is recorded as reduced provenance coverage, not treated as proof "
            "of manipulation.", styles["subtitle"]
        ))
        if exceptions:
            story.append(Spacer(1, 4))
            story.append(data_table(
                ["Evidence", "Device", "Software", "Exception or note"],
                exceptions,
                widths=[29 * mm, 35 * mm, 38 * mm, 59 * mm],
            ))

    # ------------------------------------------------------------- chronology
    major(PDF_SECTION_TITLES[2])
    emit_timeline_table(sections.get("timeline_analysis"))

    # ------------------------------------------------------ analytical findings
    major(PDF_SECTION_TITLES[3])
    subheading("Evidence relationships")
    correlation_section = sections.get("correlation_analysis")
    if not emit_correlation_table(correlation_section):
        emit(correlation_section)
    if isinstance(correlation_section, dict):
        distribution = correlation_section.get("strength_distribution")
        if isinstance(distribution, dict) and distribution:
            figure(
                _pie_figure(
                    sorted(distribution.items(), key=lambda kv: -kv[1]),
                    width=174 * mm,
                ),
                "Distribution of the examined evidence pairs by relationship "
                "strength. NO_RELATIONSHIP pairs were examined and rejected.",
            )

    subheading("Cross-case candidates")
    if not emit_cross_case_table(sections.get("cross_case_correlation")):
        emit(sections.get("cross_case_correlation"))

    subheading("Candidate campaign grouping")
    if not emit_campaign_table(sections.get("campaign_analysis")):
        emit(sections.get("campaign_analysis"))

    if not emit_suspect_table(sections.get("suspect_assessment")):
        subheading("Identity leads")
        emit(sections.get("suspect_assessment"))

    subheading("Threat-indicator assessment")
    threat = sections.get("threat_intelligence_summary")
    if isinstance(threat, dict):
        threat_labels = {
            "indicators_checked": "Indicators checked",
            "malicious_indicators": "Malicious",
            "suspicious_indicators": "Suspicious",
            "benign_indicators": "Benign",
            "evidence_with_threats": "Evidence items with flagged indicators",
        }
        story.append(paired_metrics([
            [threat_labels[key], metric_text(key, threat.get(key))]
            for key in threat_labels if key in threat
        ]))
        story.append(Spacer(1, 5))
    if not emit_predictions_table(sections.get("model_predictions")):
        emit(sections.get("model_predictions"))

    # -------------------------------------------------------- legal screening
    major(PDF_SECTION_TITLES[4])
    if not emit_legal_basis(sections.get("legal_basis")):
        emit(sections.get("legal_basis"))

    # ------------------------------------------------------------- action plan
    major(PDF_SECTION_TITLES[5])
    story.append(Paragraph(
        "Actions are sequenced for operational review. Provider requests must "
        "use identifiers verified against the original exhibits.",
        styles["caveat"],
    ))
    story.append(Spacer(1, 4 * mm))
    if not emit_numbered_table(recommendations, "Action", full_width=True):
        emit(recommendations)

    # ---------------------------------------------- method, limits, conclusion
    major(PDF_SECTION_TITLES[6])
    subheading("Scope and reproducible method")
    if not emit_scope_table(sections.get("scope_and_methodology")):
        emit(sections.get("scope_and_methodology"))
    subheading("Interpretive boundaries")
    emit_numbered_table(
        sections.get("limitations"), "Review boundary", compact=True
    )
    subheading("Investigation conclusion")
    emit_numbered_table(
        sections.get("investigation_conclusion"), "Conclusion", compact=True
    )

    # ------------------------------------------ report control and certification
    # The machine-readable JSON retains the exhaustive artifact-hash register
    # and chain-of-custody data. The investigator-facing PDF carries only the
    # control values needed to identify and review this report; raw storage
    # paths and a duplicate appendix do not improve the evidential narrative.
    major(PDF_SECTION_TITLES[7])
    provenance = sections.get("report_provenance")
    if isinstance(provenance, dict):
        story.append(paired_metrics([
            ["Case reference", case_id],
            ["Report version", f"v{report_version}"],
            ["Report reference", provenance.get("report_id", report_id)],
            ["Generated (UTC)", str(provenance.get("generated_at", generated_at))[:19].replace("T", " ")],
        ]))
        story.append(Spacer(1, 6))
        story.append(data_table(
            ["Integrity control", "Recorded value"],
            [["Evidence-set SHA-256 digest",
              provenance.get("evidence_set_digest", "not available")],
             ["Digest basis",
              provenance.get("evidence_set_digest_note", "not available")]],
            widths=[45 * mm, 116 * mm],
            compact=True,
        ))
        hashes = provenance.get("source_artifact_hashes") or {}
        story.append(Paragraph(
            f"<b>Source controls:</b> {len(hashes)} contributing analysis "
            "artifact digest(s) are retained in the stored JSON report. "
            "This PDF intentionally omits raw storage paths and repetitive "
            "technical hash listings; the evidence register above records the "
            "item-level verification outcome used in the investigation.",
            styles["subtitle"],
        ))

    # -------------------------------------------------------------- signature
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
        ("FONTNAME", (0, 0), (-1, 0), BODY_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
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
        subject=f"Digital evidence investigation report {report_id} for case {case_id}",
    )
    # Two passes: the first resolves the page number of every heading, the
    # second lays the document out again with a populated contents page.
    document.multiBuild(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
