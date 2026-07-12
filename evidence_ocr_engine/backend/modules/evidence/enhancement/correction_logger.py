"""Correction audit log: professional logging + ``ocr_corrections.csv``.

Every correction the framework applies is persisted with case/evidence
provenance, the OCR confidence that permitted it, the rule that produced it
and a timestamp - the complete audit trail required to defend the enhanced
text in a forensic setting.
"""

from __future__ import annotations

from typing import Iterable

from ..config import EvidenceConfig
from ..csv_storage import BaseCSVRepository
from ..logger import get_logger
from ..utils import utc_now_iso
from .enhancement_schemas import CorrectionEntry


class CorrectionLogRepository(BaseCSVRepository):
    """One row per applied correction -> ``storage/ocr_corrections.csv``."""

    fieldnames = (
        "case_id", "evidence_id", "original", "corrected", "confidence",
        "rule", "character_replacement", "dictionary_match", "language",
        "context_score", "line", "timestamp",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.storage_dir / "ocr_corrections.csv")
        self._logger = get_logger("enhancement.correction_log")
        self._migrate_header()

    def _migrate_header(self) -> None:
        """Rewrite the CSV when older headers lack the newer columns."""
        rows = self.read_all()
        import csv as _csv
        with open(self.path, "r", newline="", encoding="utf-8") as handle:
            existing = next(_csv.reader(handle), [])
        if tuple(existing) != tuple(self.fieldnames):
            self.overwrite_all(rows)

    def log_corrections(
        self,
        case_id: str,
        evidence_id: str,
        corrections: Iterable[CorrectionEntry],
    ) -> int:
        """Persist every correction; returns the number of rows written."""
        timestamp = utc_now_iso()
        written = 0
        for entry in corrections:
            self.append(
                {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "original": entry.original,
                    "corrected": entry.corrected,
                    "confidence": f"{entry.confidence:.4f}",
                    "rule": entry.rule,
                    "character_replacement": entry.character_replacement,
                    "dictionary_match": entry.dictionary_match,
                    "language": entry.language,
                    "context_score": f"{entry.context_score:.3f}",
                    "line": str(entry.line),
                    "timestamp": timestamp,
                }
            )
            self._logger.info(
                "%s/%s: %r -> %r (rule=%s, conf=%.2f)",
                case_id, evidence_id, entry.original, entry.corrected,
                entry.rule, entry.confidence,
            )
            written += 1
        return written
