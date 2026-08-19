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
        ["Status", "Automated analytical draft - investigator review required"],
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
        "stored forensic finding; the generator has no free-text capability. "
        "The accuracy of those findings still depends on source quality and "
        "upstream extraction, and requires investigator review. Where an "
        "input was unavailable the report says so explicitly. The Report "
        "Provenance &amp; Integrity section lists the "
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
    def emit_numbered_table(section: Any, label: str) -> bool:
        if not isinstance(section, list):
            return False
        story.append(data_table(
            ["#", label],
            [[str(index), str(item)] for index, item in enumerate(section, start=1)],
            widths=[12 * mm, 149 * mm],
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
        story.append(data_table(
            ["Scope", "Recorded basis"],
            [["Objective", section.get("objective", "not available")],
             ["Evidence scope", section.get("evidence_scope", "not available")],
             ["Reproducibility", section.get("reproducibility", "not available")]],
            widths=[34 * mm, 127 * mm],
        ))
        methods = []
        for method in section.get("methodology") or []:
            stage, separator, detail = str(method).partition(":")
            methods.append([stage, detail.strip() if separator else method])
        if methods:
            story.append(Spacer(1, 5))
            story.append(Paragraph("Processing stages", styles["h3"]))
            story.append(data_table(
                ["Stage", "Method and stored output"], methods,
                widths=[48 * mm, 113 * mm],
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
            ["Evidence", "File", "Acquired", "OCR", "Entities", "Integrity"],
            [[r.get("evidence_id", ""), r.get("file_name", ""),
              str(r.get("upload_time", ""))[:19],
              (f"{float(r.get('ocr_confidence') or 0) * 100:.0f}%"
               if r.get("ocr_confidence") is not None else "n/a"),
              str(r.get("entity_count", 0)),
              "VERIFIED" if r.get("hash_verified") else "FAILED"]
             for r in rows],
            widths=[27 * mm, 45 * mm, 31 * mm, 14 * mm, 17 * mm, 27 * mm]))
        story.append(Spacer(1, 3))
        story.append(Paragraph(
            "SHA-256 digests for each item are listed in the Appendix "
            "(chain of custody).", styles["subtitle"]))
        return True

    def emit_timeline_table(section: Any) -> bool:
        """Show the chronology and timestamp provenance in one readable view."""
        if not isinstance(section, dict) or "chronological_events" not in section:
            return False
        if section.get("summary"):
            story.append(Paragraph(esc(section["summary"]), styles["body"]))
            story.append(Spacer(1, 4))
        quality = section.get("timestamp_quality") or {}
        if quality.get("reliability_note"):
            story.append(Paragraph(
                esc(quality["reliability_note"]), styles["caveat"]
            ))
            story.append(Spacer(1, 5))
        rows = section.get("chronological_events") or []
        if rows:
            story.append(data_table(
                ["Timestamp (UTC)", "Evidence", "File", "Source", "Conf.", "Inferred"],
                [[
                    str(row.get("timestamp", "unresolved"))[:25],
                    row.get("evidence_id", ""),
                    row.get("file_name", ""),
                    str(row.get("timestamp_source", "")).replace("_", " "),
                    row.get("timestamp_confidence", ""),
                    "YES" if row.get("timestamp_inferred") else "NO",
                ] for row in rows],
                widths=[35 * mm, 25 * mm, 39 * mm, 33 * mm, 14 * mm, 15 * mm],
            ))
        story.append(Spacer(1, 5))
        order = section.get("stage_progression") or []
        story.append(Paragraph(
            "<b>Keyword-derived stage order:</b> "
            + esc(" -> ".join(order) if order else "none"),
            styles["body"],
        ))
        story.append(Paragraph(
            "<b>Order assessable:</b> "
            + ("yes" if section.get("progression_assessable") else "no")
            + " &nbsp;|&nbsp; <b>Matches configured sequence:</b> "
            + ("yes" if section.get("progression_consistent") else "no"),
            styles["subtitle"],
        ))
        critical = section.get("critical_events") or []
        if critical:
            story.append(Spacer(1, 5))
            story.append(Paragraph("<b>Critical events</b>", styles["body"]))
            for event in critical:
                reasons = "; ".join(event.get("reasons") or [])
                story.append(Paragraph(
                    f"&bull; <b>{esc(event.get('evidence_id', 'unknown'))}</b> "
                    f"{esc(event.get('timestamp', 'unresolved'))} - {esc(reasons)}",
                    styles["bullet"],
                ))
        return True

    def emit_correlation_table(section: Any) -> bool:
        if not isinstance(section, dict) or "top_relationships" not in section:
            return False
        story.append(Paragraph(
            f"{section.get('related_pair_count', 0)} of "
            f"{section.get('pair_count', 0)} analysed pairs met a configured "
            "relationship threshold. Association is not causation or identity.",
            styles["caveat"],
        ))
        rows = section.get("top_relationships") or []
        if rows:
            story.append(Spacer(1, 5))
            story.append(data_table(
                ["Evidence pair", "Strength", "Confidence", "Computed basis"],
                [[
                    row.get("pair", ""),
                    row.get("strength", ""),
                    f"{float(row.get('confidence') or 0):.2f}",
                    " ".join(str(row.get("explanation", "")).split())[:260],
                ] for row in rows],
                widths=[39 * mm, 23 * mm, 19 * mm, 80 * mm],
            ))
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
                link.get("relationship_strength", ""),
                f"{float(link.get('match_confidence') or 0):.2f}",
                ", ".join(indicators),
                " ".join(str(link.get("match_reason", "")).split())[:180],
            ])
        if rows:
            story.append(Spacer(1, 5))
            story.append(data_table(
                ["Other case", "Strength", "Conf.", "Matched indicators", "Basis"],
                rows,
                widths=[31 * mm, 22 * mm, 16 * mm, 52 * mm, 40 * mm],
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
        story.append(Paragraph(
            "Identity anchors are investigative leads, not legal attribution. "
            "Verify ownership and role using original exhibits and independent records.",
            styles["caveat"],
        ))
        story.append(Spacer(1, 5))
        story.append(data_table(
            ["Identity lead", "Score", "Confidence", "Risk", "Supporting evidence"],
            [[
                row.get("identity", ""),
                str(row.get("confidence_score", "")),
                row.get("confidence_level", ""),
                row.get("risk_level", ""),
                ", ".join(row.get("evidence_ids") or []),
            ] for row in section],
            widths=[46 * mm, 16 * mm, 24 * mm, 18 * mm, 57 * mm],
        ))
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
                data_table(
                    ["Field", "Recorded value"],
                    [["Conduct", provision["conduct"]],
                     ["Penalty", provision["penalty"]],
                     ["Evidence-based match", provision["basis"]],
                     ["Supporting evidence", ", ".join(
                         provision.get("evidence_ids") or ["none"])]],
                    widths=[39 * mm, 122 * mm],
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
                "These are preservation or investigative actions, not findings "
                "that an institution violated a rule.", styles["subtitle"]))
            story.append(Spacer(1, 5))
            for item in guidance:
                block = [
                    Paragraph(esc(item["title"]), styles["h3"]),
                    Paragraph(esc(item["citation"]), styles["subtitle"]),
                    Spacer(1, 3),
                    data_table(
                        ["Field", "Recorded value"],
                        [["Status", item.get("status", "investigative_follow_up")],
                         ["Expectation", item["expectation"]],
                         ["Why relevant", item["basis"]],
                         ["Recommended action", item["recommended_action"]],
                         ["Applicability", item["applicability"]],
                         ["Supporting evidence", ", ".join(
                             item.get("evidence_ids") or ["none"])]],
                        widths=[39 * mm, 122 * mm],
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
        if key == "scope_and_methodology" and emit_scope_table(value):
            continue
        if key == "case_overview" and emit_case_overview(value):
            continue
        if key == "evidence_summary" and emit_evidence_table(value):
            continue
        if key == "timeline_analysis" and emit_timeline_table(value):
            continue
        if key == "correlation_analysis" and emit_correlation_table(value):
            continue
        if key == "cross_case_correlation" and emit_cross_case_table(value):
            continue
        if key == "campaign_analysis" and emit_campaign_table(value):
            continue
        if key == "suspect_assessment" and emit_suspect_table(value):
            continue
        if key == "model_predictions" and emit_predictions_table(value):
            continue
        if key == "metadata_summary" and emit_metadata_table(value):
            continue
        if key == "confidence_analysis" and emit_confidence_table(value):
            continue
        if key == "legal_basis" and emit_legal_basis(value):
            continue
        if key in {
            "executive_summary", "limitations",
            "investigation_conclusion", "recommendations",
        }:
            label = {
                "executive_summary": "Finding",
                "limitations": "Review boundary",
                "investigation_conclusion": "Conclusion",
                "recommendations": "Investigator action",
            }[key]
            if emit_numbered_table(value, label):
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
