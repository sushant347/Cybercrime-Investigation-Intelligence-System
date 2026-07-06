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


# Timestamp resolution

def _parse_upload_time(upload_time_str: str):
    if not upload_time_str:
        return None
    try:
        return datetime.fromisoformat(upload_time_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _try_chat_style_timestamp(raw_text: str, reference_dt: datetime):
    if not raw_text or not reference_dt:
        return None

    match = CHAT_TIMESTAMP_RE.search(raw_text)
    if not match:
        return None

    try:
        month = int(match.group("month"))
        day = int(match.group("day"))
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))

        if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        candidate = reference_dt.replace(
            month=month, day=day, hour=hour, minute=minute,
            second=0, microsecond=0,
        )
        if candidate > reference_dt:
            candidate = candidate.replace(year=candidate.year - 1)

        return candidate
    except (ValueError, TypeError):
        return None


def _try_entity_datetime(entities: dict, reference_dt: datetime):
    dates = [d.get("normalized") or d.get("value") for d in entities.get("dates", [])]
    times = [t.get("normalized") or t.get("value") for t in entities.get("times", [])]

    dates = [d for d in dates if d]
    times = [t for t in times if t]

    if dates:
        combined = f"{dates[0]} {times[0]}" if times else dates[0]
        try:
            return dateutil_parser.parse(combined, fuzzy=True, default=reference_dt), "content_date_time"
        except (ValueError, OverflowError):
            pass

    if times and reference_dt:
        try:
            parsed_time = dateutil_parser.parse(times[0], fuzzy=True, default=reference_dt)
            combined_dt = reference_dt.replace(
                hour=parsed_time.hour, minute=parsed_time.minute,
                second=parsed_time.second, microsecond=0,
            )
            return combined_dt, "content_time_only"
        except (ValueError, OverflowError):
            pass

    return None, None


def resolve_evidence_timestamp(evidence: dict) -> dict:
    upload_dt = _parse_upload_time(evidence.get("upload_time"))
    cleaning = evidence.get("cleaning", {})
    entities = cleaning.get("entities", {})
    raw_text = evidence.get("raw_text") or cleaning.get("cleaned_text") or ""

    dt, source = _try_entity_datetime(entities, upload_dt)
    if dt:
        confidence = "high" if source == "content_date_time" else "medium"
        return {
            "resolved_time": dt,
            "resolved_time_iso": dt.isoformat(),
            "source": source,
            "confidence": confidence,
        }

    chat_dt = _try_chat_style_timestamp(raw_text, upload_dt)
    if chat_dt:
        return {
            "resolved_time": chat_dt,
            "resolved_time_iso": chat_dt.isoformat(),
            "source": "content_chat_timestamp",
            "confidence": "medium",
        }

    if upload_dt:
        return {
            "resolved_time": upload_dt,
            "resolved_time_iso": upload_dt.isoformat(),
            "source": "upload_time_fallback",
            "confidence": "low",
        }

    return {
        "resolved_time": None,
        "resolved_time_iso": None,
        "source": "unresolved",
        "confidence": "none",
    }


# Correlation context lookup

def build_correlation_lookup(graph: dict) -> dict:
    lookup = {}
    for edge in graph.get("edges", []):
        for a, b in [(edge["source"], edge["target"]), (edge["target"], edge["source"])]:
            lookup.setdefault(a, []).append({
                "linked_to": b,
                "type": edge["type"],
                "shared_entities": edge.get("shared_entities", []),
                "weight": edge.get("weight", 0),
            })
    return lookup


# Timeline building

def build_timeline(cases: list, correlation_graph: dict = None) -> dict:
    correlation_graph = correlation_graph or {"nodes": [], "edges": []}
    correlation_lookup = build_correlation_lookup(correlation_graph)

    events = []
    for case in cases:
        case_id = case.get("case_id", "UNKNOWN_CASE")
        for evidence in case.get("evidence", []):
            evidence_id = evidence.get("evidence_id", "UNKNOWN_EVID")
            resolution = resolve_evidence_timestamp(evidence)

            events.append({
                "evidence_id": evidence_id,
                "case_id": case_id,
                "file_name": evidence.get("file_name"),
                "resolved_time": resolution["resolved_time_iso"],
                "time_source": resolution["source"],
                "confidence": resolution["confidence"],
                "text_preview": (evidence.get("raw_text") or "")[:120],
                "risk_signals": evidence.get("cleaning", {}).get("risk_signals", {}),
                "correlated_with": correlation_lookup.get(evidence_id, []),
                "_sort_key": resolution["resolved_time"],
            })

    resolved = [e for e in events if e["_sort_key"] is not None]
    unresolved = [e for e in events if e["_sort_key"] is None]

    resolved.sort(key=lambda e: e["_sort_key"])

    for e in resolved + unresolved:
        del e["_sort_key"]

    ordered = resolved + unresolved

    return {
        "total_events": len(ordered),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "timeline": ordered,
    }


