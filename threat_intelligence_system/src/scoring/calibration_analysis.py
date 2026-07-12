"""
Advanced probability-calibration analysis for the training pipeline.

Builds on the existing ``src.scoring.calibrator`` primitives (Brier score,
ECE, reliability diagram, ``ConfidenceCalibrator``, ``CalibrationEvaluator``)
and adds:

* **Maximum Calibration Error (MCE)** - worst-bin calibration gap.
* A single ``CalibrationReport`` covering Brier / ECE / MCE and the
  reliability-diagram data needed for plotting.
* **Automatic recalibration**: every supported calibration method is
  evaluated against the current calibrator and the model is refitted with
  the best method only when the improvement is material.

The inference path is untouched -- recalibration only refits the
``model.calibrator`` object that the existing prediction pipeline already
consumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.scoring.calibrator import (
    CALIBRATION_METHODS,
    ConfidenceCalibrator,
    brier_score,
    expected_calibration_error,
    reliability_diagram,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def maximum_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Maximum Calibration Error: the worst |accuracy - confidence| bin gap.

    Args:
        y_true: Binary ground-truth labels.
        y_prob: Predicted probabilities for the positive class.
        n_bins: Number of equal-width probability bins.

    Returns:
        The maximum calibration gap across non-empty bins (0.0 when no bin
        contains samples).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    worst = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (y_prob >= lo) & (y_prob < hi if hi < 1.0 else y_prob <= hi)
        if not mask.any():
            continue
        gap = abs(float(y_true[mask].mean()) - float(y_prob[mask].mean()))
        worst = max(worst, gap)
    return float(worst)


@dataclass
class CalibrationReport:
    """Calibration quality report for one probability vector.

    Attributes:
        brier: Brier score (lower is better).
        ece: Expected Calibration Error (lower is better).
        mce: Maximum Calibration Error (lower is better).
        n_bins: Bin count used for ECE / MCE / reliability data.
        reliability: Reliability-diagram data (bin confidence/accuracy/count).
    """

    brier: float = 0.0
    ece: float = 0.0
    mce: float = 0.0
    n_bins: int = 10
    reliability: dict[str, list[float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "brier_score": self.brier,
            "expected_calibration_error": self.ece,
            "maximum_calibration_error": self.mce,
            "n_bins": self.n_bins,
            "reliability_diagram": self.reliability,
        }


class CalibrationAnalyzer:
    """Measure calibration quality and recalibrate models when beneficial.

    Args:
        n_bins: Probability bins for ECE / MCE / reliability diagrams.
        min_improvement: Minimum ECE improvement (absolute) required before
            the model's calibrator is replaced -- avoids churn from noise.
        methods: Candidate calibration methods to evaluate.
    """

    def __init__(
        self,
        n_bins: int = 10,
        min_improvement: float = 0.002,
        methods: tuple[str, ...] = CALIBRATION_METHODS,
    ) -> None:
        self.n_bins = int(n_bins)
        self.min_improvement = float(min_improvement)
        self.methods = tuple(methods)

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def analyze(self, y_true: np.ndarray, y_prob: np.ndarray) -> CalibrationReport:
        """Compute Brier / ECE / MCE and reliability data for *y_prob*."""
        y_true = np.asarray(y_true, dtype=float)
        y_prob = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
        return CalibrationReport(
            brier=brier_score(y_true, y_prob),
            ece=expected_calibration_error(y_true, y_prob, self.n_bins),
            mce=maximum_calibration_error(y_true, y_prob, self.n_bins),
            n_bins=self.n_bins,
            reliability=reliability_diagram(y_true, y_prob, self.n_bins),
        )

    # ------------------------------------------------------------------
    # Automatic recalibration
    # ------------------------------------------------------------------

    def auto_recalibrate(
        self,
        model: Any,
        y_val: np.ndarray,
        raw_val_proba: np.ndarray,
    ) -> dict[str, Any]:
        """Recalibrate ``model.calibrator`` when a better method exists.

        Every candidate method is fitted on the validation data and compared
        (by ECE, ties broken by Brier) against the model's *current*
        calibrated output.  The calibrator is replaced only when the ECE
        improvement is at least ``min_improvement``.

        Args:
            model: A ``BaselineModel`` exposing ``calibrator``.
            y_val: Validation labels.
            raw_val_proba: Uncalibrated validation probabilities.

        Returns:
            Report dictionary with per-method metrics, the chosen method and
            whether recalibration was applied.
        """
        y_val = np.asarray(y_val, dtype=float)
        raw = np.clip(np.asarray(raw_val_proba, dtype=float), 0.0, 1.0)

        current = getattr(model, "calibrator", None)
        if current is not None and current.is_fitted:
            current_prob = np.array([current.calibrate(p) for p in raw])
            current_method = current.method
        else:
            current_prob = raw
            current_method = "uncalibrated"
        current_report = self.analyze(y_val, current_prob)

        candidates: dict[str, dict[str, Any]] = {}
        best_method: str | None = None
        best_key: tuple[float, float] | None = None
        for method in self.methods:
            try:
                calibrator = ConfidenceCalibrator(method=method)
                calibrator.fit(y_val, raw)
                calibrated = np.array([calibrator.calibrate(p) for p in raw])
                report = self.analyze(y_val, calibrated)
                candidates[method] = report.to_dict()
                key = (report.ece, report.brier)
                if best_key is None or key < best_key:
                    best_key = key
                    best_method = method
            except Exception as exc:  # noqa: BLE001 -- skip broken method
                logger.warning("Calibration method '%s' failed: %s", method, exc)

        applied = False
        if (
            best_method is not None
            and best_key is not None
            and current_report.ece - best_key[0] >= self.min_improvement
        ):
            new_calibrator = ConfidenceCalibrator(method=best_method)
            new_calibrator.fit(y_val, raw)
            model.calibrator = new_calibrator
            applied = True
            logger.info(
                "Recalibrated with '%s' (ECE %.4f -> %.4f)",
                best_method, current_report.ece, best_key[0],
            )
        else:
            logger.info(
                "Recalibration not beneficial (current '%s' ECE=%.4f, "
                "best candidate '%s' ECE=%.4f, threshold=%.4f)",
                current_method, current_report.ece,
                best_method, best_key[0] if best_key else float("nan"),
                self.min_improvement,
            )

        return {
            "current_method": current_method,
            "current": current_report.to_dict(),
            "candidates": candidates,
            "best_method": best_method,
            "recalibrated": applied,
            "min_improvement": self.min_improvement,
        }
