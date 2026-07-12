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


def build_correlation_highlights_pdf(stats: dict, styles) -> list:
    flow = [Paragraph("Correlation Highlights", styles["Heading2"])]

    if not stats["correlated_events"]:
        flow.append(Paragraph(
            "No correlations were found between evidence items (or "
            "Module 4's correlation graph was not available when the "
            "timeline was built).",
            styles["ReportBody"],
        ))
        flow.append(Spacer(1, 8))
        return flow

    rows = []
    for event in stats["correlated_events"]:
        links = event["correlated_with"]
        link_desc = "; ".join(
            f"{_escape(c['linked_to'])} ({_escape(c['type'])}, weight {c.get('weight', 0)})"
            for c in links
        )
        text = (f"<b>{_escape(event['evidence_id'])}</b> "
                f"({_escape(event['file_name'])}) &mdash; linked to: {link_desc}")
        rows.append(ListItem(Paragraph(text, styles["ReportBody"])))

    flow.append(ListFlowable(rows, bulletType="bullet"))
    flow.append(Spacer(1, 8))
    return flow


def build_timeline_narrative_pdf(events: list, styles) -> list:
    flow = [Paragraph("Chronological Narrative", styles["Heading2"])]

    by_case = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)

    for case_id, case_events in by_case.items():
        if len(by_case) > 1:
            flow.append(Paragraph(f"Case: {_escape(case_id)}", styles["Heading3"]))

        for e in case_events:
            time_str = e["resolved_time"] or "UNKNOWN TIME"
            conf_note = (
                f" <i>(confidence: {e['confidence']}, source: {e['time_source']})</i>"
                if e["confidence"] != "high" else ""
            )
            header = (f"<b>[{_escape(time_str)}]</b> {_escape(e['file_name'])} "
                      f"({_escape(e['evidence_id'])}){conf_note}")
            flow.append(Paragraph(header, styles["EventLine"]))

            preview = (e.get("text_preview") or "").strip()
            if preview:
                flow.append(Paragraph(f"&ldquo;{_escape(preview)}&rdquo;",
                                       styles["EventQuote"]))

            if e.get("correlated_with"):
                linked_ids = ", ".join(c["linked_to"] for c in e["correlated_with"])
                flow.append(Paragraph(f"correlated with: {_escape(linked_ids)}",
                                       styles["EventSub"]))

            active_risks = [k for k, v in (e.get("risk_signals") or {}).items() if v]
            if active_risks:
                flow.append(Paragraph(f"risk signals: {_escape(', '.join(active_risks))}",
                                       styles["RiskWarning"]))

        flow.append(Spacer(1, 6))

    return flow


def build_caveats_pdf(stats: dict, styles) -> list:
    flow = [Paragraph("Confidence &amp; Caveats", styles["Heading2"])]
    flow.append(Paragraph(
        "Timestamps in this report are resolved with varying confidence. "
        "Readers should weigh conclusions accordingly:",
        styles["ReportBody"],
    ))

    items = [
        "<b>high</b> &mdash; an explicit date and time were found in the "
        "evidence content itself (most forensically reliable).",
        "<b>medium</b> &mdash; either a chat-style inline timestamp or a "
        "time-only value combined with the upload date as a best guess; "
        "the date portion may be inexact.",
        "<b>low</b> &mdash; no usable timestamp was found in the content; "
        "the system fell back to the file's processing/upload time, which "
        "may not reflect when the underlying event occurred.",
        "<b>none</b> &mdash; no timestamp could be resolved at all; this "
        "item is listed at the end of the timeline, unordered relative to "
        "other unresolved items.",
    ]
    flow.append(ListFlowable(
        [ListItem(Paragraph(i, styles["ReportBody"])) for i in items],
        bulletType="bullet",
    ))

    low_or_worse = (stats["confidence_counts"].get("low", 0)
                    + stats["confidence_counts"].get("none", 0))
    if low_or_worse:
        total = sum(stats["confidence_counts"].values())
        flow.append(Paragraph(
            f"<b>{low_or_worse} of {total} evidence item(s) have low or "
            "unresolved timestamp confidence</b> and should not be treated "
            "as precisely dated without further corroboration.",
            styles["ReportBody"],
        ))
    return flow


# ----------------------------------------------------------------------
# Markdown section builders (kept as an alternate output format)
# ----------------------------------------------------------------------

