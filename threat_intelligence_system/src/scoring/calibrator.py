"""
Confidence calibration for phishing URL detection predictions.

The ``ConfidenceCalibrator`` applies post-hoc probability calibration to raw
model output to produce more reliable confidence estimates.  It supports:

1. **Platt Scaling** (logistic regression on held-out predictions).
2. **Isotonic Regression** (non-parametric monotone mapping).
3. **Temperature Scaling** (single-parameter softmax scaling).
4. **Identity** (no-op passthrough — returns raw confidence unchanged).

All calibrators implement the same interface: ``fit(y_true, y_prob)``,
``calibrate(confidence)``, ``calibrate_batch(confidences)``.

The ``CalibratedPredictor`` wrapper combines a calibrator with the engine's
prediction output to produce a fully calibrated ``PredictionResult``.

Usage::

    from src.scoring.calibrator import ConfidenceCalibrator

    calibrator = ConfidenceCalibrator(method="platt")
    calibrator.fit(y_true=np.array([0, 1, 1, 0]),
                   y_prob=np.array([0.2, 0.8, 0.9, 0.1]))

    calibrated = calibrator.calibrate(raw_confidence=0.75)
    print(calibrated)  # e.g. 0.71  (after calibration)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Supported calibration methods
# ---------------------------------------------------------------------------

CALIBRATION_METHODS = ("platt", "isotonic", "temperature", "identity")


# ---------------------------------------------------------------------------
# ConfidenceCalibrator
# ---------------------------------------------------------------------------

class ConfidenceCalibrator:
    """Post-hoc probability calibrator for phishing detection confidence scores.

    After training a model, the raw predicted probabilities may not be
    well-calibrated (i.e. a prediction of 0.9 does not necessarily mean the
    URL is phishing with 90% probability).  This class applies one of several
    calibration strategies to correct systematic biases.

    Args:
        method: Calibration strategy to use.
            - ``'platt'``: Logistic regression (Platt scaling).
            - ``'isotonic'``: Isotonic regression.
            - ``'temperature'``: Temperature scaling (single scalar).
            - ``'identity'``: No calibration applied.

    Attributes:
        method: The active calibration strategy.
        is_fitted: ``True`` after a successful call to :meth:`fit`.
    """

    def __init__(self, method: str = "platt") -> None:
        if method not in CALIBRATION_METHODS:
            raise ValueError(
                f"Unknown calibration method '{method}'. "
                f"Choose from: {CALIBRATION_METHODS}"
            )
        self.method = method
        self.is_fitted: bool = False

        # Internal calibration state
        self._platt_A: float = 1.0   # Platt: f(p) = sigmoid(A*p + B)
        self._platt_B: float = 0.0
        self._isotonic_x: list[float] = []
        self._isotonic_y: list[float] = []
        self._temperature: float = 1.0  # Temperature: p_cal = sigmoid(log(p/(1-p))/T)

        logger.debug("ConfidenceCalibrator initialised: method=%s", method)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        y_true: "np.ndarray",
        y_prob: "np.ndarray",
    ) -> "ConfidenceCalibrator":
        """Fit the calibrator on held-out predictions.

        Args:
            y_true: Ground-truth binary labels (0 = legitimate, 1 = phishing).
                Shape: (N,).
            y_prob: Model-predicted probability of phishing (class 1).
                Shape: (N,).  Values in [0, 1].

        Returns:
            Self, for method chaining.

        Raises:
            ValueError: If arrays have different lengths or are empty.
        """
        y_true = np.asarray(y_true, dtype=float)
        y_prob = np.asarray(y_prob, dtype=float)

        if len(y_true) == 0 or len(y_prob) == 0:
            raise ValueError("y_true and y_prob must be non-empty.")
        if len(y_true) != len(y_prob):
            raise ValueError(
                f"y_true and y_prob must have the same length "
                f"({len(y_true)} vs {len(y_prob)})."
            )

        logger.info(
            "Fitting calibrator: method=%s, n_samples=%d", self.method, len(y_true)
        )

        if self.method == "platt":
            self._fit_platt(y_true, y_prob)
        elif self.method == "isotonic":
            self._fit_isotonic(y_true, y_prob)
        elif self.method == "temperature":
            self._fit_temperature(y_true, y_prob)
        else:
            # identity — nothing to fit
            pass

        self.is_fitted = True
        return self

    def calibrate(self, confidence: float) -> float:
        """Apply calibration to a single confidence value.

        Args:
            confidence: Raw model confidence in [0, 1].

        Returns:
            Calibrated confidence in [0, 1].
        """
        confidence = max(0.0, min(1.0, float(confidence)))

        if not self.is_fitted or self.method == "identity":
            return confidence

        if self.method == "platt":
            return self._apply_platt(confidence)
        elif self.method == "isotonic":
            return self._apply_isotonic(confidence)
        elif self.method == "temperature":
            return self._apply_temperature(confidence)

        return confidence

    def calibrate_batch(self, confidences: list[float]) -> list[float]:
        """Apply calibration to a list of confidence values.

        Args:
            confidences: List of raw model confidences.

        Returns:
            List of calibrated confidences.
        """
        return [self.calibrate(c) for c in confidences]

    def save(self, path: Path) -> None:
        """Persist calibration parameters to a JSON file.

        Args:
            path: File path to write (must be writable).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "method": self.method,
            "is_fitted": self.is_fitted,
            "platt_A": self._platt_A,
            "platt_B": self._platt_B,
            "isotonic_x": self._isotonic_x,
            "isotonic_y": self._isotonic_y,
            "temperature": self._temperature,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        logger.info("Calibrator saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> "ConfidenceCalibrator":
        """Load a saved calibrator from a JSON file.

        Args:
            path: File path to load.

        Returns:
            Fitted ``ConfidenceCalibrator`` instance.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as fh:
            state = json.load(fh)

        calibrator = cls(method=state["method"])
        calibrator.is_fitted = state["is_fitted"]
        calibrator._platt_A = state["platt_A"]
        calibrator._platt_B = state["platt_B"]
        calibrator._isotonic_x = state["isotonic_x"]
        calibrator._isotonic_y = state["isotonic_y"]
        calibrator._temperature = state["temperature"]

        logger.info("Calibrator loaded from %s (method=%s)", path, calibrator.method)
        return calibrator

    # ------------------------------------------------------------------
    # Platt scaling
    # ------------------------------------------------------------------

    def _fit_platt(self, y_true: np.ndarray, y_prob: np.ndarray) -> None:
        """Fit Platt scaling using a lightweight Newton's method solver.

        Fits parameters A and B such that ``sigmoid(A * f + B)`` minimizes
        the log-loss on the held-out set.

        Args:
            y_true: Ground-truth labels (0/1).
            y_prob: Raw probabilities in [0, 1].
        """
        # Use sklearn if available; fall back to numpy gradient descent
        try:
            from sklearn.linear_model import LogisticRegression
            lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
            lr.fit(y_prob.reshape(-1, 1), y_true)
            self._platt_A = float(lr.coef_[0][0])
            self._platt_B = float(lr.intercept_[0])
            logger.debug(
                "Platt scaling fitted (sklearn): A=%.4f, B=%.4f",
                self._platt_A, self._platt_B,
            )
        except Exception:
            # Fallback: simple gradient descent
            self._platt_A, self._platt_B = self._platt_gradient_descent(y_true, y_prob)
            logger.debug(
                "Platt scaling fitted (gd): A=%.4f, B=%.4f",
                self._platt_A, self._platt_B,
            )

    @staticmethod
    def _platt_gradient_descent(
        y_true: np.ndarray, y_prob: np.ndarray, lr: float = 0.01, n_iter: int = 1000
    ) -> tuple[float, float]:
        """Gradient descent solver for Platt scaling (fallback)."""
        A, B = 1.0, 0.0
        n = len(y_true)
        for _ in range(n_iter):
            logits = A * y_prob + B
            p = 1.0 / (1.0 + np.exp(-logits))
            error = p - y_true
            grad_A = np.dot(error, y_prob) / n
            grad_B = np.mean(error)
            A -= lr * grad_A
            B -= lr * grad_B
        return float(A), float(B)

    def _apply_platt(self, confidence: float) -> float:
        """Apply the fitted Platt scaling transform."""
        logit = self._platt_A * confidence + self._platt_B
        calibrated = 1.0 / (1.0 + math.exp(-logit))
        return round(max(0.0, min(1.0, calibrated)), 6)

    # ------------------------------------------------------------------
    # Isotonic regression
    # ------------------------------------------------------------------

    def _fit_isotonic(self, y_true: np.ndarray, y_prob: np.ndarray) -> None:
        """Fit isotonic regression calibration.

        Args:
            y_true: Ground-truth labels.
            y_prob: Raw probabilities.
        """
        try:
            from sklearn.isotonic import IsotonicRegression
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(y_prob, y_true)
            # Store the fitted mapping as sorted x/y pairs
            self._isotonic_x = list(map(float, iso.X_thresholds_))
            self._isotonic_y = list(map(float, iso.y_thresholds_))
            logger.debug(
                "Isotonic regression fitted: %d calibration points",
                len(self._isotonic_x),
            )
        except Exception as exc:
            logger.warning("Isotonic regression fitting failed: %s — using identity", exc)
            # Fall back to identity if sklearn is unavailable
            self._isotonic_x = []
            self._isotonic_y = []

    def _apply_isotonic(self, confidence: float) -> float:
        """Apply the fitted isotonic regression transform via linear interpolation."""
        x = self._isotonic_x
        y = self._isotonic_y
        if not x:
            return confidence
        # np.interp handles out-of-bounds by clamping to boundary values
        calibrated = float(np.interp(confidence, x, y))
        return round(max(0.0, min(1.0, calibrated)), 6)

    # ------------------------------------------------------------------
    # Temperature scaling
    # ------------------------------------------------------------------

    def _fit_temperature(self, y_true: np.ndarray, y_prob: np.ndarray) -> None:
        """Fit temperature scaling by grid search over T in [0.1, 5.0].

        Temperature scaling: ``p_cal = sigmoid(log(p/(1-p)) / T)``

        Args:
            y_true: Ground-truth labels.
            y_prob: Raw probabilities.
        """
        best_t = 1.0
        best_loss = float("inf")

        # Clip to avoid log(0)
        y_prob_clipped = np.clip(y_prob, 1e-7, 1 - 1e-7)
        logits = np.log(y_prob_clipped / (1 - y_prob_clipped))

        for t in np.linspace(0.1, 5.0, 200):
            p_cal = 1.0 / (1.0 + np.exp(-logits / t))
            loss = -np.mean(
                y_true * np.log(np.clip(p_cal, 1e-9, 1))
                + (1 - y_true) * np.log(np.clip(1 - p_cal, 1e-9, 1))
            )
            if loss < best_loss:
                best_loss = loss
                best_t = float(t)

        self._temperature = best_t
        logger.debug("Temperature scaling fitted: T=%.4f (log-loss=%.4f)", best_t, best_loss)

    def _apply_temperature(self, confidence: float) -> float:
        """Apply temperature scaling."""
        confidence = max(1e-7, min(1 - 1e-7, confidence))
        logit = math.log(confidence / (1 - confidence))
        scaled = logit / max(self._temperature, 1e-6)
        calibrated = 1.0 / (1.0 + math.exp(-scaled))
        return round(max(0.0, min(1.0, calibrated)), 6)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def calibration_info(self) -> dict[str, Any]:
        """Return a summary of calibration parameters.

        Returns:
            Dictionary with calibration method and fitted parameters.
        """
        info: dict[str, Any] = {
            "method": self.method,
            "is_fitted": self.is_fitted,
        }
        if self.method == "platt":
            info["platt_A"] = self._platt_A
            info["platt_B"] = self._platt_B
        elif self.method == "isotonic":
            info["n_calibration_points"] = len(self._isotonic_x)
        elif self.method == "temperature":
            info["temperature"] = self._temperature
        return info


# ---------------------------------------------------------------------------
# Calibration quality metrics (Phase 3-D)
# ---------------------------------------------------------------------------

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute the Brier score (mean squared error of probabilities).

    Lower is better; 0.0 is a perfect probabilistic forecast.

    Args:
        y_true: Binary ground-truth labels (0/1).
        y_prob: Predicted probabilities of the positive class.

    Returns:
        Brier score in [0, 1].
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) == 0:
        return 0.0
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute the Expected Calibration Error (ECE).

    Probabilities are bucketed into *n_bins* equal-width bins; ECE is the
    weighted mean absolute difference between each bin's mean predicted
    probability and its empirical positive rate.  Lower is better.

    Args:
        y_true: Binary ground-truth labels (0/1).
        y_prob: Predicted probabilities of the positive class.
        n_bins: Number of equal-width probability bins.

    Returns:
        ECE in [0, 1].
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    n = len(y_true)
    if n == 0:
        return 0.0

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        count = int(mask.sum())
        if count == 0:
            continue
        avg_conf = float(y_prob[mask].mean())
        avg_acc = float(y_true[mask].mean())
        ece += (count / n) * abs(avg_conf - avg_acc)
    return float(ece)


def reliability_diagram(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> dict[str, list[float]]:
    """Compute reliability-diagram data (per-bin confidence vs accuracy).

    Args:
        y_true: Binary ground-truth labels (0/1).
        y_prob: Predicted probabilities of the positive class.
        n_bins: Number of equal-width probability bins.

    Returns:
        Dictionary with parallel lists: ``bin_centers``, ``mean_predicted``,
        ``fraction_positive`` and ``bin_counts``.  Empty bins are omitted.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)

    centers: list[float] = []
    mean_pred: list[float] = []
    frac_pos: list[float] = []
    counts: list[float] = []

    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        count = int(mask.sum())
        if count == 0:
            continue
        centers.append(float((lo + hi) / 2.0))
        mean_pred.append(float(y_prob[mask].mean()))
        frac_pos.append(float(y_true[mask].mean()))
        counts.append(float(count))

    return {
        "bin_centers": centers,
        "mean_predicted": mean_pred,
        "fraction_positive": frac_pos,
        "bin_counts": counts,
    }


