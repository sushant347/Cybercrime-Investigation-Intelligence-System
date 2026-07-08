"""Confidence Fusion (Feature 9) - Overall Threat Confidence, explained.

Combines the independent evidence streams the platform produces into one
0-100 **Overall Threat Confidence** with a transparent, auditable breakdown
of how the value was reached (forensic requirement: every score carries its
reasons and the weight of each contributing source).

Fusion is a weighted average over *available* sources only - missing sources
are dropped and the remaining weights renormalise, so the score degrades
gracefully and never silently assumes a value for an unavailable signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Default source weights (sum need not be 1.0; renormalised over what is
#: actually present). Justification: ML and blacklist evidence are the most
#: decisive, domain heuristics next, individual network facts least.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "ml": 0.35,
    "blacklist": 0.25,
    "reputation": 0.20,
    "domain": 0.10,
    "rule_engine": 0.10,
}


@dataclass
class FusionResult:
    """Fused confidence plus a per-source explanation."""

    overall_threat_confidence: int              # 0-100
    contributions: List[Dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    sources_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_threat_confidence": self.overall_threat_confidence,
            "contributions": self.contributions,
            "explanation": self.explanation,
            "sources_used": self.sources_used,
        }


class ConfidenceFusion:
    """Fuses ML + reputation + blacklist + domain + rule-engine evidence."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self._weights = weights or DEFAULT_WEIGHTS

    def fuse(
        self,
        ml_threat_probability: Optional[float] = None,   # 0-1, P(phishing)
        reputation: Optional[Dict[str, Any]] = None,
        rule_engine_score: Optional[float] = None,       # 0-1 threat-ness
    ) -> FusionResult:
        """Compute Overall Threat Confidence from whatever evidence exists.

        All inputs are optional; the score is a weighted average over the
        sources actually supplied, each expressed as a 0-1 "threat-ness".
        """
        signals: Dict[str, float] = {}
        notes: Dict[str, str] = {}

        if ml_threat_probability is not None:
            signals["ml"] = self._clamp(ml_threat_probability)
            notes["ml"] = f"ML phishing probability {signals['ml']:.2f}"

        if reputation:
            rep_score = reputation.get("reputation_score")
            if rep_score is not None:
                signals["reputation"] = self._clamp(1 - rep_score / 100)
                notes["reputation"] = (
                    f"Reputation {rep_score}/100 -> threat-ness "
                    f"{signals['reputation']:.2f}")
            blacklists = reputation.get("blacklists") or []
            listed = sum(1 for b in blacklists if b.get("available") and b.get("listed"))
            available = any(b.get("available") for b in blacklists)
            if available:
                signals["blacklist"] = 1.0 if listed else 0.0
                notes["blacklist"] = (
                    f"{listed} community feed hit(s)" if listed
                    else "no community feed hits")
            domain = reputation.get("domain_analysis") or {}
            if domain:
                signals["domain"] = self._clamp(min(1.0, (domain.get("risk_points") or 0) / 60))
                notes["domain"] = (
                    f"domain risk points {domain.get('risk_points', 0)}/60")

        if rule_engine_score is not None:
            signals["rule_engine"] = self._clamp(rule_engine_score)
            notes["rule_engine"] = f"rule-engine threat score {signals['rule_engine']:.2f}"

        if not signals:
            return FusionResult(0, [], "No evidence sources were available.", [])

        total_weight = sum(self._weights.get(src, 0.0) for src in signals)
        contributions: List[Dict[str, Any]] = []
        fused = 0.0
        for source, value in signals.items():
            weight = self._weights.get(source, 0.0)
            norm = weight / total_weight if total_weight else 1 / len(signals)
            fused += value * norm
            contributions.append({
                "source": source,
                "threat_ness": round(value, 3),
                "weight": round(norm, 3),
                "note": notes[source],
            })

        contributions.sort(key=lambda c: -c["weight"] * c["threat_ness"])
        confidence = int(round(fused * 100))
        explanation = self._explain(confidence, contributions)
        return FusionResult(confidence, contributions, explanation,
                            sorted(signals.keys()))

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _explain(confidence: int, contributions: List[Dict[str, Any]]) -> str:
        parts = ", ".join(
            f"{c['source']} ({c['note']}, weight {c['weight']:.0%})"
            for c in contributions)
        verdict = ("high threat" if confidence >= 70 else
                   "elevated threat" if confidence >= 45 else
                   "low threat")
        return (f"Overall Threat Confidence {confidence}/100 ({verdict}), a "
                f"weight-normalised fusion of the available sources: {parts}.")