def render_overview_md(timeline: dict, stats: dict, generated_at: str,
                        report_id: str, investigator: str,
                        source_path: str, source_hash: str) -> str:
    lines = ["# Investigation Report", ""]
    lines.append(f"- **Report ID:** {report_id}")
    lines.append(f"- **Generated:** {generated_at}")
    lines.append(f"- **Investigator:** {investigator}")
    lines.append(f"- **Source file:** {os.path.basename(source_path)}")
    lines.append(f"- **Source SHA-256:** {source_hash}")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Total evidence items:** {timeline['total_events']}")
    lines.append(f"- **Resolved timestamps:** {timeline['resolved_count']}")
    lines.append(f"- **Unresolved timestamps:** {timeline['unresolved_count']}")
    if len(stats["case_counts"]) > 1:
        case_list = ", ".join(f"{cid} ({n})" for cid, n in stats["case_counts"].items())
        lines.append(f"- **Cases covered:** {case_list}")
    conf = stats["confidence_counts"]
    conf_line = ", ".join(f"{level}: {conf.get(level, 0)}" for level in
                          ("high", "medium", "low", "none") if conf.get(level))
    lines.append(f"- **Timestamp confidence breakdown:** {conf_line}")
    lines.append("")
    return "\n".join(lines)


def render_risk_highlights_md(stats: dict) -> str:
    lines = ["## Risk Signal Highlights", ""]
    if not stats["flagged_events"]:
        lines.append("No risk signals were flagged on any evidence item.")
        lines.append("")
        return "\n".join(lines)
    tally_line = ", ".join(f"{signal} ({count})" for signal, count in
                           stats["risk_tally"].most_common())
    lines.append(f"**Signal frequency:** {tally_line}")
    lines.append("")
    for event, active in stats["flagged_events"]:
        time_str = event["resolved_time"] or "unknown time"
        lines.append(
            f"- `{event['evidence_id']}` ({event['file_name']}) at {time_str} "
            f"— flags: {', '.join(active)}"
        )
    lines.append("")
    return "\n".join(lines)


def render_correlation_highlights_md(stats: dict) -> str:
    lines = ["## Correlation Highlights", ""]
    if not stats["correlated_events"]:
        lines.append(
            "No correlations were found between evidence items "
            "(or Module 4's correlation graph was not available when the "
            "timeline was built)."
        )
        lines.append("")
        return "\n".join(lines)
    for event in stats["correlated_events"]:
        links = event["correlated_with"]
        link_desc = "; ".join(
            f"{c['linked_to']} ({c['type']}, weight {c.get('weight', 0)})"
            for c in links
        )
        lines.append(f"- `{event['evidence_id']}` ({event['file_name']}) — linked to: {link_desc}")
    lines.append("")
    return "\n".join(lines)


def render_timeline_narrative_md(events: list) -> str:
    lines = ["## Chronological Narrative", ""]
    by_case = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)
    for case_id, case_events in by_case.items():
        if len(by_case) > 1:
            lines.append(f"### Case: {case_id}")
            lines.append("")
        for e in case_events:
            time_str = e["resolved_time"] or "UNKNOWN TIME"
            conf_note = (
                f" _(confidence: {e['confidence']}, source: {e['time_source']})_"
                if e["confidence"] != "high" else ""
            )
            line = f"- **[{time_str}]** {e['file_name']} (`{e['evidence_id']}`){conf_note}"
            preview = (e.get("text_preview") or "").strip()
            if preview:
                line += f"\n  > {preview}"
            if e.get("correlated_with"):
                linked_ids = ", ".join(c["linked_to"] for c in e["correlated_with"])
                line += f"\n  — correlated with: {linked_ids}"
            active_risks = [k for k, v in (e.get("risk_signals") or {}).items() if v]
            if active_risks:
                line += f"\n  — ⚠ risk signals: {', '.join(active_risks)}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines)


def render_caveats_md(stats: dict) -> str:
    lines = ["## Confidence & Caveats", ""]
    lines.append(
        "Timestamps in this report are resolved with varying confidence. "
        "Readers should weigh conclusions accordingly:"
    )
    lines.append("")
    lines.append("- **high** — an explicit date and time were found in the evidence "
                  "content itself (most forensically reliable).")
    lines.append("- **medium** — either a chat-style inline timestamp or a time-only "
                  "value combined with the upload date as a best guess; the date "
                  "portion may be inexact.")
    lines.append("- **low** — no usable timestamp was found in the content; the "
                  "system fell back to the file's processing/upload time, which may "
                  "not reflect when the underlying event occurred.")
    lines.append("- **none** — no timestamp could be resolved at all; this item is "
                  "listed at the end of the timeline, unordered relative to other "
                  "unresolved items.")
    low_or_worse = (stats["confidence_counts"].get("low", 0)
                    + stats["confidence_counts"].get("none", 0))
    if low_or_worse:
        lines.append("")
        lines.append(
            f"**{low_or_worse} of {sum(stats['confidence_counts'].values())} "
            "evidence item(s) have low or unresolved timestamp confidence** "
            "and should not be treated as precisely dated without further "
            "corroboration."
        )
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Report assembly
# ----------------------------------------------------------------------

