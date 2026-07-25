"""End-to-end pipeline orchestrator (merge convenience, additive).

Runs the full post-OCR chain for a case in the correct merged order by
delegating to the EXISTING services - it neither reimplements nor modifies
any of them:

    OCR (already done)  →  CleaningService.clean_case
                        →  EnhancementService.enhance_case
                        →  SemanticCorrectionService.correct_case
                           (semantic_text → entity extraction, appended)

Each stage reads the previous stage's section from the case JSON and appends
its own; all forensic invariants and JSON contracts are preserved. This class
exists only so investigators can run one command instead of three.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import EvidenceConfig
from ..logger import StageTimer, get_logger
from .semantic_pipeline import SemanticCorrectionPipeline
from .semantic_service import SemanticCorrectionService


class EvidenceProcessingOrchestrator:
    """Chains cleaning → enhancement → semantic correction for a case."""

    def __init__(
        self,
        config: EvidenceConfig,
        cleaning_service: object = None,
        enhancement_service: object = None,
        semantic_service: Optional[SemanticCorrectionService] = None,
        semantic_pipeline: Optional[SemanticCorrectionPipeline] = None,
    ) -> None:
        self._cfg = config
        # Lazy imports keep this module independent and import-light.
        if cleaning_service is None:
            from ..cleaning.cleaning_service import CleaningService
            cleaning_service = CleaningService(config)
        if enhancement_service is None:
            from ..enhancement.enhancement_service import EnhancementService
            enhancement_service = EnhancementService(config)
        self._clean = cleaning_service
        self._enhance = enhancement_service
        self._semantic = semantic_service or SemanticCorrectionService(
            config, pipeline=semantic_pipeline)
        self._log = get_logger("semantic.orchestrator", config.log_dir)

    def process_case(self, case_id: str) -> Dict[str, Any]:
        """Run the full chain over ``case_id``; returns a per-stage summary."""
        summary: Dict[str, Any] = {"case_id": case_id, "stages": {}}
        with StageTimer(self._log, f"orchestrate {case_id}") as timer:
            cleaned = self._clean.clean_case(case_id)
            enhanced = self._enhance.enhance_case(case_id)
            semantic = self._semantic.correct_case(case_id)
        summary["stages"] = {
            "cleaning": len(cleaned),
            "enhancement": len(enhanced),
            "semantic": len(semantic),
        }
        summary["semantic_results"] = semantic
        summary["duration_ms"] = round(timer.elapsed_ms, 1)
        self._log.info("orchestrated %s: clean=%d enhance=%d semantic=%d in %.0f ms",
                       case_id, len(cleaned), len(enhanced), len(semantic),
                       timer.elapsed_ms)
        return summary

    def process_evidence(self, case_id: str, evidence_id: str) -> Dict[str, Any]:
        """Run the full chain for ONE evidence item of a case.

        Same contract as :meth:`process_case`, but scoped to a single
        ``evidence_id``. This is what incremental uploads should use: cleaning,
        enhancement and semantic correction are per-item operations, so
        re-running them over the whole case on every upload made the n-th
        upload do n items' worth of work (O(n^2) across a case's lifetime)
        for identical results — already-processed items are simply rewritten.
        The CSV side-effects (entities.csv, keyword_statistics.csv) are
        idempotent per (case_id, evidence_id) either way.
        """
        summary: Dict[str, Any] = {"case_id": case_id, "stages": {}}
        with StageTimer(self._log, f"orchestrate {case_id}/{evidence_id}") as timer:
            self._clean.clean_evidence(case_id, evidence_id)
            self._enhance.enhance_evidence(case_id, evidence_id)
            semantic = self._semantic.correct_evidence(case_id, evidence_id)
        summary["stages"] = {"cleaning": 1, "enhancement": 1, "semantic": 1}
        summary["semantic_results"] = [semantic]
        summary["duration_ms"] = round(timer.elapsed_ms, 1)
        self._log.info("orchestrated %s/%s in %.0f ms",
                       case_id, evidence_id, timer.elapsed_ms)
        return summary