class CalibrationEvaluator:
    """Evaluate calibration methods and select the best one (Phase 3-D).

    Fits every candidate :class:`ConfidenceCalibrator` method on a held-out
    set, scores each with Brier score and Expected Calibration Error, and
    selects the best method (lowest ECE; Brier score as tie-breaker).

    Usage::

        evaluator = CalibrationEvaluator()
        report = evaluator.evaluate_methods(y_true, y_prob)
        best = evaluator.best_calibrator(y_true, y_prob)
    """

    def __init__(self, methods: tuple[str, ...] = CALIBRATION_METHODS, n_bins: int = 10) -> None:
        """Initialise the evaluator.

        Args:
            methods: Calibration methods to evaluate.
            n_bins: Bin count for ECE / reliability computation.
        """
        self.methods = tuple(methods)
        self.n_bins = int(n_bins)

    def evaluate_methods(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
    ) -> dict[str, Any]:
        """Fit and score every calibration method.

        Args:
            y_true: Binary ground-truth labels for the held-out set.
            y_prob: Raw (uncalibrated) predicted probabilities.

        Returns:
            Report dictionary::

                {
                  "uncalibrated": {"brier_score": ..., "ece": ...},
                  "methods": {method: {"brier_score", "ece", "reliability"}},
                  "best_method": "<method>",
                }
        """
        y_true = np.asarray(y_true, dtype=float)
        y_prob = np.asarray(y_prob, dtype=float)

        report: dict[str, Any] = {
            "uncalibrated": {
                "brier_score": brier_score(y_true, y_prob),
                "ece": expected_calibration_error(y_true, y_prob, self.n_bins),
            },
            "methods": {},
            "best_method": "identity",
        }

        best_key: tuple[float, float] | None = None
        for method in self.methods:
            try:
                calibrator = ConfidenceCalibrator(method=method)
                calibrator.fit(y_true, y_prob)
                calibrated = np.array(
                    calibrator.calibrate_batch(y_prob.tolist()), dtype=float
                )
                m_brier = brier_score(y_true, calibrated)
                m_ece = expected_calibration_error(y_true, calibrated, self.n_bins)
                report["methods"][method] = {
                    "brier_score": m_brier,
                    "ece": m_ece,
                    "reliability": reliability_diagram(y_true, calibrated, self.n_bins),
                }
                key = (m_ece, m_brier)
                if best_key is None or key < best_key:
                    best_key = key
                    report["best_method"] = method
            except Exception as exc:  # noqa: BLE001 -- evaluate remaining methods
                logger.warning("Calibration method '%s' failed: %s", method, exc)
                report["methods"][method] = {"error": str(exc)}

        logger.info(
            "Calibration evaluation complete -- best method: %s",
            report["best_method"],
        )
        return report

    def best_calibrator(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
    ) -> "ConfidenceCalibrator":
        """Fit and return the best calibrator for the given held-out data.

        Args:
            y_true: Binary ground-truth labels.
            y_prob: Raw predicted probabilities.

        Returns:
            A fitted ``ConfidenceCalibrator`` using the best method.
        """
        report = self.evaluate_methods(y_true, y_prob)
        best = ConfidenceCalibrator(method=report["best_method"])
        best.fit(np.asarray(y_true, dtype=float), np.asarray(y_prob, dtype=float))
        return best
