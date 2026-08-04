"""
Module 5 - Timeline Reconstruction
====================================
Cybercrime Investigation Intelligence Engine (CIIS)

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
    python -m ciis_timeline_report.timeline.engine case1.json [case2.json ...] \
        [--correlation output/correlation_graph.json]
"""

import json
import os
import re
import argparse
from datetime import datetime, timezone
from typing import Iterable, Optional

OUTPUT_DIR = "output"


# Local rather than imported from ciis_correlation.core.text: this module is
# the framework-independent algorithm and deliberately depends on nothing but
# the standard library, so it stays testable and reusable on its own.
def _plural(word: str, count: float) -> str:
    """``"hour"`` or ``"hours"``, agreeing with ``count``."""
    return word if count == 1 else f"{word}s"


def _count(count: int, word: str) -> str:
    """``"3 events"`` - the number and its correctly agreeing noun."""
    return f"{count} {_plural(word, count)}"


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
        parsed = datetime.fromisoformat(upload_time_str.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
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


def _entity_values(entities: dict, entity_type: str) -> list[str]:
    values = []
    for item in entities.get(entity_type, []):
        value = (item.get("normalized") or item.get("value")) \
            if isinstance(item, dict) else item
        if value:
            values.append(str(value).strip())
    return values


def _parse_date(value: str, reference_dt: Optional[datetime]) -> Optional[datetime]:
    """Parse common normalized/visible forensic date representations."""
    text = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    # Partial month-day dates use the upload year, rolling back if needed.
    for fmt in ("%m-%d", "%d-%m"):
        if reference_dt is None:
            continue
        try:
            partial = datetime.strptime(text, fmt)
            parsed = reference_dt.replace(
                month=partial.month, day=partial.day,
                hour=0, minute=0, second=0, microsecond=0,
            )
            if parsed > reference_dt:
                parsed = parsed.replace(year=parsed.year - 1)
            return parsed
        except ValueError:
            continue
    return None


def _parse_time(value: str) -> Optional[tuple[int, int, int]]:
    text = value.strip().lower().replace(".", ":")
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.hour, parsed.minute, parsed.second
        except ValueError:
            continue
    return None


def _try_entity_datetime(entities: dict, reference_dt: Optional[datetime]):
    dates = _entity_values(entities, "dates")
    times = _entity_values(entities, "times")

    dates = [d for d in dates if d]
    times = [t for t in times if t]

    if dates:
        parsed_date = _parse_date(dates[0], reference_dt)
        if parsed_date is not None:
            parsed_time = _parse_time(times[0]) if times else None
            if parsed_time is not None:
                return parsed_date.replace(
                    hour=parsed_time[0], minute=parsed_time[1], second=parsed_time[2]
                ), "content_date_time"
            return parsed_date, "content_date_only"

    if times and reference_dt:
        parsed_time = _parse_time(times[0])
        if parsed_time is not None:
            combined_dt = reference_dt.replace(
                hour=parsed_time[0], minute=parsed_time[1],
                second=parsed_time[2], microsecond=0,
            )
            return combined_dt, "content_time_only"

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
    seen = set()
    for edge in graph.get("edges", []):
        source = str(edge.get("source", "")).removeprefix("evidence:")
        target = str(edge.get("target", "")).removeprefix("evidence:")
        if not source or not target:
            continue
        for a, b in ((source, target), (target, source)):
            key = (a, b, edge.get("type") or edge.get("edge_type", "relationship"))
            if key in seen:
                continue
            seen.add(key)
            lookup.setdefault(a, []).append({
                "linked_to": b,
                "type": edge.get("type") or edge.get("edge_type", "relationship"),
                "shared_entities": edge.get("shared_entities", []),
                "weight": edge.get("weight", 0),
                "confidence": edge.get("confidence", edge.get("weight", 0)),
            })
    return lookup


# Timeline building

def _classify_stages(text: str, stage_order: Iterable[str],
                     stage_keywords: dict) -> tuple[list[str], dict[str, list[str]]]:
    lowered = (text or "").lower()
    stages, matched = [], {}
    for stage in stage_order:
        hits = sorted({keyword.strip() for keyword in stage_keywords.get(stage, ())
                       if keyword and keyword.lower() in lowered})
        if hits:
            stages.append(stage)
            matched[stage] = hits
    return stages, matched


def _critical_reasons(entities: dict, entity_types: Iterable[str]) -> list[str]:
    reasons = []
    for entity_type in entity_types:
        values = sorted(set(_entity_values(entities, entity_type)))
        if values:
            reasons.append(
                f"contains {entity_type} entity/entities: " + ", ".join(values[:3])
            )
    return reasons


def _attack_stages(events: list[dict], stage_order: Iterable[str],
                   stage_hits: dict[str, dict[str, list[str]]]) -> list[dict]:
    by_id = {event["evidence_id"]: event for event in events}
    result = []
    for stage in stage_order:
        hits = stage_hits.get(stage, {})
        if not hits:
            continue
        evidence_ids = sorted(
            hits,
            key=lambda eid: (
                not bool(by_id[eid]["timestamp"]), by_id[eid]["timestamp"], eid
            ),
        )
        keywords = sorted({keyword for values in hits.values() for keyword in values})
        timestamps = [by_id[eid]["timestamp"] for eid in evidence_ids
                      if by_id[eid]["timestamp"]]
        result.append({
            "stage": stage,
            "evidence_ids": evidence_ids,
            "first_seen": timestamps[0] if timestamps else "",
            "last_seen": timestamps[-1] if timestamps else "",
            "matched_keywords": keywords,
            "explanation": (
                f"Stage '{stage}' is evidenced by keyword matches "
                f"({', '.join(keywords[:5])}) in " + ", ".join(evidence_ids) + "."
            ),
        })
    return result


def _milestones(events: list[dict]) -> list[dict]:
    if not events:
        return []
    milestones = [{
        **events[0], "event_type": "milestone", "stages": [],
        "critical": False, "critical_reasons": [],
        "description": "Investigation start - first reconstructed evidence event",
    }]
    seen = set()
    for event in events:
        for stage in event["stages"]:
            if stage in seen:
                continue
            seen.add(stage)
            milestones.append({
                **event, "event_type": "milestone", "stages": [stage],
                "critical": False, "critical_reasons": [],
                "description": f"First observation of stage '{stage}' ({event['evidence_id']})",
            })
    return milestones


def build_timeline(
    cases: list,
    correlation_graph: Optional[dict] = None,
    *,
    stage_keywords: Optional[dict] = None,
    stage_order: Iterable[str] = (),
    critical_entity_types: Iterable[str] = (),
) -> dict:
    """Build the canonical, framework-independent investigation timeline."""
    correlation_graph = correlation_graph or {"nodes": [], "edges": []}
    correlation_lookup = build_correlation_lookup(correlation_graph)
    stage_keywords = stage_keywords or {}
    stage_order = tuple(stage_order)

    events = []
    seen_events = set()
    stage_hits: dict[str, dict[str, list[str]]] = {}
    for case in cases:
        case_id = case.get("case_id", "UNKNOWN_CASE")
        for evidence in case.get("evidence", []):
            evidence_id = evidence.get("evidence_id", "UNKNOWN_EVID")
            resolution = resolve_evidence_timestamp(evidence)
            event_key = (case_id, evidence_id)
            if event_key in seen_events:
                continue
            seen_events.add(event_key)
            cleaning = evidence.get("cleaning", {}) or {}
            entities = cleaning.get("entities", {}) or {}
            text = (
                evidence.get("semantic_text")
                or (evidence.get("semantic_correction", {}) or {}).get("semantic_text")
                or (evidence.get("enhancement", {}) or {}).get("enhanced_text")
                or cleaning.get("cleaned_text")
                or evidence.get("raw_text")
                or ""
            )
            stages, matched = _classify_stages(text, stage_order, stage_keywords)
            for stage, keywords in matched.items():
                stage_hits.setdefault(stage, {})[evidence_id] = keywords
            critical_reasons = _critical_reasons(entities, critical_entity_types)
            timestamp_inferred = resolution["source"] in {
                "content_date_only", "content_time_only", "content_chat_timestamp",
                "upload_time_fallback",
            }

            events.append({
                "evidence_id": evidence_id,
                "case_id": case_id,
                "file_name": evidence.get("file_name") or "",
                "resolved_time": resolution["resolved_time_iso"],
                "timestamp": resolution["resolved_time_iso"] or "",
                "time_source": resolution["source"],
                "confidence": resolution["confidence"],
                "timestamp_inferred": timestamp_inferred,
                "event_type": "evidence_event",
                "description": (
                    f"Evidence {evidence_id} ({evidence.get('file_name') or 'unknown file'})"
                    + (f"; stages: {', '.join(stages)}" if stages else "")
                ),
                "stages": stages,
                "critical": bool(critical_reasons),
                "critical_reasons": critical_reasons,
                "source_evidence_ids": [evidence_id],
                "text_preview": text[:120],
                "risk_signals": cleaning.get("risk_signals", {}),
                "correlated_with": correlation_lookup.get(evidence_id, []),
                "_sort_key": resolution["resolved_time"],
            })

    resolved = [e for e in events if e["_sort_key"] is not None]
    unresolved = [e for e in events if e["_sort_key"] is None]

    resolved.sort(key=lambda event: (event["_sort_key"], event["evidence_id"]))
    unresolved.sort(key=lambda event: (event["case_id"], event["evidence_id"]))

    for e in resolved + unresolved:
        del e["_sort_key"]

    ordered = resolved + unresolved

    attack_stages = _attack_stages(ordered, stage_order, stage_hits)
    progression = []
    for event in ordered:
        for stage in event["stages"]:
            if stage not in progression:
                progression.append(stage)
    order_index = {stage: index for index, stage in enumerate(stage_order)}
    observed = [order_index[stage] for stage in progression if stage in order_index]
    timestamps = [datetime.fromisoformat(event["timestamp"])
                  for event in ordered if event["timestamp"]]
    span_hours = ((max(timestamps) - min(timestamps)).total_seconds() / 3600.0
                  if len(timestamps) > 1 else 0.0)
    milestones = _milestones(ordered)
    critical_events = [event for event in ordered if event["critical"]]
    summary = (
        f"{_count(len(ordered), 'event')} spanning "
        f"{span_hours:.1f} {_plural('hour', span_hours)}; "
        f"{_count(len(unresolved), 'timestamp')} unresolved."
    )
    if progression:
        summary += " Observed scam progression: " + " -> ".join(progression) + "."

    return {
        "case_id": cases[0].get("case_id", "UNKNOWN_CASE")
        if len(cases) == 1 else "MULTI_CASE",
        "total_events": len(ordered),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "timeline": ordered,
        "events": ordered,
        "attack_stages": attack_stages,
        "stage_progression": progression,
        "progression_consistent": observed == sorted(observed),
        "milestones": milestones,
        "critical_events": critical_events,
        "summary": summary,
        "statistics": {
            "event_count": float(len(ordered)),
            "resolved_event_count": float(len(resolved)),
            "unresolved_event_count": float(len(unresolved)),
            "inferred_event_count": float(sum(
                1 for event in ordered if event["timestamp_inferred"]
            )),
            "stage_count": float(len(attack_stages)),
            "critical_event_count": float(len(critical_events)),
            "timeline_span_hours": round(span_hours, 2),
        },
    }


def generate_narrative(timeline: dict) -> list:
    lines = []
    for event in timeline["timeline"]:
        time_str = event["resolved_time"] or "UNKNOWN TIME"
        confidence_note = f" (confidence: {event['confidence']})" if event["confidence"] != "high" else ""
        line = f"[{time_str}] {event['file_name']} (evidence {event['evidence_id']}){confidence_note}"

        if event["correlated_with"]:
            linked_ids = ", ".join(c["linked_to"] for c in event["correlated_with"])
            line += f" -- correlated with: {linked_ids}"

        risk = event.get("risk_signals", {})
        active_risks = [k for k, v in risk.items() if v]
        if active_risks:
            line += f" -- risk signals: {', '.join(active_risks)}"

        lines.append(line)
    return lines


# CLI entry point

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="+", help="Case JSON file(s)")
    parser.add_argument("--correlation", default=None,
                         help="Path to correlation_graph.json from Module 4")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cases = [load_case(p) for p in args.cases]
    correlation_graph = load_correlation_graph(args.correlation)

    timeline = build_timeline(cases, correlation_graph)
    narrative = generate_narrative(timeline)

    timeline_path = os.path.join(OUTPUT_DIR, "timeline.json")
    narrative_path = os.path.join(OUTPUT_DIR, "timeline_narrative.txt")

    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, ensure_ascii=False)

    with open(narrative_path, "w", encoding="utf-8") as f:
        f.write("\n".join(narrative))

    print(f"Built timeline: {_count(timeline['total_events'], 'event')}, "
          f"{timeline['resolved_count']} resolved, "
          f"{timeline['unresolved_count']} unresolved")
    print(f"Saved -> {timeline_path}")
    print(f"Saved -> {narrative_path}")
    print("\nNarrative preview:")
    for line in narrative:
        print(f"  {line}")


if __name__ == "__main__":
    main()
