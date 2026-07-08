"""
Ensemble prediction engine (Phase 3-B).

Combines every detection signal produced by the engine into a single final
decision with configurable weights:

* XGBoost (baseline ML) phishing probability
* Transformer phishing probability (optional -- weight is redistributed
  when no transformer model is available)
* Rule engine score
* Threat intelligence score
* Trust score (inverted: low trust raises risk)

The engine is a pure, stateless combiner: it does not run models itself, it
only merges their outputs.  This keeps it independently testable and lets
future signals (e.g. GNN embeddings, external reputation feeds) be added
without modifying existing components.

Weights are read from ``settings.threat.ensemble_weights`` (backed by
``config/settings.yaml``) and can be overridden per instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EnsembleInputs:
    """Signals fed into the ensemble.

    All probabilities/scores are expressed as *phishing risk* in [0, 1],
    except ``trust_score`` which is the 0-100 domain trust value (higher =
    more trustworthy) and is inverted internally.

    Attributes:
        xgboost_probability: Calibrated phishing probability from XGBoost.
        transformer_probability: Phishing probability from the URL
            transformer, or ``None`` when unavailable.
        rule_score: Aggregate rule engine score (0-1).
        threat_intel_score: Aggregate threat intelligence score (0-1).
        trust_score: Domain trust score (0-100).
    """

    xgboost_probability: float = 0.0
    transformer_probability: Optional[float] = None
    rule_score: float = 0.0
    threat_intel_score: float = 0.0
    trust_score: float = 50.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "xgboost_probability": self.xgboost_probability,
            "transformer_probability": self.transformer_probability,
            "rule_score": self.rule_score,
            "threat_intel_score": self.threat_intel_score,
            "trust_score": self.trust_score,
        }


@dataclass
class EnsembleDecision:
    """Final ensemble output.

    Attributes:
        prediction: ``'Legitimate'``, ``'Suspicious'`` or ``'Phishing'``.
        confidence: Confidence in the final prediction (0-1).
        risk_score: Composite risk score (0-100).
        breakdown: Per-signal weighted contributions (percentage points of
            the final risk score).
        weights_used: Normalised weights actually applied (after
            redistribution of unavailable signals).
        explanation: Human-readable decision explanation strings.
    """

    prediction: str = "Legitimate"
    confidence: float = 0.0
    risk_score: int = 0
    breakdown: dict[str, float] = field(default_factory=dict)
    weights_used: dict[str, float] = field(default_factory=dict)
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "prediction": self.prediction,
            "confidence": round(self.confidence, 4),
            "risk_score": self.risk_score,
            "breakdown": {k: round(v, 2) for k, v in self.breakdown.items()},
            "weights_used": {k: round(v, 4) for k, v in self.weights_used.items()},
            "explanation": self.explanation,
        }


class EnsembleEngine:
    """Configurable-weight ensemble combiner (Phase 3-B).

    Args:
        weights: Optional weight override.  Keys: ``xgboost``,
            ``transformer``, ``rules``, ``threat_intelligence``, ``trust``.
            Defaults come from ``settings.threat.ensemble_weights``.

    Usage::

        engine = EnsembleEngine()
        decision = engine.combine(EnsembleInputs(
            xgboost_probability=0.92,
            transformer_probability=0.88,
            rule_score=0.75,
            threat_intel_score=0.4,
            trust_score=10,
        ))
        print(decision.prediction, decision.confidence)
    """

    _SIGNAL_KEYS = ("xgboost", "transformer", "rules", "threat_intelligence", "trust")

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        settings = get_settings()
        defaults = dict(getattr(settings.threat, "ensemble_weights", {}) or {})
        if not defaults:
            defaults = {
                "xgboost": 0.35,
                "transformer": 0.20,
                "rules": 0.20,
                "threat_intelligence": 0.15,
                "trust": 0.10,
            }
        self.weights: dict[str, float] = {
            k: float((weights or defaults).get(k, defaults.get(k, 0.0)))
            for k in self._SIGNAL_KEYS
        }
        thresholds = settings.threat.classification_thresholds
        self._legitimate_max = int(thresholds.get("legitimate_max", 30))
        self._suspicious_max = int(thresholds.get("suspicious_max", 60))
        logger.debug("EnsembleEngine initialised with weights: %s", self.weights)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def combine(self, inputs: EnsembleInputs) -> EnsembleDecision:
        """Combine all signals into the final decision.

        Signals that are unavailable (currently only the transformer) have
        their weight redistributed proportionally across the remaining
        signals so the composite stays on the same 0-1 scale.

        Args:
            inputs: The ensemble input signals.

        Returns:
            ``EnsembleDecision`` with final prediction, confidence,
            risk score, per-signal breakdown, and explanation.
        """
        clamp = lambda v: max(0.0, min(1.0, float(v)))  # noqa: E731

        signal_values: dict[str, Optional[float]] = {
            "xgboost": clamp(inputs.xgboost_probability),
            "transformer": (
                clamp(inputs.transformer_probability)
                if inputs.transformer_probability is not None
                else None
            ),
            "rules": clamp(inputs.rule_score),
            "threat_intelligence": clamp(inputs.threat_intel_score),
            "trust": clamp(1.0 - (float(inputs.trust_score) / 100.0)),
        }

        # Redistribute weights of unavailable signals
        available = {k: v for k, v in signal_values.items() if v is not None}
        active_weight = sum(self.weights[k] for k in available)
        if active_weight <= 0:
            logger.warning("EnsembleEngine: no active signal weights; returning neutral.")
            return EnsembleDecision(
                prediction="Suspicious",
                confidence=0.0,
                risk_score=50,
                explanation=["No ensemble signals available -- neutral decision."],
            )

        weights_used = {k: self.weights[k] / active_weight for k in available}

        composite = sum(available[k] * weights_used[k] for k in available)
        risk_score = max(0, min(100, int(round(composite * 100))))

        breakdown = {
            k: available[k] * weights_used[k] * 100 for k in available
        }
        if signal_values["transformer"] is None:
            breakdown["transformer"] = 0.0

        prediction = self._classify(risk_score)
        confidence = self._confidence(risk_score, prediction)
        explanation = self._explain(prediction, risk_score, available, weights_used, inputs)

        decision = EnsembleDecision(
            prediction=prediction,
            confidence=round(confidence, 4),
            risk_score=risk_score,
            breakdown=breakdown,
            weights_used=weights_used,
            explanation=explanation,
        )

        logger.debug(
            "Ensemble decision: %s risk=%d conf=%.3f signals=%s",
            prediction, risk_score, confidence,
            {k: round(v, 3) for k, v in available.items()},
        )
        return decision

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _classify(self, risk_score: int) -> str:
        """Map the risk score to the 3-class prediction."""
        if risk_score <= self._legitimate_max:
            return "Legitimate"
        if risk_score <= self._suspicious_max:
            return "Suspicious"
        return "Phishing"

    def _confidence(self, risk_score: int, prediction: str) -> float:
        """Derive a confidence value from the risk score and class."""
        dec = risk_score / 100.0
        if prediction == "Phishing":
            confidence = dec
        elif prediction == "Legitimate":
            confidence = 1.0 - dec
        else:
            mid = (self._legitimate_max + self._suspicious_max) / 200.0
            confidence = 1.0 - abs(dec - mid) * 2.0
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _explain(
        prediction: str,
        risk_score: int,
        available: dict[str, float],
        weights_used: dict[str, float],
        inputs: EnsembleInputs,
    ) -> list[str]:
        """Generate human-readable explanation strings for the decision."""
        labels = {
            "xgboost": "ML model (XGBoost)",
            "transformer": "URL transformer",
            "rules": "Rule engine",
            "threat_intelligence": "Threat intelligence",
            "trust": "Domain trust",
        }
        explanation = [
            f"Final decision '{prediction}' from composite risk score {risk_score}/100."
        ]
        for key, value in sorted(
            available.items(), key=lambda kv: kv[1] * weights_used[kv[0]], reverse=True
        ):
            contribution = value * weights_used[key] * 100
            explanation.append(
                f"{labels[key]} signal {value:.2f} x weight {weights_used[key]:.2f} "
                f"-> +{contribution:.1f} risk points."
            )
        if inputs.transformer_probability is None:
            explanation.append(
                "URL transformer unavailable -- its weight was redistributed "
                "across the remaining signals."
            )
        return explanation
