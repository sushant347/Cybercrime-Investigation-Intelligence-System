"""Application service: connects the enhancement framework to case storage.

Reads each evidence item's ``cleaning.cleaned_text`` (Prompt 2) and the OCR
``pages`` confidences (Prompt 1) from the case JSON, runs the enhancement
pipeline and persists:

* ``evidence[i]["enhancement"]`` in the case JSON (raw_text and cleaned_text
  remain untouched - the enhancement carries its own copies),
* one row per correction into ``storage/ocr_corrections.csv``.
"""

from __future__ import annotations

from typing import List, Optional

from ..config import EvidenceConfig
from ..json_storage import JSONCaseStorage
from ..logger import StageTimer, get_logger
from ..utils import EvidenceError, utc_now_iso
from .correction_logger import CorrectionLogRepository
from .enhancement_pipeline import EnhancementPipeline
from .enhancement_schemas import EnhancementResult


class EnhancementService:
    """Enhances cleaned OCR text for whole cases or single evidence items."""

    def __init__(
        self,
        config: EvidenceConfig,
        pipeline: Optional[EnhancementPipeline] = None,
        json_storage: Optional[JSONCaseStorage] = None,
        correction_log: Optional[CorrectionLogRepository] = None,
    ) -> None:
        self._cfg = config
        self._pipeline = pipeline or EnhancementPipeline()
        self._json = json_storage or JSONCaseStorage(config)
        self._corrections = correction_log or CorrectionLogRepository(config)
        self._log = get_logger("enhancement.service", config.log_dir)

    def enhance_case(self, case_id: str) -> List[EnhancementResult]:
        """Enhance every cleaned evidence item of ``case_id``."""
        document = self._load(case_id)
        results: List[EnhancementResult] = []
        with StageTimer(self._log, f"enhance case {case_id}") as timer:
            for evidence in document.get("evidence", []):
                result = self._enhance_evidence_dict(case_id, evidence)
                if result is not None:
                    results.append(result)
            self._save(document)
        self._log.info("case %s enhanced: %d item(s) in %.0f ms",
                       case_id, len(results), timer.elapsed_ms)
        return results

    def enhance_evidence(self, case_id: str, evidence_id: str) -> EnhancementResult:
        """Enhance a single evidence item."""
        document = self._load(case_id)
        for evidence in document.get("evidence", []):
            if evidence.get("evidence_id") == evidence_id:
                result = self._enhance_evidence_dict(case_id, evidence)
                if result is None:
                    raise EvidenceError(
                        f"Evidence '{evidence_id}' has no cleaning section - "
                        "run Prompt 2 (clean) first"
                    )
                self._save(document)
                return result
        raise EvidenceError(f"Evidence '{evidence_id}' not found in {case_id}")

    # ---------------------------------------------------------------- internal

    def _enhance_evidence_dict(
        self, case_id: str, evidence: dict
    ) -> Optional[EnhancementResult]:
        """Enhance one evidence dict in place (adds 'enhancement' section)."""
        cleaning = evidence.get("cleaning")
        if not cleaning or "cleaned_text" not in cleaning:
            self._log.warning(
                "%s: skipped - no cleaning section (run 'clean' first)",
                evidence.get("evidence_id", "?"),
            )
            return None

        result = self._pipeline.enhance(
            cleaned_text=cleaning["cleaned_text"],
            ocr_pages=evidence.get("pages"),
            case_id=case_id,
            evidence_id=evidence.get("evidence_id", ""),
        )
        # Forensic invariant: raw_text (Prompt 1) and cleaned_text (Prompt 2)
        # sections are untouched; enhancement is attached as a new section.
        evidence["enhancement"] = result.model_dump()
        rows = self._corrections.log_corrections(
            case_id, result.evidence_id, result.corrections
        )
        self._log.info("%s: %d corrections logged", result.evidence_id, rows)
        return result

    def _load(self, case_id: str) -> dict:
        document = self._json.load_case(case_id)
        if document is None:
            raise EvidenceError(f"Unknown case '{case_id}' - no JSON document")
        return document

    def _save(self, document: dict) -> None:
        document["updated_at"] = utc_now_iso()
        self._json._atomic_write(self._json.case_file(document["case_id"]),
                                 document)