def _scope_to_case(timeline: dict, case_filter: str) -> dict:
    events = [e for e in timeline["timeline"] if e["case_id"] == case_filter]
    if not events:
        raise ValueError(f"No evidence found for case_id '{case_filter}'")
    return {
        "total_events": len(events),
        "resolved_count": sum(1 for e in events if e["resolved_time"]),
        "unresolved_count": sum(1 for e in events if not e["resolved_time"]),
        "timeline": events,
    }


def generate_report_pdf(timeline: dict, output_path: str, source_path: str,
                         case_filter: str = None, investigator: str = "Unspecified",
                         report_id: str = None):
    if case_filter:
        timeline = _scope_to_case(timeline, case_filter)

    report_id = report_id or new_report_id()
    source_hash = hash_file(source_path)

    events = timeline["timeline"]
    stats = compute_stats(events)
    generated_at = datetime.now().isoformat(timespec="seconds")
    styles = _build_styles()

    story = []
    story += build_overview_pdf(timeline, stats, generated_at, styles,
                                 report_id, investigator, source_path, source_hash)
    story.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC")))
    story += build_risk_highlights_pdf(stats, styles)
    story += build_correlation_highlights_pdf(stats, styles)
    story += build_timeline_narrative_pdf(events, styles)
    story.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC")))
    story += build_caveats_pdf(stats, styles)

    footer_left = f"{report_id}  |  Generated {generated_at}"

    def _make_canvas(*args, **kwargs):
        return _FootedCanvas(*args, footer_left=footer_left, **kwargs)

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=54, bottomMargin=64, leftMargin=54, rightMargin=54,
        title="Investigation Report", author=investigator,
        subject=f"CIIS Investigation Report {report_id}",
    )
    doc.build(story, canvasmaker=_make_canvas)
    return report_id, source_hash


def generate_report_md(timeline: dict, source_path: str, case_filter: str = None,
                        investigator: str = "Unspecified", report_id: str = None) -> tuple:
    if case_filter:
        timeline = _scope_to_case(timeline, case_filter)

    report_id = report_id or new_report_id()
    source_hash = hash_file(source_path)

    events = timeline["timeline"]
    stats = compute_stats(events)
    generated_at = datetime.now().isoformat(timespec="seconds")

    sections = [
        render_overview_md(timeline, stats, generated_at, report_id,
                            investigator, source_path, source_hash),
        render_risk_highlights_md(stats),
        render_correlation_highlights_md(stats),
        render_timeline_narrative_md(events),
        render_caveats_md(stats),
    ]
    return "\n".join(sections), report_id, source_hash


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("timeline", help="Path to timeline.json from Module 5")
    parser.add_argument("--case", default=None,
                         help="Restrict the report to a single case_id")
    parser.add_argument("--format", choices=["pdf", "md"], default="pdf",
                         help="Output format (default: pdf)")
    parser.add_argument("--output", default=None,
                         help="Output path (default: output/report.<format>)")
    parser.add_argument("--investigator", default="Unspecified",
                         help="Name/ID recorded on the report as the investigator")
    parser.add_argument("--report-id", default=None,
                         help="Custom report ID (default: auto-generated, e.g. RPT-XXXXXXXXXX)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timeline = load_timeline(args.timeline)
    output_path = args.output or os.path.join(OUTPUT_DIR, f"report.{args.format}")

    if args.format == "pdf":
        report_id, source_hash = generate_report_pdf(
            timeline, output_path, args.timeline, case_filter=args.case,
            investigator=args.investigator, report_id=args.report_id,
        )
    else:
        report, report_id, source_hash = generate_report_md(
            timeline, args.timeline, case_filter=args.case,
            investigator=args.investigator, report_id=args.report_id,
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

    print(f"Generated report -> {output_path}")
    print(f"Report ID: {report_id}")
    print(f"Source SHA-256: {source_hash}")


if __name__ == "__main__":
    main()
