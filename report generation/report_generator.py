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
