"""Read-only data gateway over all existing CIIS storage.

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

from ..evidence.logger import get_logger
from .config import InvestigationConfig

_VERSION_RE = re.compile(r"_v(\d+)$")


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
    ocr_confidence: float = 0.0
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
        self.threat_intel = threat_intel or ThreatIntelProvider(config.threat_intel_json)

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
        path = self._cfg.case_json_dir / f"{case_id}.json"
        if not path.exists():
            return
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._log.warning("case JSON unreadable (%s): %s", path, exc)
            return
        for item in document.get("evidence", []):
            context = contexts.get(item.get("evidence_id", ""))
            if context is None:
                continue
            context.raw_text = item.get("raw_text", "") or ""
            context.ocr_confidence = float(item.get("average_confidence", 0.0) or 0.0)

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
        """Latest version of each Phase-1 report payload for one evidence."""
        directory = self._cfg.forensics_dir / evidence_id
        if not directory.is_dir():
            return {}
        reports: Dict[str, Dict[str, Any]] = {}
        for name in self.FORENSIC_REPORTS:
            latest: Optional[tuple[int, Path]] = None
            for path in directory.glob(f"{name}*.json"):
                stem = path.stem
                if stem == name:
                    version = 1
                else:
                    match = _VERSION_RE.search(stem)
                    if not match or stem != f"{name}_v{match.group(1)}":
                        continue
                    version = int(match.group(1))
                if latest is None or version > latest[0]:
                    latest = (version, path)
            if latest is None:
                continue
            try:
                document = json.loads(latest[1].read_text(encoding="utf-8"))
                reports[name] = document.get("report", document)
            except (OSError, json.JSONDecodeError) as exc:
                self._log.warning("forensic report unreadable (%s): %s", latest[1], exc)
        return reports

    def _read_csv(self, path: Path) -> List[Dict[str, str]]:
        if not path.exists():
            return []
        try:
            with open(path, "r", newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))
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
