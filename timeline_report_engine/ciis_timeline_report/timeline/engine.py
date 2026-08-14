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
from datetime import datetime, timedelta, timezone
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

FULL_CHAT_TIMESTAMP_RE = re.compile(
    r"(?<!\d)[\[(]?\s*(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-]"
    r"(?P<year>\d{2,4})\s*,?\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2}))?\s*(?P<ampm>am|pm)?\s*[\])]?\s*(?!\d)",
    re.IGNORECASE,
)

# OCR often removes the separator between an ISO date and its time, for
# example ``2026-06-1110:42AM``. Fixed-width year/month/day groups are
# intentional: a permissive day/month parser can backtrack into that value and
# turn it into the syntactically valid but impossible year 0111.
VISIBLE_ISO_DATETIME_RE = re.compile(
    r"(?<!\d)(?P<year>\d{4})[/-](?P<month>\d{1,2})[/-](?P<day>\d{1,2})"
    r"(?:[ T]?)(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2}))?\s*(?P<ampm>am|pm)?\b",
    re.IGNORECASE,
)

# A labelled value is more probative than the first date mentioned in prose.
# The label grammar is deliberately generic (``Payment Date``, ``Date of
# Report``, ``Created Time`` and similar forms), rather than tied to a case or
# document template. Both ``Label: value`` and OCR's ``Label\nvalue`` survive.
LABELLED_TIMESTAMP_RE = re.compile(
    r"^[ \t]*(?P<label>(?:"
    r"date(?:\s*(?:&|and)\s*time)?|timestamp|time|"
    r"date\s+of\s+[A-Za-z][A-Za-z0-9 _/&-]{0,30}|"
    r"[A-Za-z][A-Za-z0-9 _/&-]{0,30}\s+"
    r"(?:date(?:\s*(?:&|and)\s*time)?|timestamp|time)"
    r"))[ \t]*(?::[ \t]*|\r?\n[ \t]*)(?P<value>[^\r\n]{1,100})",
    re.IGNORECASE | re.MULTILINE,
)

