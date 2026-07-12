"""
SHAP explainability for the XGBoost phishing classifier (Phase 3-C).

Computes exact TreeSHAP feature contributions using XGBoost's native
``pred_contribs=True`` prediction mode, which implements the same TreeSHAP
algorithm as the ``shap`` package's ``TreeExplainer`` without requiring the
additional dependency.  If the optional ``shap`` package is installed it can
be used interchangeably; the native path is the default because it is
dependency-free and fast enough for per-request explanation.

This module is independent and additive -- it does not modify the model or
the prediction path.  Consumers call :class:`SHAPExplainer` explicitly.

Usage::

    from src.explainability.shap_explainer import SHAPExplainer

    explainer = SHAPExplainer(model, feature_names)
    explanation = explainer.explain_local(feature_vector)
    print(explanation.top_features)
    print(explainer.global_importance())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SHAPFeatureContribution:
    """A single feature's SHAP contribution for one prediction.

    Attributes:
        feature: Feature name.
        value: The feature's value in the explained sample.
        contribution: SHAP value (log-odds contribution). Positive pushes
            towards *phishing*, negative towards *legitimate*.
    """

    feature: str
    value: float
    contribution: float
    percentage: float = 0.0  # share of total |SHAP| for this prediction

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "feature": self.feature,
            "value": self.value,
            "contribution": round(self.contribution, 6),
            "percentage": round(self.percentage, 2),
        }


@dataclass
class SHAPExplanation:
    """Local SHAP explanation for a single prediction.

    Attributes:
        base_value: Model expected value (log-odds) before features.
        top_features: Top-k contributions ordered by absolute magnitude.
        positive_contributions: Features pushing towards phishing.
        negative_contributions: Features pushing towards legitimate.
        success: False when the explanation could not be computed.
        error_message: Failure description when ``success`` is False.
    """

    base_value: float = 0.0
    top_features: list[SHAPFeatureContribution] = field(default_factory=list)
    positive_contributions: list[SHAPFeatureContribution] = field(default_factory=list)
    negative_contributions: list[SHAPFeatureContribution] = field(default_factory=list)
    explanation_text: str = ""
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "base_value": round(self.base_value, 6),
            "top_features": [c.to_dict() for c in self.top_features],
            "positive_contributions": [c.to_dict() for c in self.positive_contributions],
            "negative_contributions": [c.to_dict() for c in self.negative_contributions],
            "explanation_text": self.explanation_text,
            "success": self.success,
            "error_message": self.error_message,
        }


class SHAPExplainer:
    """TreeSHAP explainer for the XGBoost baseline model.

    Args:
        model: A trained model wrapper exposing the underlying XGBoost
            classifier (``BaselineModel`` with an ``XGBClassifier``), or an
            ``xgboost.XGBClassifier`` / ``xgboost.Booster`` directly.
        feature_names: Ordered feature names matching the training schema.
        top_k: Number of features returned in ``top_features``.
    """

    def __init__(
        self,
        model: Any,
        feature_names: list[str],
        top_k: int = 10,
    ) -> None:
        self._feature_names = list(feature_names)
        self._top_k = int(top_k)
        self._booster = self._resolve_booster(model)
        logger.debug(
            "SHAPExplainer initialised: %d features, top_k=%d, booster=%s",
            len(self._feature_names), self._top_k, self._booster is not None,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True when an XGBoost booster could be resolved from the model."""
        return self._booster is not None

    def explain_local(self, feature_vector: np.ndarray) -> SHAPExplanation:
        """Compute the local SHAP explanation for one sample.

        Args:
            feature_vector: 1-D or (1, n_features) array of feature values.

        Returns:
            ``SHAPExplanation`` with per-feature contributions.  On failure a
            result with ``success=False`` is returned (never raises).
        """
        if self._booster is None:
            return SHAPExplanation(
                success=False,
                error_message="No XGBoost booster available for SHAP explanation.",
            )

        try:
            import xgboost as xgb

            vector = np.asarray(feature_vector, dtype=float)
            if vector.ndim == 1:
                vector = vector.reshape(1, -1)

            if vector.shape[1] != len(self._feature_names):
                return SHAPExplanation(
                    success=False,
                    error_message=(
                        f"Feature count mismatch: vector has {vector.shape[1]}, "
                        f"expected {len(self._feature_names)}."
                    ),
                )

            dmatrix = xgb.DMatrix(vector, feature_names=self._feature_names)
            # pred_contribs returns (n_samples, n_features + 1); last column
            # is the base (expected) value.  Values are exact TreeSHAP.
            contribs = self._booster.predict(dmatrix, pred_contribs=True)
            row = contribs[0]
            base_value = float(row[-1])
            shap_values = row[:-1]

            total_abs = float(np.abs(shap_values).sum()) or 1.0
            contributions = [
                SHAPFeatureContribution(
                    feature=name,
                    value=float(vector[0][idx]),
                    contribution=float(shap_values[idx]),
                    percentage=float(abs(shap_values[idx]) / total_abs * 100.0),
                )
                for idx, name in enumerate(self._feature_names)
            ]

            by_magnitude = sorted(
                contributions, key=lambda c: abs(c.contribution), reverse=True
            )
            positive = sorted(
                (c for c in contributions if c.contribution > 0),
                key=lambda c: c.contribution,
                reverse=True,
            )
            negative = sorted(
                (c for c in contributions if c.contribution < 0),
                key=lambda c: c.contribution,
            )

            return SHAPExplanation(
                base_value=base_value,
                top_features=by_magnitude[: self._top_k],
                positive_contributions=positive[: self._top_k],
                negative_contributions=negative[: self._top_k],
                explanation_text=self._build_explanation_text(
                    base_value, shap_values, positive, negative
                ),
            )
        except Exception as exc:  # noqa: BLE001 -- explanation must never break prediction
            logger.warning("SHAP local explanation failed: %s", exc)
            return SHAPExplanation(success=False, error_message=str(exc))

    def global_importance(self, importance_type: str = "gain") -> dict[str, float]:
        """Compute normalised global feature importance from the booster.

        Args:
            importance_type: XGBoost importance type -- ``'gain'``,
                ``'weight'``, ``'cover'``, ``'total_gain'`` or ``'total_cover'``.

        Returns:
            Mapping of feature name -> normalised importance (sums to 1.0),
            sorted descending.  Empty dict on failure.
        """
        if self._booster is None:
            return {}

        try:
            raw = self._booster.get_score(importance_type=importance_type)
            # Booster may key by f0..fN when trained without names
            named: dict[str, float] = {}
            for key, val in raw.items():
                if key.startswith("f") and key[1:].isdigit():
                    idx = int(key[1:])
                    if idx < len(self._feature_names):
                        named[self._feature_names[idx]] = float(val)
                        continue
                named[key] = float(val)

            total = sum(named.values())
            if total <= 0:
                return {}
            normalised = {k: v / total for k, v in named.items()}
            return dict(
                sorted(normalised.items(), key=lambda kv: kv[1], reverse=True)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SHAP global importance failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanation_text(
        base_value: float,
        shap_values: np.ndarray,
        positive: list[SHAPFeatureContribution],
        negative: list[SHAPFeatureContribution],
    ) -> str:
        """Generate a plain-language explanation of the prediction.

        Args:
            base_value: Model expected value (log-odds).
            shap_values: Raw SHAP values for the sample.
            positive: Contributions pushing towards phishing (descending).
            negative: Contributions pushing towards legitimate (ascending).

        Returns:
            A human-readable multi-sentence explanation string.
        """
        logit = base_value + float(shap_values.sum())
        probability = 1.0 / (1.0 + np.exp(-logit))
        leaning = "PHISHING" if probability >= 0.5 else "LEGITIMATE"

        parts = [
            f"The ML model leans {leaning} "
            f"(phishing probability {probability:.1%})."
        ]
        if positive:
            top = ", ".join(
                f"{c.feature} ({c.percentage:.0f}%)" for c in positive[:3]
            )
            parts.append(f"Strongest phishing indicators: {top}.")
        if negative:
            top = ", ".join(
                f"{c.feature} ({c.percentage:.0f}%)" for c in negative[:3]
            )
            parts.append(f"Strongest legitimate indicators: {top}.")
        return " ".join(parts)

    @staticmethod
    def _resolve_booster(model: Any) -> Optional[Any]:
        """Extract an ``xgboost.Booster`` from supported model wrappers."""
        try:
            import xgboost as xgb
        except ImportError:
            logger.warning("xgboost not installed -- SHAP explainer unavailable.")
            return None

        try:
            if isinstance(model, xgb.Booster):
                return model
            if isinstance(model, xgb.XGBClassifier):
                return model.get_booster()
            # BaselineModel wrapper exposes the sklearn estimator as .model
            for attr in ("model", "_model"):
                inner = getattr(model, attr, None)
                if isinstance(inner, xgb.XGBClassifier):
                    return inner.get_booster()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not resolve XGBoost booster: %s", exc)
        return None
