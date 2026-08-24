"""Read-only data gateway over all existing CIIE storage.

Every Phase-2 module obtains its inputs exclusively through
:class:`CaseDataRepository`, so the analytical engines are decoupled from the
physical storage layout (Repository Pattern) and existing files are opened
strictly read-only.

Sources consumed (never written):

* ``storage/evidence.csv``                    chain-of-custody register
* ``storage/entities.csv``                    extracted entities per evidence
* ``storage/json/<CASE_ID>.json``             full OCR output per case
* ``storage/forensics/<EVID>/<report>.json``  Phase-1 forensic reports
* optional threat-intel indicator file       (config.threat_intel_json)
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.modules.evidence.logger import get_logger
from .config import InvestigationConfig

_VERSION_RE = re.compile(r"_v(\d+)$")

#: ``path -> (mtime, rows)`` for the storage CSVs this gateway reads. Process
#: local and read-only from the caller's point of view: rows are never handed
#: out for mutation (every consumer copies fields into its own model), so a
#: shared list is safe and avoids re-parsing a file that has not changed.
_CSV_CACHE: Dict[str, tuple] = {}

#: ``path -> (mtime, payload)`` for parsed Phase-1 forensic reports. Same
#: contract as ``_CSV_CACHE``: payloads are treated as read-only by every
#: consumer, and a rewritten report changes mtime.
_REPORT_CACHE: Dict[str, tuple] = {}


@dataclass(frozen=True)
class EntityRecord:
    """One extracted entity attributed to an evidence item."""

    case_id: str
    evidence_id: str
    entity_type: str
    value: str
    normalized: str


@dataclass
class EvidenceContext:
    """Everything Phase 2 knows about one evidence item (read-only view)."""

    evidence_id: str
    case_id: str
    file_name: str = ""
    sha256: str = ""
    upload_time: str = ""
    status: str = ""
    hash_verified: Optional[bool] = None
    raw_text: str = ""
    #: ``None`` means no OCR result was ever recorded for this item, which is
    #: not the same fact as OCR running and scoring zero. Collapsing the two
    #: made "text read 0%" claim the engine read the file and got nothing, and
    #: dragged every mean that averaged over it. Phase 1's own confidence
    #: engine already models the distinction this way.
    ocr_confidence: Optional[float] = None
    entities: List[EntityRecord] = field(default_factory=list)
    #: Latest Phase-1 report payloads keyed by report name (may be empty).
    forensics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def entity_values(self, entity_type: str) -> List[str]:
        return [e.normalized or e.value for e in self.entities
                if e.entity_type == entity_type]

    @property
    def upload_datetime(self) -> Optional[datetime]:
        return parse_iso(self.upload_time)


class ThreatIntelProvider:
    """Explainable threat-intel lookups from a static indicator file.

    File format (optional; absence simply disables the factor)::

        {"indicators": {"bad-domain.top": {"verdict": "malicious",
                                            "source": "PhishTank"}}}
    """

    source_name = "static-indicators"

    def __init__(self, path: Path) -> None:
        self._log = get_logger("investigation.threat_intel")
        self._indicators: Dict[str, Dict[str, Any]] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._indicators = {
                    str(k).lower(): dict(v)
                    for k, v in data.get("indicators", {}).items()
                }
                self._log.info("threat intel loaded: %d indicators", len(self._indicators))
            except (OSError, json.JSONDecodeError) as exc:
                self._log.warning("threat intel file unreadable: %s", exc)

    @property
    def available(self) -> bool:
        return bool(self._indicators)

    def lookup(self, value: str) -> Optional[Dict[str, Any]]:
        """Verdict for a URL/domain/value, matching full value then domain."""
        needle = value.lower().strip()
        if needle in self._indicators:
            return self._indicators[needle]
        domain = _domain_of(needle)
        if domain and domain in self._indicators:
            return self._indicators[domain]
        return None

    def is_malicious(self, value: str) -> bool:
        hit = self.lookup(value)
        return bool(hit) and str(hit.get("verdict", "")).lower() in {
            "malicious", "phishing", "scam", "fraud",
        }


def default_threat_intel(config: InvestigationConfig):
    """The provider a case gets when the caller injects nothing.

    Curated indicators first, rule-based scoring behind them. Pairing the two
    means the factor is *never* unavailable: before this, a deployment without
    an indicator file (the default - the file is not shipped) produced
    ``intel_available = 0`` and an empty threat panel on every case, which
    reads as "nothing suspicious found" when the truth was "nothing was ever
    checked".
    """
    from ..threat.heuristics import (
        ChainedThreatIntelProvider,
        HeuristicThreatIntelProvider,
    )

    return ChainedThreatIntelProvider(
        ThreatIntelProvider(config.threat_intel_json),
        HeuristicThreatIntelProvider(),
    )


class CaseDataRepository:
    """Read-only access to every input a Phase-2 analysis needs."""

    #: Phase-1 report names surfaced on the evidence context.
    FORENSIC_REPORTS = (
        "quality_report", "forgery_report", "metadata_report",
        "file_fingerprint", "logo_detections", "ocr_fusion",
        "evidence_confidence",
    )

    def __init__(self, config: InvestigationConfig,
                 threat_intel: Optional[ThreatIntelProvider] = None) -> None:
        self._cfg = config
        self._log = get_logger("investigation.data")
        self.threat_intel = threat_intel or default_threat_intel(config)

    # ------------------------------------------------------------------ cases

    def list_case_ids(self) -> List[str]:
        seen: List[str] = []
        for row in self._read_csv(self._cfg.evidence_csv):
            case_id = row.get("case_id", "")
            if case_id and case_id not in seen:
                seen.append(case_id)
        return seen

    def case_exists(self, case_id: str) -> bool:
        return any(row.get("case_id") == case_id
                   for row in self._read_csv(self._cfg.evidence_csv))

    def load_case_evidence(self, case_id: str) -> List[EvidenceContext]:
        """Full evidence contexts for one case, upload order preserved."""
        contexts: Dict[str, EvidenceContext] = {}
        for row in self._read_csv(self._cfg.evidence_csv):
            if row.get("case_id") != case_id:
                continue
            evidence_id = row.get("evidence_id", "")
            contexts[evidence_id] = EvidenceContext(
                evidence_id=evidence_id,
                case_id=case_id,
                file_name=row.get("original_file_name", ""),
                sha256=row.get("sha256_before", ""),
                upload_time=row.get("upload_time", ""),
                status=row.get("status", ""),
                hash_verified=_to_bool(row.get("hash_verified")),
            )
        self._attach_ocr(case_id, contexts)
        self._attach_entities(case_id, contexts)
        for context in contexts.values():
            context.forensics = self._load_forensics(context.evidence_id)
        ordered = sorted(contexts.values(), key=lambda c: c.upload_time or "")
        return ordered

    # ---------------------------------------------------------------- helpers

    def _attach_ocr(self, case_id: str, contexts: Dict[str, EvidenceContext]) -> None:
        """Attach OCR text and confidence to each evidence context.

        The case JSON is the only place the *full* recognised text lives, but
        it is also the first artifact to disappear when a case's working files
        are cleared - and when it did, every item silently kept the 0.0
        default, so a case whose text was read at 0.99 confidence reported
        "0% text read" across the board. ``ocr_results.csv`` survives that
        clearance and holds the same per-item confidence, so it seeds every
        context first and the JSON overwrites it where the JSON still exists.
        Only the confidence is recovered this way: the CSV stores a truncated
        preview, never the full text, and passing a preview off as the text
        would quietly narrow keyword screening instead of reporting a gap.
        """
        self._attach_ocr_confidence_from_csv(case_id, contexts)

        path = self._cfg.case_json_dir / f"{case_id}.json"
        if not path.exists():
            return
        # The case OCR document holds the raw text of every evidence item and
        # is the largest file a case load touches; memoised on mtime like the
        # rest of the gateway's reads.
        try:
            key = str(path)
            mtime = path.stat().st_mtime
            cached = _REPORT_CACHE.get(key)
            if cached is not None and cached[0] == mtime:
                document = cached[1]
            else:
                document = json.loads(path.read_text(encoding="utf-8"))
                _REPORT_CACHE[key] = (mtime, document)
        except (OSError, json.JSONDecodeError) as exc:
            self._log.warning("case JSON unreadable (%s): %s", path, exc)
            return
        for item in document.get("evidence", []):
            context = contexts.get(item.get("evidence_id", ""))
            if context is None:
                continue
            context.raw_text = item.get("raw_text", "") or ""
            recorded = item.get("average_confidence")
            if recorded is not None:
                context.ocr_confidence = float(recorded or 0.0)

    def _attach_ocr_confidence_from_csv(
        self, case_id: str, contexts: Dict[str, EvidenceContext]
    ) -> None:
        """Seed ``ocr_confidence`` from the OCR results register."""
        csv_path = getattr(self._cfg, "ocr_results_csv", None)
        if csv_path is None or not Path(csv_path).exists():
            return
        for row in self._read_csv(Path(csv_path)):
            if row.get("case_id") != case_id:
                continue
            context = contexts.get(row.get("evidence_id", ""))
            if context is None:
                continue
            recorded = row.get("average_confidence")
            if recorded in (None, ""):
                continue
            try:
                context.ocr_confidence = float(recorded)
            except (TypeError, ValueError):
                # A malformed row must not cost the whole case its figures.
                continue

    def _attach_entities(self, case_id: str,
                         contexts: Dict[str, EvidenceContext]) -> None:
        for row in self._read_csv(self._cfg.entities_csv):
            if row.get("case_id") != case_id:
                continue
            context = contexts.get(row.get("evidence_id", ""))
            if context is None:
                continue
            context.entities.append(EntityRecord(
                case_id=case_id,
                evidence_id=context.evidence_id,
                entity_type=row.get("entity_type", ""),
                value=row.get("value", ""),
                normalized=row.get("normalized", row.get("value", "")),
            ))

    def _load_forensics(self, evidence_id: str) -> Dict[str, Dict[str, Any]]:
        """Latest version of each Phase-1 report payload for one evidence.

        This is the hot path of the whole Phase-2 stack: a case load calls it
        once per evidence item, and a single analysis loads the case six times
        over (correlation, cross-case, timeline, graph, analytics, report). The
        previous implementation ran **one glob per report type** - seven
        directory scans per item - and re-read and re-parsed every JSON on
        every load. Profiling a normal 8-item case put 98% of case-load time
        right here, ~1.5 s per load, which is most of the "system feels slow".

        Two changes: one directory listing serves all seven report types, and
        parsed payloads are memoised per ``(path, mtime)`` so repeat loads of
        an unchanged report cost nothing. Freshness is unaffected - a report
        rewritten by the forensics pipeline gets a new mtime.
        """
        directory = self._cfg.forensics_dir / evidence_id
        try:
            entries = list(directory.iterdir())
        except (OSError, NotADirectoryError):
            return {}

        wanted = set(self.FORENSIC_REPORTS)
        latest: Dict[str, tuple] = {}          # report name -> (version, path)
        for path in entries:
            if path.suffix != ".json":
                continue
            stem = path.stem
            match = _VERSION_RE.search(stem)
            if match:
                name, version = stem[: match.start()], int(match.group(1))
            else:
                name, version = stem, 1
            if name not in wanted:
                continue
            current = latest.get(name)
            if current is None or version > current[0]:
                latest[name] = (version, path)

        reports: Dict[str, Dict[str, Any]] = {}
        for name, (_version, path) in latest.items():
            try:
                key = str(path)
                mtime = path.stat().st_mtime
                cached = _REPORT_CACHE.get(key)
                if cached is not None and cached[0] == mtime:
                    reports[name] = cached[1]
                    continue
                document = json.loads(path.read_text(encoding="utf-8"))
                payload = document.get("report", document)
                _REPORT_CACHE[key] = (mtime, payload)
                reports[name] = payload
            except (OSError, json.JSONDecodeError) as exc:
                self._log.warning("forensic report unreadable (%s): %s", path, exc)
        return reports

    def _read_csv(self, path: Path) -> List[Dict[str, str]]:
        """Read a storage CSV, memoised on the file's modification time.

        ``entities.csv`` is a single file for the whole system and is re-read
        in full for every case load - and a Phase-2 run loads the case several
        times over (correlation, cross-case, timeline, graph, analytics,
        report). Keying the cache on mtime keeps it exactly as fresh as the
        file while removing the repeated parse; any write through the engine
        bumps mtime and invalidates it.
        """
        if not path.exists():
            return []
        try:
            mtime = path.stat().st_mtime
            cached = _CSV_CACHE.get(str(path))
            if cached is not None and cached[0] == mtime:
                return cached[1]
            with open(path, "r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            _CSV_CACHE[str(path)] = (mtime, rows)
            return rows
        except OSError as exc:
            self._log.warning("csv unreadable (%s): %s", path, exc)
            return []


# ------------------------------------------------------------------ utilities


def parse_iso(value: str) -> Optional[datetime]:
    """Tolerant ISO-8601 parser returning timezone-aware UTC datetimes."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _domain_of(value: str) -> str:
    text = value.lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0]
    return text if "." in text else ""


def _to_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    return str(value).strip().lower() in {"true", "1", "yes"}