VISIBLE_DATE_PATTERNS = (
    re.compile(r"(?<!\d)\d{4}[/-]\d{1,2}[/-]\d{1,2}(?!\d)"),
    re.compile(r"(?<!\d)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?!\d)"),
    re.compile(
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{4}\b",
        re.IGNORECASE,
    ),
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


def _plausible_year(year: int, reference_dt: Optional[datetime] = None) -> bool:
    """Reject parser artefacts while retaining ordinary historical evidence."""
    upper_reference = reference_dt or datetime.now(timezone.utc)
    return 1970 <= year <= upper_reference.year + 1


def _plausible_datetime(
    value: datetime, reference_dt: Optional[datetime] = None
) -> bool:
    return _plausible_year(value.year, reference_dt)


def _try_chat_style_timestamp(raw_text: str, reference_dt: Optional[datetime]):
    if not raw_text:
        return None

    full = FULL_CHAT_TIMESTAMP_RE.search(raw_text)
    if full:
        try:
            year = int(full.group("year"))
            if year < 100:
                year += 2000 if year <= 68 else 1900
            if not _plausible_year(year, reference_dt):
                raise ValueError("implausible timestamp year")
            hour = int(full.group("hour"))
            ampm = (full.group("ampm") or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            candidate = datetime(
                year,
                int(full.group("month")),
                int(full.group("day")),
                hour,
                int(full.group("minute")),
                int(full.group("second") or 0),
                tzinfo=timezone.utc,
            )
            return candidate, False
        except (ValueError, TypeError):
            pass

    if not reference_dt:
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

        return candidate, True
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
    text = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", value.strip(), flags=re.I)
    text = text.replace(",", "").replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%B %d %Y", "%b %d %Y",
                "%d %B %Y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            if _plausible_datetime(parsed, reference_dt):
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


def _parse_metadata_datetime(value: str) -> Optional[datetime]:
    """Parse ISO, EXIF and PDF metadata timestamp representations."""
    text = str(value or "").strip()
    if not text:
        return None
    # PDF dates commonly use D:YYYYMMDDHHmmSS+05'45'. Preserve the offset.
    pdf = re.match(
        r"^D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?"
        r"(?:(Z)|([+-])(\d{2})'?(\d{2})'?)?",
        text,
    )
    if pdf:
        try:
            base = datetime(
                int(pdf.group(1)), int(pdf.group(2)), int(pdf.group(3)),
                int(pdf.group(4) or 0), int(pdf.group(5) or 0),
                int(pdf.group(6) or 0), tzinfo=timezone.utc,
            )
            if pdf.group(8):
                offset_minutes = int(pdf.group(9)) * 60 + int(pdf.group(10))
                if pdf.group(8) == "+":
                    offset_minutes *= -1
                base += timedelta(minutes=offset_minutes)
            return base
        except (ValueError, TypeError):
            return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _try_metadata_datetime(metadata: dict):
    candidates = (
        ("metadata_exif_created", (metadata.get("image") or {}).get("date_created")),
        ("metadata_pdf_created", (metadata.get("pdf") or {}).get("creation_date")),
        ("metadata_office_created", (metadata.get("office") or {}).get("created")),
    )
    for source, value in candidates:
        parsed = _parse_metadata_datetime(value)
        if parsed is not None:
            return parsed, source
    return None, None


def _parse_time(value: str) -> Optional[tuple[int, int, int]]:
    text = value.strip().lower().replace(".", ":")
    text = re.sub(r"(?<=\d)(am|pm)$", r" \1", text)
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.hour, parsed.minute, parsed.second
        except ValueError:
            continue
    return None


def _visible_datetime(
    value: str, reference_dt: Optional[datetime]
) -> Optional[tuple[datetime, bool]]:
    """Parse one visible label value and say whether it included a time."""
    match = VISIBLE_ISO_DATETIME_RE.search(value or "")
    if match:
        try:
            year = int(match.group("year"))
            if not _plausible_year(year, reference_dt):
                return None
            hour = int(match.group("hour"))
            ampm = (match.group("ampm") or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            parsed = datetime(
                year,
                int(match.group("month")),
                int(match.group("day")),
                hour,
                int(match.group("minute")),
                int(match.group("second") or 0),
                tzinfo=timezone.utc,
            )
            return parsed, True
        except (TypeError, ValueError):
            return None

    date_value = None
    for pattern in VISIBLE_DATE_PATTERNS:
        date_match = pattern.search(value or "")
        if date_match:
            date_value = date_match.group(0)
            break
    parsed_date = _parse_date(date_value, reference_dt) if date_value else None
    if parsed_date is None:
        return None

    remainder = (value or "").replace(date_value, " ", 1)
    time_match = re.search(
        r"(?<!\d)(\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?)(?!\d)",
        remainder,
        re.IGNORECASE,
    )
    parsed_time = _parse_time(time_match.group(1)) if time_match else None
    if parsed_time is None:
        return parsed_date, False
    return parsed_date.replace(
        hour=parsed_time[0], minute=parsed_time[1], second=parsed_time[2]
    ), True


def _try_labelled_timestamp(raw_text: str, reference_dt: Optional[datetime]):
    """Resolve explicit document labels before unrelated narrative dates."""
    for match in LABELLED_TIMESTAMP_RE.finditer(raw_text or ""):
        parsed = _visible_datetime(match.group("value"), reference_dt)
        if parsed is None:
            continue
        value, has_time = parsed
        return value, (
            "content_labeled_date_time" if has_time
            else "content_labeled_date_only"
        )
    return None, None


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

    dt, source = _try_labelled_timestamp(raw_text, upload_dt)
    if dt:
        return {
            "resolved_time": dt,
            "resolved_time_iso": dt.isoformat(),
            "source": source,
            "confidence": "high" if source.endswith("date_time") else "medium",
            "inferred": source.endswith("date_only"),
        }

    dt, source = _try_entity_datetime(entities, upload_dt)
    if dt:
        confidence = "high" if source == "content_date_time" else "medium"
        return {
            "resolved_time": dt,
            "resolved_time_iso": dt.isoformat(),
            "source": source,
            "confidence": confidence,
            "inferred": source != "content_date_time",
        }

    chat_resolution = _try_chat_style_timestamp(raw_text, upload_dt)
    if chat_resolution:
        chat_dt, inferred = chat_resolution
        return {
            "resolved_time": chat_dt,
            "resolved_time_iso": chat_dt.isoformat(),
            "source": "content_chat_timestamp",
            "confidence": "medium" if inferred else "high",
            "inferred": inferred,
        }

    metadata_dt, metadata_source = _try_metadata_datetime(
        evidence.get("metadata") or {}
    )
    if metadata_dt:
        return {
            "resolved_time": metadata_dt,
            "resolved_time_iso": metadata_dt.isoformat(),
            "source": metadata_source,
            "confidence": "medium",
            "inferred": False,
        }

    if upload_dt:
        return {
            "resolved_time": upload_dt,
            "resolved_time_iso": upload_dt.isoformat(),
            "source": "upload_time_fallback",
            "confidence": "low",
            "inferred": True,
        }

    return {
        "resolved_time": None,
        "resolved_time_iso": None,
        "source": "unresolved",
        "confidence": "none",
        "inferred": False,
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
            timestamp_inferred = resolution["inferred"]

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
    event_timestamps = [
        datetime.fromisoformat(event["timestamp"])
        for event in ordered
        if event["timestamp"] and event["time_source"] != "upload_time_fallback"
    ]
    acquisition_inclusive_span = (
        (max(timestamps) - min(timestamps)).total_seconds() / 3600.0
        if len(timestamps) > 1 else 0.0
    )
    span_hours = (
        (max(event_timestamps) - min(event_timestamps)).total_seconds() / 3600.0
        if len(event_timestamps) > 1 else 0.0
    )
    milestones = _milestones(ordered)
    critical_events = [event for event in ordered if event["critical"]]
    inferred_count = sum(1 for event in ordered if event["timestamp_inferred"])
    fallback_count = sum(
        1 for event in ordered if event["time_source"] == "upload_time_fallback"
    )
    direct_count = len(resolved) - inferred_count
    staged_events = [event for event in ordered if event["stages"]]
    progression_assessable = bool(staged_events) and all(
        event["timestamp"] and event["time_source"] != "upload_time_fallback"
        for event in staged_events
    )
    summary = (
        f"{_count(len(ordered), 'event')}; {_count(len(resolved), 'timestamp')} "
        f"resolved ({direct_count} non-inferred, {inferred_count} inferred, "
        f"including {fallback_count} acquisition-time "
        f"{_plural('fallback', fallback_count)}); "
        f"{_count(len(unresolved), 'timestamp')} unresolved."
    )
    if len(event_timestamps) > 1:
        summary += (
            f" Content/metadata event times span {span_hours:.1f} "
            f"{_plural('hour', span_hours)}."
        )
    if progression:
        summary += " Keyword-derived stage order: " + " -> ".join(progression) + "."
        if not progression_assessable:
            summary += " This order is provisional because one or more stages use acquisition time."

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
            "inferred_event_count": float(inferred_count),
            "non_inferred_event_count": float(direct_count),
            "acquisition_fallback_count": float(fallback_count),
            "progression_assessable": float(progression_assessable),
            "stage_count": float(len(attack_stages)),
            "critical_event_count": float(len(critical_events)),
            # Retained as the acquisition-inclusive value for schema/backward
            # compatibility. Consumers that need event chronology should use
            # event_time_span_hours, which excludes intake-time fallbacks.
            "timeline_span_hours": round(acquisition_inclusive_span, 2),
            "event_time_span_hours": round(span_hours, 2),
            "acquisition_inclusive_span_hours": round(
                acquisition_inclusive_span, 2
            ),
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
