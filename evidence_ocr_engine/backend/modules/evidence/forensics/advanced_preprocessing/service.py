"""Module 2 - Advanced Image Preprocessing service.

Executes the operation plan produced by :class:`PreprocessingPlanner` on an
in-memory working copy. The original evidence file is never opened for
writing; the enhanced working copy is saved separately under
``storage/forensics/<EVIDENCE_ID>/derived/`` and a full
``preprocessing_report.json`` is stored for the audit trail.

This service complements - and never replaces - the existing
:class:`~...preprocessing.ImagePreprocessor` used by the legacy pipeline.
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ...logger import get_logger
from ...utils import utc_now_iso
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..quality.models import QualityAssessment
from ..repository import ForensicReportRepository
from . import operations as ops
from .models import AppliedOperation, PreprocessingReport
from .planner import PreprocessingPlanner

MODULE = "advanced_preprocessing"


class AdvancedPreprocessingService:
    """Quality-driven, fully audited preprocessing engine."""

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
        planner: Optional[PreprocessingPlanner] = None,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._planner = planner or PreprocessingPlanner()
        self._log = get_logger("forensics.preprocessing")

    # ------------------------------------------------------------------ public

    def enhance(
        self,
        image: np.ndarray,
        assessment: QualityAssessment,
        *,
        persist: bool = True,
        save_derived_image: bool = True,
    ) -> Tuple[np.ndarray, PreprocessingReport]:
        """Apply only the operations the quality assessment justifies.

        Returns:
            ``(enhanced_working_copy, report)`` - the input array is never
            mutated in place.
        """
        started = time.perf_counter()
        plan = self._planner.plan(assessment)
        reasons = self._planner.reasons(assessment)
        working = image.copy()
        applied: List[AppliedOperation] = []

        for name in plan:
            op_started = time.perf_counter()
            try:
                working, record = self._execute(name, working, assessment, reasons)
            except Exception as exc:  # noqa: BLE001 - one op must not kill the run
                record = AppliedOperation(
                    name=name, applied=False, reason=reasons.get(name, ""),
                    detail=f"failed: {exc}",
                )
                self._log.warning("operation %s failed: %s", name, exc)
            record.duration_ms = round((time.perf_counter() - op_started) * 1000.0, 1)
            applied.append(record)
            if persist:
                self._audit.record(
                    assessment.case_id, assessment.evidence_id, MODULE,
                    f"op:{name}",
                    f"applied={record.applied} {record.detail}",
                    duration_ms=record.duration_ms,
                )

        derived_file: Optional[str] = None
        if save_derived_image and any(op.applied for op in applied):
            derived_file = self._save_derived(working, assessment.evidence_id)

        report = PreprocessingReport(
            evidence_id=assessment.evidence_id,
            case_id=assessment.case_id,
            driven_by_quality_score=assessment.overall_score,
            planned_operations=plan,
            operations=applied,
            input_shape=list(image.shape),
            output_shape=list(working.shape),
            derived_image_file=derived_file,
            total_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(
                assessment.evidence_id, assessment.case_id,
                self._cfg.preprocessing_report_name, report.model_dump(),
            )
            self._audit.record(
                assessment.case_id, assessment.evidence_id, MODULE, "completed",
                f"{sum(1 for o in applied if o.applied)}/{len(plan)} operations applied",
                duration_ms=report.total_time_ms,
            )
        return working, report

    # ---------------------------------------------------------------- internal

    def _execute(
        self,
        name: str,
        working: np.ndarray,
        assessment: QualityAssessment,
        reasons: dict,
    ) -> Tuple[np.ndarray, AppliedOperation]:
        cfg = self._cfg
        m = assessment.metrics
        reason = reasons.get(name, "")

        if name == "perspective_correction":
            out, detail, was_applied = ops.perspective_correction(working, cfg)
            return out, AppliedOperation(
                name=name, applied=was_applied, reason=reason, detail=detail
            )
        if name == "deskew":
            out, detail = ops.deskew(working, m.skew_angle_deg)
            return out, AppliedOperation(
                name=name, applied=True, reason=reason, detail=detail,
                parameters={"angle_deg": round(m.skew_angle_deg, 3)},
            )
        if name == "super_resolution":
            if min(working.shape[:2]) >= cfg.super_resolution_trigger_px:
                return working, AppliedOperation(
                    name=name, applied=False, reason=reason,
                    detail="resolution already adequate after earlier steps",
                )
            out, detail = ops.super_resolution(working, cfg)
            return out, AppliedOperation(name=name, applied=True, reason=reason, detail=detail)
        if name == "adaptive_denoise":
            out, detail = ops.adaptive_denoise(working, cfg, m.noise_residual)
            return out, AppliedOperation(
                name=name, applied=True, reason=reason, detail=detail,
                parameters={"noise_residual": round(m.noise_residual, 2)},
            )
        if name == "illumination_correction":
            out, detail = ops.illumination_correction(working, cfg)
            return out, AppliedOperation(name=name, applied=True, reason=reason, detail=detail)
        if name == "shadow_removal":
            out, detail = ops.shadow_removal(working, cfg)
            return out, AppliedOperation(name=name, applied=True, reason=reason, detail=detail)
        if name == "clahe":
            out, detail = ops.clahe(working, cfg)
            return out, AppliedOperation(name=name, applied=True, reason=reason, detail=detail)
        if name == "morphological_cleanup":
            out, detail = ops.morphological_cleanup(working, cfg)
            return out, AppliedOperation(name=name, applied=True, reason=reason, detail=detail)
        if name == "edge_enhancement":
            out, detail = ops.edge_enhancement(working, cfg)
            return out, AppliedOperation(name=name, applied=True, reason=reason, detail=detail)

        return working, AppliedOperation(
            name=name, applied=False, reason=reason, detail="unknown operation"
        )

    def _save_derived(self, working: np.ndarray, evidence_id: str) -> Optional[str]:
        """Persist the enhanced working copy (a *derived* artefact, clearly
        separated from the pristine original in storage/originals/)."""
        directory = self._cfg.derived_dir(evidence_id)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = utc_now_iso().replace(":", "-")
        path = directory / f"enhanced_{stamp}.png"
        try:
            cv2.imwrite(str(path), cv2.cvtColor(working, cv2.COLOR_RGB2BGR))
            return path.name
        except cv2.error as exc:  # pragma: no cover
            self._log.warning("could not save derived image: %s", exc)
            return None
