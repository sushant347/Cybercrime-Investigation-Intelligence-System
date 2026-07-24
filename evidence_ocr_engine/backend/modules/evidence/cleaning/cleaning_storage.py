"""CSV persistence for cleaning results (Repository pattern).

Adds two repositories (``entities.csv``, ``keyword_statistics.csv``) and an
augmenter that extends ``ocr_results.csv`` from Prompt 1 with cleaning
columns. The augmenter migrates the existing header in place (old rows get
empty values for the new columns), so Prompt 1 code keeps working unchanged.
"""

from __future__ import annotations

import csv
from typing import Dict, List

from ..config import EvidenceConfig
from ..csv_storage import BaseCSVRepository
from ..logger import get_logger
from ..utils import StorageError, utc_now_iso
from .cleaning_schemas import CleaningResult


class EntityRepository(BaseCSVRepository):
    """One row per extracted entity occurrence -> ``storage/entities.csv``."""

    fieldnames = (
        "case_id", "evidence_id", "entity_type", "value", "normalized",
        "extracted_at",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.storage_dir / "entities.csv")

    def add_result(self, result: CleaningResult) -> int:
        """Persist every entity of a cleaning result; returns rows written.

        Idempotent per evidence item: any existing rows for this
        ``(case_id, evidence_id)`` are removed first so re-processing (e.g. a
        second API upload to the same case, which re-cleans every item)
        replaces the entity rows instead of duplicating them.
        """
        self.delete_where(
            case_id=result.case_id, evidence_id=result.evidence_id
        )
        written = 0
        timestamp = utc_now_iso()
        for entity_type, records in result.entities.items():
            for record in records:
                self.append(
                    {
                        "case_id": result.case_id,
                        "evidence_id": result.evidence_id,
                        "entity_type": entity_type,
                        "value": record.value,
                        "normalized": record.normalized,
                        "extracted_at": timestamp,
                    }
                )
                written += 1
        return written


class KeywordStatisticsRepository(BaseCSVRepository):
    """Keyword frequencies + risk signals -> ``storage/keyword_statistics.csv``."""

    fieldnames = (
        "case_id", "evidence_id", "keyword", "count", "category", "analyzed_at",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.storage_dir / "keyword_statistics.csv")

    def add_result(self, result: CleaningResult) -> int:
        from .keyword_analyzer import KEYWORD_GROUPS  # avoid import cycle

        # Idempotent per evidence item (see EntityRepository.add_result).
        self.delete_where(
            case_id=result.case_id, evidence_id=result.evidence_id
        )
        written = 0
        timestamp = utc_now_iso()
        for keyword, count in result.keywords.items():
            category = KEYWORD_GROUPS.get(keyword, ("", ()))[0]
            self.append(
                {
                    "case_id": result.case_id,
                    "evidence_id": result.evidence_id,
                    "keyword": keyword,
                    "count": str(count),
                    "category": category,
                    "analyzed_at": timestamp,
                }
            )
            written += 1
        for category, count in result.risk_signals.items():
            self.append(
                {
                    "case_id": result.case_id,
                    "evidence_id": result.evidence_id,
                    "keyword": f"__risk_signal__{category}",
                    "count": str(count),
                    "category": category,
                    "analyzed_at": timestamp,
                }
            )
            written += 1
        return written


class OCRResultsAugmenter:
    """Adds cleaning columns to Prompt 1's ``ocr_results.csv`` rows.

    New columns: ``language``, ``cleaned_text_preview``, ``entity_count``,
    ``keyword_hits``, ``cleaned_at``. The header is migrated on first use.
    """

    _NEW_COLUMNS = (
        "language", "cleaned_text_preview", "entity_count", "keyword_hits",
        "cleaned_at",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        self._path = config.ocr_results_csv
        self._log = get_logger("cleaning.csv.ocr_results")

    def update_row(self, result: CleaningResult) -> bool:
        """Write cleaning summary into the evidence's ocr_results row.

        Returns ``True`` when a matching row was found and updated.
        """
        rows, fieldnames = self._read()
        for column in self._NEW_COLUMNS:
            if column not in fieldnames:
                fieldnames.append(column)

        updated = False
        preview = result.cleaned_text[:200].replace("\n", " ")
        for row in rows:
            if row.get("evidence_id") == result.evidence_id:
                row["language"] = result.language
                row["cleaned_text_preview"] = preview
                row["entity_count"] = str(result.statistics.entity_count)
                row["keyword_hits"] = str(sum(result.keywords.values()))
                row["cleaned_at"] = utc_now_iso()
                updated = True
        self._write(rows, fieldnames)
        if not updated:
            self._log.warning("no ocr_results row for %s", result.evidence_id)
        return updated

    # ---------------------------------------------------------------- internal

    def _read(self) -> tuple[List[Dict[str, str]], List[str]]:
        if not self._path.exists():
            raise StorageError(
                f"'{self._path}' not found - run Prompt 1 (OCR) first"
            )
        with open(self._path, "r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader), list(reader.fieldnames or [])

    def _write(self, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
        tmp_path = self._path.with_suffix(".csv.tmp")
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                        restval="")
                writer.writeheader()
                writer.writerows(rows)
            tmp_path.replace(self._path)
        except OSError as exc:
            raise StorageError(f"Cannot rewrite '{self._path}': {exc}") from exc
