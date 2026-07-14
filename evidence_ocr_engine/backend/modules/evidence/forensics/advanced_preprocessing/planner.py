"""Preprocessing planner: turns a Module-1 quality assessment into an
ordered, minimal operation plan.

The planner *never* schedules unnecessary work - an operation is planned only
when the quality report recommends it, and conditional operations (e.g.
perspective correction) may still be skipped at execution time when their
preconditions are not met.
"""

from __future__ import annotations

from typing import Dict, List

from ..quality.models import QualityAssessment

#: Canonical execution order - geometric fixes first, tonal fixes second,
#: detail fixes last, so operations do not undo each other.
EXECUTION_ORDER: List[str] = [
    "perspective_correction",
    "deskew",
    "super_resolution",
    "adaptive_denoise",
    "illumination_correction",
    "shadow_removal",
    "clahe",
    "morphological_cleanup",
    "edge_enhancement",
]


class PreprocessingPlanner:
    """Derives the ordered operation plan for one evidence image."""

    def plan(self, assessment: QualityAssessment) -> List[str]:
        """Ordered subset of :data:`EXECUTION_ORDER` for this image."""
        recommended = set(assessment.recommended_operations)
        return [op for op in EXECUTION_ORDER if op in recommended]

    def reasons(self, assessment: QualityAssessment) -> Dict[str, str]:
        """Human-readable justification per planned operation (audit trail)."""
        m = assessment.metrics
        sub = assessment.sub_scores
        mapping = {
            "adaptive_denoise": f"noise sub-score {sub.get('noise', 0):.0f}/100 "
                                f"(residual {m.noise_residual:.1f})",
            "clahe": f"contrast sub-score {sub.get('contrast', 0):.0f}/100 "
                     f"(std {m.contrast_std:.1f})",
            "illumination_correction": f"brightness sub-score "
                                       f"{sub.get('brightness', 0):.0f}/100 "
                                       f"(mean {m.brightness_mean:.0f})",
            "shadow_removal": "uneven bright background suggests cast shadows",
            "deskew": f"skew angle {m.skew_angle_deg:.2f} deg",
            "edge_enhancement": f"blur sub-score {sub.get('blur', 0):.0f}/100 "
                                f"(laplacian var {m.blur_laplacian_variance:.0f})",
            "super_resolution": f"min dimension {min(m.width, m.height)} px "
                                "below the OCR-adequate threshold",
            "perspective_correction": "probe for photographed-document geometry",
            "morphological_cleanup": "combined low contrast + noise",
        }
        return {op: mapping.get(op, "recommended by quality assessment")
                for op in self.plan(assessment)}
