"""Application service: connects the semantic engine to case storage.

Reads each evidence item's ``enhancement.enhanced_text`` (Prompt 2.5) from
the case JSON, runs the semantic pipeline, and appends a
``semantic_correction`` section - leaving raw/cleaned/enhanced text and every
existing field untouched (forensic invariant + backward compatibility).
"""

from __future__ import annotations

from typing import List, Optional

from ..config import EvidenceConfig
from ..json_storage import JSONCaseStorage
from ..logger import StageTimer, get_logger
from ..utils import EvidenceError, utc_now_iso
from .semantic_pipeline import SemanticCorrectionPipeline
from .semantic_schemas import SemanticResult


class SemanticCorrectionService:
    """Runs semantic correction over whole cases or single evidence items."""

    def __init__(
        self,
        config: EvidenceConfig,
        pipeline: Optional[SemanticCorrectionPipeline] = None,
        json_storage: Optional[JSONCaseStorage] = None,
    ) -> None:
        self._cfg = config
        self._pipeline = pipeline or SemanticCorrectionPipeline()
        self._json = json_storage or JSONCaseStorage(config)
        self._log = get_logger("semantic.service", config.log_dir)

    def correct_case(self, case_id: str) -> List[SemanticResult]:
        document = self._load(case_id)
        results: List[SemanticResult] = []
        with StageTimer(self._log, f"semantic case {case_id}") as timer:
            for evidence in document.get("evidence", []):
                result = self._correct_evidence_dict(case_id, evidence)
                if result is not None:
                    results.append(result)
            self._save(document)
        self._log.info("case %s semantically corrected: %d item(s) in %.0f ms",
                       case_id, len(results), timer.elapsed_ms)
        return results

    def correct_evidence(self, case_id: str, evidence_id: str) -> SemanticResult:
        document = self._load(case_id)
        for evidence in document.get("evidence", []):
            if evidence.get("evidence_id") == evidence_id:
                result = self._correct_evidence_dict(case_id, evidence)
                if result is None:
                    raise EvidenceError(
                        f"Evidence '{evidence_id}' has no enhancement section - "
                        "run Prompt 2.5 (enhance) first")
                self._save(document)
                return result
        raise EvidenceError(f"Evidence '{evidence_id}' not found in {case_id}")

    # ---------------------------------------------------------------- internal

    def _correct_evidence_dict(self, case_id: str, evidence: dict) -> Optional[SemanticResult]:
        enhancement = evidence.get("enhancement")
        if not enhancement or "enhanced_text" not in enhancement:
            self._log.warning("%s: skipped - no enhancement section",
                              evidence.get("evidence_id", "?"))
            return None
        result = self._pipeline.correct(
            enhanced_text=enhancement["enhanced_text"],
            case_id=case_id, evidence_id=evidence.get("evidence_id", ""))
        # Append-only: existing fields untouched.
        evidence["semantic_correction"] = result.model_dump()
        return result

    def _load(self, case_id: str) -> dict:
        document = self._json.load_case(case_id)
        if document is None:
            raise EvidenceError(f"Unknown case '{case_id}' - no JSON document")
        return document

    def _save(self, document: dict) -> None:
        document["updated_at"] = utc_now_iso()
        self._json._atomic_write(self._json.case_file(document["case_id"]), document)
