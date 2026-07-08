"""Application service: connects the cleaning pipeline to Prompt 1 storage.

Reads OCR output from the per-case JSON documents produced by Prompt 1,
cleans each evidence item, and persists:

* the cleaning result into the case JSON (``evidence[i]["cleaning"]``),
  leaving ``raw_text`` and every Prompt 1 field untouched,
* one row per entity into ``storage/entities.csv``,
* keyword frequencies + risk signals into ``storage/keyword_statistics.csv``,
* a cleaning summary into the existing ``storage/ocr_results.csv`` row.
"""

from __future__ import annotations

from typing import List, Optional

from ..config import EvidenceConfig
from ..json_storage import JSONCaseStorage
from ..logger import StageTimer, get_logger
from ..utils import EvidenceError, StorageError
from .cleaning_pipeline import CleaningPipeline
from .cleaning_schemas import CleaningResult
from .cleaning_storage import (
    EntityRepository,
    KeywordStatisticsRepository,
    OCRResultsAugmenter,
)


class CleaningService:
    """Cleans OCR output for whole cases or single evidence items."""

    def __init__(
        self,
        config: EvidenceConfig,
        pipeline: Optional[CleaningPipeline] = None,
        json_storage: Optional[JSONCaseStorage] = None,
        entity_repo: Optional[EntityRepository] = None,
        keyword_repo: Optional[KeywordStatisticsRepository] = None,
        ocr_augmenter: Optional[OCRResultsAugmenter] = None,
    ) -> None:
        self._cfg = config
        self._pipeline = pipeline or CleaningPipeline()
        self._json = json_storage or JSONCaseStorage(config)
        self._entities = entity_repo or EntityRepository(config)
        self._keywords = keyword_repo or KeywordStatisticsRepository(config)
        self._augmenter = ocr_augmenter or OCRResultsAugmenter(config)
        self._log = get_logger("cleaning.service", config.log_dir)

    def clean_case(self, case_id: str) -> List[CleaningResult]:
        """Clean every evidence item of ``case_id`` and persist all outputs."""
        document = self._json.load_case(case_id)
        if document is None:
            raise EvidenceError(f"Unknown case '{case_id}' - no JSON document")

        results: List[CleaningResult] = []
        with StageTimer(self._log, f"clean case {case_id}") as timer:
            for evidence in document.get("evidence", []):
                results.append(self._clean_evidence_dict(case_id, evidence))
            self._save_document(document)
        self._log.info(
            "case %s cleaned: %d evidence item(s) in %.0f ms",
            case_id, len(results), timer.elapsed_ms,
        )
        return results

    def clean_evidence(self, case_id: str, evidence_id: str) -> CleaningResult:
        """Clean a single evidence item of a case."""
        document = self._json.load_case(case_id)
        if document is None:
            raise EvidenceError(f"Unknown case '{case_id}' - no JSON document")
        for evidence in document.get("evidence", []):
            if evidence.get("evidence_id") == evidence_id:
                result = self._clean_evidence_dict(case_id, evidence)
                self._save_document(document)
                return result
        raise EvidenceError(f"Evidence '{evidence_id}' not found in {case_id}")

    # ---------------------------------------------------------------- internal

    def _clean_evidence_dict(self, case_id: str, evidence: dict) -> CleaningResult:
        """Clean one evidence dict in place (adds the 'cleaning' section)."""
        evidence_id = evidence.get("evidence_id", "")
        raw_text = evidence.get("raw_text", "")

        result = self._pipeline.clean(raw_text, case_id=case_id,
                                      evidence_id=evidence_id)

        # Forensic invariant: Prompt 1 fields are never touched; the cleaning
        # result is attached as a new section carrying its own raw_text copy.
        evidence["cleaning"] = result.model_dump()

        entity_rows = self._entities.add_result(result)
        keyword_rows = self._keywords.add_result(result)
        self._augmenter.update_row(result)
        self._log.info(
            "%s: language=%s, %d entity rows, %d keyword rows",
            evidence_id, result.language, entity_rows, keyword_rows,
        )
        return result

    def _save_document(self, document: dict) -> None:
        """Atomically rewrite the case JSON via the Prompt 1 storage layer."""
        from ..utils import utc_now_iso

        document["updated_at"] = utc_now_iso()
        path = self._json.case_file(document["case_id"])
        try:
            self._json._atomic_write(path, document)  # reuse atomic writer
        except StorageError:
            raise
