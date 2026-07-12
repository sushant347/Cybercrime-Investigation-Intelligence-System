"""
PredictionResult dataclass -- the canonical output of the Phishing URL Detection Engine.

This is the public interface that other CIIS modules will import and consume.
Supports JSON serialization, dictionary conversion, and factory methods.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class PredictionResult:
    """
    Structured prediction output for a single URL analysis.

    This dataclass encapsulates the complete result of phishing URL detection,
    including the AI prediction, confidence score, threat intelligence findings,
    extracted features, and human-readable explanations.

    Attributes:
        url: The original URL that was analyzed.
        prediction: Classification result -- 'Phishing', 'Suspicious', or 'Legitimate'.
        confidence: Combined decision confidence in the prediction (0.0 to 1.0).
        risk_score: Composite threat score (0 to 100).
        risk_level: Human-readable risk level -- 'Critical', 'High', 'Medium', 'Low', or 'Safe'.
        features: Dictionary of extracted features used for prediction.
        threat_intelligence: Dictionary of external intelligence data.
        reasons: List of human-readable reasons supporting the prediction.
        model_type: The model used for prediction (e.g., 'xgboost', 'distilbert').
        analysis_timestamp: ISO 8601 timestamp of when the analysis was performed.
        metadata: Optional additional metadata for extensibility.
        
        # New attributes (v2.0)
        trust_score: Domain trust score (0 to 100; higher = more trustworthy).
        ml_confidence: ML model's confidence IN the predicted class
            (0.0 to 1.0; e.g. 0.99 for a confident 'Legitimate').
        rule_confidence: Rule engine RISK signal (0.0 to 1.0; 0.0 means no
            rules fired -- this is a risk score, not a confidence).
        decision_confidence: Final risk score expressed as 0.0-1.0
            (risk_score / 100).
        brand_detected: Brand name string if brand impersonation was detected, otherwise None.
        official_domain: True if the domain is the official domain of the brand.
        ssl_status: Certificate status -- 'VALID', 'INVALID', or 'UNKNOWN'.
        positive_indicators: List of positive security trust signals.
        negative_indicators: List of negative security threat signals.
        neutral_indicators: List of neutral/information indicators.
    """

    url: str
    prediction: str
    confidence: float
    risk_score: int
    risk_level: str
    features: dict[str, Any] = field(default_factory=dict)
    threat_intelligence: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    model_type: str = "unknown"
    analysis_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # New fields with defaults (v2.0)
    trust_score: int = 50
    ml_confidence: float = 0.0
    rule_confidence: float = 0.0
    decision_confidence: float = 0.0
    brand_detected: Optional[str] = None
    official_domain: bool = False
    ssl_status: str = "UNKNOWN"
    positive_indicators: list[str] = field(default_factory=list)
    negative_indicators: list[str] = field(default_factory=list)
    neutral_indicators: list[str] = field(default_factory=list)
    raw_probability: float = 0.0
    calibrated_probability: float = 0.0
    predicted_class: str = "unknown"
    decision_threshold: float = 0.5

    # Versioning fields (v2.1) -- populated from trained model metadata
    model_version: str = "unknown"
    feature_version: str = "unknown"

    # Phase 3 output fields (v3.0)
    transformer_confidence: Optional[float] = None
    threat_intelligence_score: float = 0.0
    decision_breakdown: dict[str, Any] = field(default_factory=dict)
    top_shap_features: list[dict[str, Any]] = field(default_factory=list)
    dataset_version: str = "unknown"
    calibration_version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the prediction result to a plain dictionary.

        Returns:
            Dictionary representation of the prediction result.
        """
        return asdict(self)

    def to_json(self, indent: int | None = 2) -> str:
        """
        Serialize the prediction result to a JSON string.

        Args:
            indent: Number of spaces for JSON indentation. None for compact output.

        Returns:
            JSON string representation of the prediction result.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictionResult":
        """
        Create a PredictionResult from a dictionary.

        Args:
            data: Dictionary containing prediction result fields.

        Returns:
            PredictionResult instance.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> "PredictionResult":
        """
        Deserialize a PredictionResult from a JSON string.

        Args:
            json_str: JSON string containing prediction result data.

        Returns:
            PredictionResult instance.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @property
    def is_phishing(self) -> bool:
        """Check if the prediction indicates phishing. (True only if prediction is 'Phishing')"""
        return self.prediction.lower() == "phishing"

    @property
    def is_suspicious(self) -> bool:
        """Check if the prediction indicates suspicious. (True only if prediction is 'Suspicious')"""
        return self.prediction.lower() == "suspicious"

    @property
    def is_high_risk(self) -> bool:
        """Check if the risk level is High or Critical."""
        return self.risk_level in ("Critical", "High")

    def summary(self) -> str:
        """
        Generate a concise one-line summary of the prediction.

        Returns:
            Human-readable summary string.
        """
        return (
            f"[{self.risk_level}] {self.prediction.upper()} "
            f"(confidence={self.confidence:.2f}, score={self.risk_score}/100, trust={self.trust_score}/100) -- {self.url}"
        )

    def __str__(self) -> str:
        """String representation with key fields."""
        reasons_str = "; ".join(self.reasons[:5]) if self.reasons else "None"
        return (
            f"PredictionResult(\n"
            f"  url={self.url!r},\n"
            f"  prediction={self.prediction!r},\n"
            f"  confidence={self.confidence:.4f},\n"
            f"  risk_score={self.risk_score},\n"
            f"  risk_level={self.risk_level!r},\n"
            f"  trust_score={self.trust_score},\n"
            f"  ssl_status={self.ssl_status!r},\n"
            f"  reasons=[{reasons_str}],\n"
            f"  model_type={self.model_type!r},\n"
            f"  timestamp={self.analysis_timestamp}\n"
            f")"
        )
