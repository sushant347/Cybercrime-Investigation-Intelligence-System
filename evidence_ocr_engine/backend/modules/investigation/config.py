"""Configuration for every Phase-2 investigation module.

All weights, thresholds, bands, stage definitions and file names live here -
services contain zero hardcoded values. ``INVESTIGATION_*`` environment
variables may override selected values via :meth:`InvestigationConfig.from_env`.

Storage tree (all new, independent of legacy storage)::

    storage/investigation/
        investigation_audit_log.csv
        <CASE_ID>/
            correlation_analysis.json       Module 1
            graph.json                      Module 2
            graph_statistics.json           Module 2
            graph_summary.json              Module 2
            campaign_analysis.json          Module 3
            suspect_assessment.json         Module 4
            timeline_analysis.json          Module 5
            analytics.json                  Module 6
            case_statistics.json            Module 6
            entity_statistics.json          Module 6
            investigation_report.json       Module 7
            investigation_report.md         Module 7
            case_priority.json              Module 8
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

from ..evidence.config import EvidenceConfig


@dataclass(frozen=True)
class InvestigationConfig:
    """Immutable runtime configuration injected into every Phase-2 service."""

    # ------------------------------------------------------------------ paths
    investigation_dir: Path = Path("storage") / "investigation"
    #: Legacy storage roots (READ-ONLY access).
    evidence_csv: Path = Path("storage") / "evidence.csv"
    entities_csv: Path = Path("storage") / "entities.csv"
    case_json_dir: Path = Path("storage") / "json"
    forensics_dir: Path = Path("storage") / "forensics"
    #: Optional threat-intelligence verdict file:
    #: ``{"indicators": {"<url-or-domain>": {"verdict": "malicious", ...}}}``
    threat_intel_json: Path = Path("storage") / "investigation" / "threat_intel_indicators.json"

    audit_csv_name: str = "investigation_audit_log.csv"

    # Report file names (Storage Requirements section of the Phase-2 spec)
    correlation_report_name: str = "correlation_analysis"
    graph_report_name: str = "graph"
    graph_statistics_name: str = "graph_statistics"
    graph_summary_name: str = "graph_summary"
    campaign_report_name: str = "campaign_analysis"
    suspect_report_name: str = "suspect_assessment"
    timeline_report_name: str = "timeline_analysis"
    analytics_report_name: str = "analytics"
    case_statistics_name: str = "case_statistics"
    entity_statistics_name: str = "entity_statistics"
    investigation_report_name: str = "investigation_report"
    priority_report_name: str = "case_priority"

    # ------------------------------------------------ Module 1: correlation
    #: Per-factor weights of the explainable correlation framework.
    correlation_weights: Dict[str, float] = field(default_factory=lambda: {
        "phones": 0.90, "emails": 0.85, "urls": 0.75, "domains": 0.60,
        "wallets": 1.00, "bank_accounts": 1.00, "social_accounts": 0.80,
        "file_hash": 1.00, "device_metadata": 0.70, "image_metadata": 0.50,
        "timeline_proximity": 0.40, "threat_intelligence": 0.80,
    })
    #: Max counted matches per factor (prevents one spammy entity dominating).
    correlation_factor_cap: int = 3
    #: Hours within which two evidence items are "temporally close".
    timeline_proximity_hours: float = 48.0
    #: Weight sum -> confidence via  1 - exp(-weight / normaliser).
    correlation_confidence_normaliser: float = 1.6
    #: Relationship bands over confidence (evaluated in order, score < value).
    relationship_bands: Dict[str, float] = field(default_factory=lambda: {
        "NO_RELATIONSHIP": 0.05, "WEAK": 0.30, "MEDIUM": 0.55,
        "STRONG": 0.80, "VERY_STRONG": 1.01,
    })

    # ------------------------------------------------------ Module 2: graph
    #: Entity types promoted to graph nodes (entity_type -> node_type).
    graph_entity_node_types: Dict[str, str] = field(default_factory=lambda: {
        "phones": "phone_number", "emails": "email", "urls": "url",
        "domains": "domain", "wallets": "wallet",
        "bank_accounts": "bank_account", "social_accounts": "social_media_account",
    })
    #: Correlation confidence required for a behavioural evidence-evidence edge.
    graph_behavioral_min_confidence: float = 0.55
    graph_top_hubs: int = 10

    # -------------------------------------------------- Module 3: campaigns
    #: Minimum pairwise correlation confidence for campaign membership links.
    campaign_min_confidence: float = 0.55
    campaign_min_members: int = 2
    campaign_id_prefix: str = "CAMP"
    campaign_signature_entities: int = 5

    # --------------------------------------------------- Module 4: suspects
    #: Entity types treated as suspect identity anchors.
    suspect_identity_types: Tuple[str, ...] = (
        "phones", "emails", "wallets", "bank_accounts", "social_accounts",
    )
    suspect_weights: Dict[str, float] = field(default_factory=lambda: {
        "identity_strength": 0.25,   # anchor type weight (wallet > phone > ...)
        "evidence_count": 0.20,      # breadth of appearances
        "evidence_confidence": 0.15, # mean Phase-1 evidence confidence
        "threat_intelligence": 0.15, # anchor flagged by threat intel
        "correlation_strength": 0.15,# how tightly its evidence set is linked
        "timeline_span": 0.10,       # sustained activity over time
    })
    suspect_identity_type_scores: Dict[str, float] = field(default_factory=lambda: {
        "wallets": 100.0, "bank_accounts": 100.0, "phones": 85.0,
        "emails": 75.0, "social_accounts": 70.0,
    })
    suspect_evidence_count_full_score: int = 4
    suspect_timeline_span_full_days: float = 7.0
    suspect_confidence_bands: Dict[str, float] = field(default_factory=lambda: {
        "VERY_LOW": 20.0, "LOW": 40.0, "MODERATE": 60.0,
        "HIGH": 80.0, "VERY_HIGH": 101.0,
    })
    suspect_risk_bands: Dict[str, float] = field(default_factory=lambda: {
        "LOW": 40.0, "MEDIUM": 60.0, "HIGH": 80.0, "CRITICAL": 101.0,
    })
    suspect_max_results: int = 50

    # --------------------------------------------------- Module 5: timeline
    #: Attack-stage keyword rules (stage -> lowercase keywords). Configuration
    #: driven so investigators can extend without code changes.
    timeline_stage_keywords: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "initial_contact": ("hello", "hi ", "namaste", "dear customer", "offer",
                            "prize", "lottery", "job", "congratulation"),
        "social_engineering": ("urgent", "verify", "suspended", "blocked",
                               "immediately", "warning", "last chance", "expire"),
        "credential_theft": ("password", "otp", "pin", "login", "log in",
                             "credential", "cvv", "security code"),
        "financial_transaction": ("esewa", "khalti", "ime pay", "bank", "transfer",
                                  "paid", "payment", "send money", "rs.", "npr",
                                  "account number", "wallet"),
        "post_attack": ("blocked me", "deleted", "not responding", "scammed",
                        "fraud", "police", "report", "cheated"),
    })
    #: Canonical stage order for progression analysis.
    timeline_stage_order: Tuple[str, ...] = (
        "initial_contact", "social_engineering", "credential_theft",
        "financial_transaction", "post_attack",
    )
    #: Events flagged critical when these entity types appear in the evidence.
    timeline_critical_entity_types: Tuple[str, ...] = ("otp", "money", "wallets",
                                                       "bank_accounts")

    # -------------------------------------------------- Module 6: analytics
    analytics_top_n: int = 10

    # ----------------------------------------------------- Module 8: priority
    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        "evidence_confidence": 0.20, "threat_intelligence": 0.20,
        "forgery_risk": 0.15, "campaign_size": 0.15,
        "correlation_strength": 0.15, "timeline_criticality": 0.15,
    })
    priority_bands: Dict[str, float] = field(default_factory=lambda: {
        "LOW": 30.0, "MEDIUM": 55.0, "HIGH": 75.0, "CRITICAL": 101.0,
    })
    priority_campaign_full_size: int = 5
    priority_critical_events_full: int = 3

    # ------------------------------------------------------------------ misc
    report_schema_version: str = "2.0"

    # ------------------------------------------------------------- factories
    @classmethod
    def from_evidence_config(cls, evidence_config: EvidenceConfig) -> "InvestigationConfig":
        """Anchor all paths inside the existing storage directory."""
        storage = evidence_config.storage_dir
        investigation = storage / "investigation"
        return cls(
            investigation_dir=investigation,
            evidence_csv=evidence_config.evidence_csv,
            entities_csv=storage / "entities.csv",
            case_json_dir=evidence_config.json_dir,
            forensics_dir=storage / "forensics",
            threat_intel_json=investigation / "threat_intel_indicators.json",
        )

    @classmethod
    def from_env(cls, evidence_config: EvidenceConfig) -> "InvestigationConfig":
        base = cls.from_evidence_config(evidence_config)
        investigation = Path(os.environ.get("INVESTIGATION_STORAGE_DIR",
                                            str(base.investigation_dir)))
        threat = Path(os.environ.get("INVESTIGATION_THREAT_INTEL_JSON",
                                     str(investigation / "threat_intel_indicators.json")))
        return cls(
            investigation_dir=investigation,
            evidence_csv=base.evidence_csv,
            entities_csv=base.entities_csv,
            case_json_dir=base.case_json_dir,
            forensics_dir=base.forensics_dir,
            threat_intel_json=threat,
            timeline_proximity_hours=float(
                os.environ.get("INVESTIGATION_TIMELINE_PROXIMITY_HOURS", "48")
            ),
            campaign_min_confidence=float(
                os.environ.get("INVESTIGATION_CAMPAIGN_MIN_CONFIDENCE", "0.55")
            ),
        )

    # ------------------------------------------------------------------ paths
    @property
    def audit_csv(self) -> Path:
        return self.investigation_dir / self.audit_csv_name

    def case_dir(self, case_id: str) -> Path:
        return self.investigation_dir / case_id

    def ensure_directories(self) -> None:
        self.investigation_dir.mkdir(parents=True, exist_ok=True)
