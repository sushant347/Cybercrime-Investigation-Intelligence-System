"""Investigator-facing report generator (additive, optional).

Merges the existing ``PredictionResult`` (ML prediction, risk/trust/
confidence, reasons, feature importance, intelligence details - untouched)
with the new ``ReputationEngine`` output into one structured report with the
sections investigators expect. Produces both an expanded JSON object and a
formatted plain-text CLI report.

Backward compatibility: this consumes existing objects read-only; it never
mutates them and never changes their contracts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .fusion import ConfidenceFusion


@dataclass
class ThreatReport:
    """Unified investigator report over prediction + reputation."""

    indicator: str
    prediction: Dict[str, Any] = field(default_factory=dict)
    reputation: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    investigator_notes: str = ""
    threat_confidence: Dict[str, Any] = field(default_factory=dict)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        rep = self.reputation
        pred = self.prediction
        return {
            "summary": self._summary(),
            "threat_reputation": {
                "reputation_score": rep.get("reputation_score"),
                "reputation_level": rep.get("reputation_level"),
                "ioc_type": rep.get("ioc_type"),
                "reasons": rep.get("reasons", []),
            },
            "ml_prediction": pred,                      # existing contract, verbatim
            "threat_intelligence": rep.get("network_intelligence", {}),
            "indicators": {
                "indicator": self.indicator,
                "normalized": rep.get("normalized", self.indicator),
                "ioc_type": rep.get("ioc_type", "unknown"),
                "blacklists": rep.get("blacklists", []),
                "domain_analysis": rep.get("domain_analysis", {}),
            },
            "positive_signals": rep.get("positive_signals", []),
            "negative_signals": rep.get("negative_signals", []),
            "risk_factors": rep.get("reasons", []),
            "threat_indicators": rep.get("indicators", []),
            "overall_threat_confidence": self.threat_confidence,
            "recommendations": rep.get("recommendations", []),
            "evidence_references": self.evidence_refs,
            "investigator_notes": self.investigator_notes,
            "sources_available": rep.get("sources_available", []),
            "sources_unavailable": rep.get("sources_unavailable", []),
            "processing_time_ms": rep.get("processing_time_ms"),
        }

    def to_cli(self) -> str:
        d = self.to_dict()
        lines = [
            "=" * 66,
            "  THREAT INTELLIGENCE REPORT",
            "=" * 66,
            f"  Indicator      : {self.indicator}",
            f"  Type           : {d['indicators']['ioc_type']}",
            f"  Summary        : {d['summary']}",
            "-" * 66,
            "  THREAT REPUTATION",
            f"    Score        : {d['threat_reputation']['reputation_score']}/100"
            f"  ({d['threat_reputation']['reputation_level']})",
        ]
        for reason in d["threat_reputation"]["reasons"]:
            lines.append(f"      - {reason}")
        if self.prediction:
            lines += ["-" * 66, "  ML PREDICTION",
                      f"    {self.prediction.get('prediction', 'n/a')} "
                      f"(risk={self.prediction.get('risk_score', 'n/a')}, "
                      f"confidence={self.prediction.get('confidence', 'n/a')})"]
        lines += ["-" * 66, "  POSITIVE SIGNALS"]
        lines += [f"      + {s}" for s in d["positive_signals"]] or ["      (none)"]
        lines += ["  NEGATIVE SIGNALS"]
        lines += [f"      - {s}" for s in d["negative_signals"]] or ["      (none)"]
        conf = d.get("overall_threat_confidence") or {}
        if conf.get("overall_threat_confidence") is not None:
            lines += ["-" * 66,
                      f"  OVERALL THREAT CONFIDENCE : {conf['overall_threat_confidence']}/100"]
            if conf.get("explanation"):
                lines.append(f"    {conf['explanation']}")
        if d.get("threat_indicators"):
            lines += ["-" * 66, "  THREAT INDICATORS"]
            for ind in d["threat_indicators"]:
                lines.append(f"      [{ind['severity'].upper()}] {ind['name']} "
                             f"(confidence {ind['confidence']:.0%})")
                lines.append(f"          {ind['reason']}")
        lines += ["-" * 66, "  RECOMMENDATIONS"]
        lines += [f"      * {r}" for r in d["recommendations"]]
        if self.evidence_refs:
            lines += ["-" * 66, "  EVIDENCE REFERENCES"]
            lines += [f"      {ref}" for ref in self.evidence_refs]
        lines.append("=" * 66)
        return "\n".join(lines)

    # ---------------------------------------------------------------- internal

    def _summary(self) -> str:
        level = self.reputation.get("reputation_level", "unknown")
        score = self.reputation.get("reputation_score", "n/a")
        verdict = ""
        if self.prediction:
            verdict = f", ML says {self.prediction.get('prediction', 'n/a')}"
        return (f"Reputation {score}/100 ({level}){verdict}. "
                f"{len(self.reputation.get('reasons', []))} risk factor(s) identified.")


class ReportGenerator:
    """Builds a :class:`ThreatReport` from optional prediction + reputation."""

    def build(
        self,
        indicator: str,
        prediction: Optional[Any] = None,
        reputation: Optional[Dict[str, Any]] = None,
        evidence_refs: Optional[List[str]] = None,
        investigator_notes: str = "",
    ) -> ThreatReport:
        pred_dict: Dict[str, Any] = {}
        if prediction is not None:
            # Accept an existing PredictionResult (has to_dict/to_json) or a dict.
            if hasattr(prediction, "to_dict"):
                pred_dict = prediction.to_dict()
            elif isinstance(prediction, dict):
                pred_dict = prediction
        rep = reputation or {}
        ml_prob = self._ml_probability(pred_dict)
        rule_score = self._rule_score(pred_dict)
        fusion = ConfidenceFusion().fuse(
            ml_threat_probability=ml_prob,
            reputation=rep,
            rule_engine_score=rule_score,
        ).to_dict()
        return ThreatReport(
            indicator=indicator,
            prediction=pred_dict,
            reputation=rep,
            evidence_refs=evidence_refs or [],
            investigator_notes=investigator_notes,
            threat_confidence=fusion,
        )

    @staticmethod
    def _ml_probability(pred: Dict[str, Any]) -> Optional[float]:
        """Best-effort P(phishing) from an existing prediction dict."""
        for key in ("phishing_probability", "threat_probability", "probability"):
            if isinstance(pred.get(key), (int, float)):
                return float(pred[key])
        # Derive from confidence + label without changing the ML contract.
        conf, label = pred.get("confidence"), str(pred.get("prediction", "")).lower()
        if isinstance(conf, (int, float)):
            conf = conf / 100 if conf > 1 else conf
            return conf if "phish" in label or "malic" in label else 1 - conf
        risk = pred.get("risk_score")
        return risk / 100 if isinstance(risk, (int, float)) else None

    @staticmethod
    def _rule_score(pred: Dict[str, Any]) -> Optional[float]:
        rule = pred.get("rule_score") or pred.get("rule_engine_score")
        if isinstance(rule, (int, float)):
            return rule / 100 if rule > 1 else rule
        return None
