"""
Module 5 - Timeline Reconstruction
====================================
Cybercrime Investigation Intelligence System (CIIS)

Consumes:
  - Case JSON from the OCR/evidence engine (Module 2)
  - correlation_graph.json from the Evidence Correlation Engine (Module 4)
    [optional, but recommended -- adds "why this fits here" context]

Produces a chronologically ordered timeline of evidence, resolving the best
available timestamp for each item:

  1. In-content date+time extracted from OCR text (most forensically
     meaningful -- e.g. when a chat message was actually sent)
  2. In-content time only, combined with the evidence upload date as a
     best-guess day (lower confidence)
  3. Evidence upload_time as a last-resort fallback (lowest confidence --
     this is when the file was processed by the system, not necessarily
     when the underlying event happened)

Each timeline entry is also annotated with any evidence it's correlated
with (from Module 4's graph), so the timeline reads as a narrative rather
than a bare sorted list.

Usage:
    python timeline_reconstruction.py case1.json [case2.json ...] \
        [--correlation output/correlation_graph.json]
"""

import json
import os
import sys
import re
import argparse
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser

OUTPUT_DIR = "output"

CHAT_TIMESTAMP_RE = re.compile(
    r"(?P<month>\d{1,2})-(?P<day>\d{1,2})\s*,\s*"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::\w+)?"
)


# Loading

def load_case(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_correlation_graph(path: str) -> dict:
    if not path:
        print("NOTE: no --correlation path given -- timeline will not include "
              "correlation context (correlated_with will be empty for every event).")
        return {"nodes": [], "edges": []}

    if not os.path.exists(path):
        print(f"WARNING: --correlation path '{path}' does not exist. "
              f"Did you run correlation_engine.py first? "
              f"Proceeding without correlation context.")
        return {"nodes": [], "edges": []}

    with open(path, "r", encoding="utf-8") as f:
        graph = json.load(f)
        print(f"Loaded correlation graph: {len(graph.get('nodes', []))} nodes, "
              f"{len(graph.get('edges', []))} edges from {path}")
        return graph


