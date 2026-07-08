"""
Pluggable ML model ensemble (ML Improvement, step 4 / step 9).

A registry-based ensemble that lets any number of ML models contribute to a
single machine-learning probability WITHOUT modifying the decision engine.
The existing XGBoost model remains the primary member; future models --
LightGBM, CatBoost, CharacterBERT, RoBERTa-for-URLs, or any URL-specific
transformer -- plug in by registering an adapter.

Each member declares its input type:
  * ``"features"`` -- receives the numeric feature vector
  * ``"url"``      -- receives the raw URL string (transformer-style models)

so feature-based and text-based models coexist behind one interface.  The
weighted-average output can be fed into the decision engine's existing
``xgboost_probability`` slot, keeping the hybrid pipeline unchanged.

Usage::

    from src.ensemble.ml_ensemble import MLModelEnsemble, MLMember

    ensemble = MLModelEnsemble()
    ensemble.register(MLMember(name="xgboost", model=xgb_model,
                               input_type="features", weight=0.7))
    ensemble.register(MLMember(name="url_transformer", model=transformer,
                               input_type="url", weight=0.3))
    probability, breakdown = ensemble.predict_proba(url, feature_vector)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MLMember:
    """One registered ensemble member.

    Attributes:
        name: Unique member name.
        model: Object exposing ``predict_proba`` and ``is_trained``
            (the engine's ``BaseModel`` contract).
        input_type: ``"features"`` or ``"url"``.
        weight: Relative contribution weight (> 0).
        enabled: Set False to bench a member without unregistering it.
    """

    name: str
    model: Any
    input_type: str = "features"
    weight: float = 1.0
    enabled: bool = True

    def is_ready(self) -> bool:
        """True when the member can produce predictions."""
        try:
            return bool(self.enabled and getattr(self.model, "is_trained", False))
        except Exception:  # noqa: BLE001
            return False


class MLModelEnsemble:
    """Weighted-average ensemble over registered ML models.

    Members that are disabled, untrained, or fail at inference are skipped
    and their weight is redistributed -- one bad member never breaks the
    prediction.
    """

    def __init__(self) -> None:
        self._members: dict[str, MLMember] = {}

    # ------------------------------------------------------------------
    # Registry API
    # ------------------------------------------------------------------

    def register(self, member: MLMember) -> None:
        """Register (or replace) an ensemble member.

        Args:
            member: The member to add.

        Raises:
            ValueError: On invalid input_type or non-positive weight.
        """
        if member.input_type not in ("features", "url"):
            raise ValueError(
                f"input_type must be 'features' or 'url', got {member.input_type!r}"
            )
        if member.weight <= 0:
            raise ValueError("weight must be > 0")
        self._members[member.name] = member
        logger.info(
            "MLModelEnsemble: registered '%s' (input=%s, weight=%.2f)",
            member.name, member.input_type, member.weight,
        )

    def unregister(self, name: str) -> None:
        """Remove a member by name (no-op when absent)."""
        self._members.pop(name, None)

    @property
    def members(self) -> list[str]:
        """Names of all registered members."""
        return list(self._members)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_proba(
        self,
        url: str,
        feature_vector: Optional[np.ndarray] = None,
    ) -> tuple[Optional[float], dict[str, Any]]:
        """Weighted-average phishing probability across ready members.

        Args:
            url: Raw URL (given to ``input_type='url'`` members).
            feature_vector: Numeric features (given to feature members).

        Returns:
            Tuple ``(probability, breakdown)``.  ``probability`` is ``None``
            when no member produced a prediction.  ``breakdown`` maps member
            name -> {probability, weight_used} plus a ``skipped`` list.
        """
        outputs: dict[str, float] = {}
        skipped: list[str] = []

        for member in self._members.values():
            if not member.is_ready():
                skipped.append(member.name)
                continue
            try:
                if member.input_type == "url":
                    proba = member.model.predict_proba(np.array([url]))
                else:
                    if feature_vector is None:
                        skipped.append(member.name)
                        continue
                    vector = np.asarray(feature_vector, dtype=float)
                    if vector.ndim == 1:
                        vector = vector.reshape(1, -1)
                    proba = member.model.predict_proba(vector)
                outputs[member.name] = float(np.asarray(proba).ravel()[0])
            except Exception as exc:  # noqa: BLE001 -- skip failing members
                logger.warning(
                    "MLModelEnsemble member '%s' failed: %s", member.name, exc
                )
                skipped.append(member.name)

        if not outputs:
            return None, {"skipped": skipped, "members": {}}

        total_weight = sum(self._members[n].weight for n in outputs)
        probability = sum(
            outputs[n] * (self._members[n].weight / total_weight) for n in outputs
        )

        breakdown = {
            "members": {
                name: {
                    "probability": round(prob, 6),
                    "weight_used": round(self._members[name].weight / total_weight, 4),
                }
                for name, prob in outputs.items()
            },
            "skipped": skipped,
        }
        return float(min(1.0, max(0.0, probability))), breakdown
