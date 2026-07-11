"""
Module 6 - Report Generator
====================================
Cybercrime Investigation Intelligence System (CIIS)

Consumes:
  - timeline.json from the Timeline Reconstruction engine (Module 5)

Produces a human-readable investigation report:

  1. Case overview / summary statistics
  2. Chronological narrative of evidence (grouped by case)
  3. Risk-signal highlights (pulled to the front, not buried in the timeline)
  4. Correlation highlights (which pieces of evidence reinforce each other)
  5. Confidence & caveats section, so low-confidence timestamps aren't
     mistaken for established fact

Default output format is PDF (for sharing/printing/filing as a case
artifact). Markdown output is also available via --format md.

This module is intentionally template-based rather than free-form/LLM-based
generation: every sentence in the report is traceable back to a specific
field in timeline.json, which matters for evidentiary use.

Usage:
    python report_generator.py output/timeline.json \
        [--case CASE_ID] [--format pdf|md] [--output output/report.pdf]
"""

import json
import os
import argparse
import hashlib
import uuid
from collections import defaultdict, Counter
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable,
)
from reportlab.pdfgen.canvas import Canvas as _BaseCanvas

OUTPUT_DIR = "output"


# ----------------------------------------------------------------------
# Report identity / integrity helpers
# ----------------------------------------------------------------------

def new_report_id() -> str:
    return f"RPT-{uuid.uuid4().hex[:10].upper()}"


def hash_file(path: str) -> str:
    """SHA-256 of the source timeline.json bytes, so a report can later be
    tied back to the exact evidence-timeline snapshot it was generated
    from (chain-of-custody / integrity check, not a security control)."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class _FootedCanvas(_BaseCanvas):
    """Canvas that adds a footer with report id / generated time on the
    left and 'Page X of Y' on the right. Reportlab requires a two-pass
    approach to know the total page count, hence the buffering here."""

    def __init__(self, *args, footer_left: str = "", **kwargs):
        _BaseCanvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self._footer_left = footer_left

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            _BaseCanvas.showPage(self)
        _BaseCanvas.save(self)

    def _draw_footer(self, total_pages: int):
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.grey)
        self.drawString(54, 30, self._footer_left)
        self.drawRightString(
            letter[0] - 54, 30,
            f"Page {self.getPageNumber()} of {total_pages}",
        )


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------

def load_timeline(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------
# Stats (shared by both output formats)
# ----------------------------------------------------------------------

def compute_stats(events: list) -> dict:
    confidence_counts = Counter(e["confidence"] for e in events)
    source_counts = Counter(e["time_source"] for e in events)
    case_counts = Counter(e["case_id"] for e in events)

    risk_tally = Counter()
    flagged_events = []
    for e in events:
        active = [k for k, v in (e.get("risk_signals") or {}).items() if v]
        if active:
            flagged_events.append((e, active))
            risk_tally.update(active)

    correlated_events = [e for e in events if e.get("correlated_with")]

    return {
        "confidence_counts": confidence_counts,
        "source_counts": source_counts,
        "case_counts": case_counts,
        "risk_tally": risk_tally,
        "flagged_events": flagged_events,
        "correlated_events": correlated_events,
    }


def _escape(text: str) -> str:
    """Escape text that will be embedded in a reportlab Paragraph (which
    parses a small XML-like markup), so raw evidence text can't break
    rendering or be mistaken for markup."""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


# ----------------------------------------------------------------------
# PDF styles
# ----------------------------------------------------------------------

def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportBody", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=6, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="Meta", parent=styles["Normal"],
        fontSize=9, textColor=colors.grey, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="EventLine", parent=styles["ReportBody"],
        spaceBefore=4, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="EventSub", parent=styles["ReportBody"],
        fontSize=9, leftIndent=14, textColor=colors.black,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="EventQuote", parent=styles["EventSub"],
        fontName="Helvetica-Oblique", textColor=colors.HexColor("#444444"),
    ))
    styles.add(ParagraphStyle(
        name="RiskWarning", parent=styles["EventSub"],
        textColor=colors.HexColor("#B03A2E"),
    ))
    return styles


# ----------------------------------------------------------------------
# PDF section builders (each returns a list of flowables)
# ----------------------------------------------------------------------

def build_overview_pdf(timeline: dict, stats: dict, generated_at: str, styles,
                        report_id: str, investigator: str,
                        source_path: str, source_hash: str) -> list:
    flow = [Paragraph("Investigation Report", styles["Title"])]

    meta_items = [
        f"Report ID: {_escape(report_id)}",
        f"Generated: {_escape(generated_at)}",
        f"Investigator: {_escape(investigator)}",
        f"Source file: {_escape(os.path.basename(source_path))}",
        f"Source SHA-256: {source_hash}",
    ]
    for item in meta_items:
        flow.append(Paragraph(item, styles["Meta"]))
    flow.append(Spacer(1, 4))

    flow.append(Paragraph("Overview", styles["Heading2"]))

    items = [
        f"Total evidence items: {timeline['total_events']}",
        f"Resolved timestamps: {timeline['resolved_count']}",
        f"Unresolved timestamps: {timeline['unresolved_count']}",
    ]
    if len(stats["case_counts"]) > 1:
        case_list = ", ".join(f"{cid} ({n})" for cid, n in stats["case_counts"].items())
        items.append(f"Cases covered: {_escape(case_list)}")

    conf = stats["confidence_counts"]
    conf_line = ", ".join(f"{level}: {conf.get(level, 0)}" for level in
                          ("high", "medium", "low", "none") if conf.get(level))
    items.append(f"Timestamp confidence breakdown: {conf_line}")

    flow.append(ListFlowable(
        [ListItem(Paragraph(i, styles["ReportBody"])) for i in items],
        bulletType="bullet",
    ))
    flow.append(Spacer(1, 8))
    return flow


def build_risk_highlights_pdf(stats: dict, styles) -> list:
    flow = [Paragraph("Risk Signal Highlights", styles["Heading2"])]

    if not stats["flagged_events"]:
        flow.append(Paragraph(
            "No risk signals were flagged on any evidence item.",
            styles["ReportBody"],
        ))
        flow.append(Spacer(1, 8))
        return flow

    tally_line = ", ".join(f"{signal} ({count})" for signal, count in
                           stats["risk_tally"].most_common())
    flow.append(Paragraph(f"<b>Signal frequency:</b> {_escape(tally_line)}",
                           styles["ReportBody"]))

    rows = []
    for event, active in stats["flagged_events"]:
        time_str = event["resolved_time"] or "unknown time"
        text = (f"<b>{_escape(event['evidence_id'])}</b> "
                f"({_escape(event['file_name'])}) at {_escape(time_str)} "
                f"&mdash; flags: {_escape(', '.join(active))}")
        rows.append(ListItem(Paragraph(text, styles["ReportBody"])))

    flow.append(ListFlowable(rows, bulletType="bullet"))
    flow.append(Spacer(1, 8))
    return flow


