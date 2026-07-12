"""Threat Reputation Engine (facade) - additive, backward compatible.

Aggregates blacklists, domain analysis and the existing intelligence
connectors (WHOIS/DNS/SSL/GeoIP/VirusTotal via ``IntelligenceAggregator``)
into a single 0-100 **Reputation Score** with investigator-readable reasons.

Design guarantees: every source degrades gracefully (unavailable sources are
reported, never fatal); lookups run in a thread pool with hard timeouts;
results are TTL-cached; nothing in the existing prediction pipeline is
modified - this engine is a pure extension consumed alongside
``PhishingPredictor``.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .blacklists import BlacklistEngine, BlacklistResult
from .cache import TTLCache
from .domain_analysis import DomainAnalyzer
from .indicators import IndicatorGenerator
from .ioc import detect_ioc
from .normalizer import normalize_domain, normalize_url

_UNSET = object()  # sentinel: distinguishes "no intel" from "use default"


class ReputationEngine:
    """Multi-source reputation scoring for any IOC type."""

    def __init__(
        self,
        blacklists: Optional[BlacklistEngine] = None,
        domain_analyzer: Optional[DomainAnalyzer] = None,
        intelligence: Any = _UNSET,        # duck-typed IntelligenceAggregator; None disables
        cache: Optional[TTLCache] = None,
        timeout_seconds: float = 12.0,
        max_workers: int = 4,
    ) -> None:
        self._cache = cache or TTLCache(ttl_seconds=1800)
        self._blacklists = blacklists or BlacklistEngine(cache=self._cache)
        self._domains = domain_analyzer or DomainAnalyzer()
        from .cloud_hosting import CloudHostingDetector
        self._cloud = CloudHostingDetector()
        self._indicators = IndicatorGenerator()
        self._intel = self._default_intel() if intelligence is _UNSET else intelligence
        self._timeout = timeout_seconds
        self._workers = max_workers

    # ------------------------------------------------------------------ public

    def analyze(self, indicator: str) -> Dict[str, Any]:
        """Analyse any IOC; returns the expanded reputation JSON contract."""
        started = time.perf_counter()
        ioc = detect_ioc(indicator)
        cache_key = f"rep:{ioc.ioc_type}:{indicator.strip().lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        domain = self._domain_for(ioc)
        report: Dict[str, Any] = {
            "indicator": indicator,
            "normalized": normalize_url(indicator) if ioc.ioc_type == "url" else indicator.strip(),
            "ioc_type": ioc.ioc_type,
            "sources_available": [],
            "sources_unavailable": [],
            "blacklists": [],
            "domain_analysis": {},
            "network_intelligence": {},
            "reasons": [],
            "positive_signals": [],
            "negative_signals": [],
            "recommendations": [],
            "investigator_notes": "",
        }

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {}
            if ioc.ioc_type in ("url", "domain"):
                futures["blacklists"] = pool.submit(self._blacklists.check, indicator)
            if domain:
                futures["domain"] = pool.submit(self._domains.analyze, domain)
                if self._intel is not None:
                    futures["intel"] = pool.submit(self._safe_intel, domain)
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=self._timeout)
                except (FutureTimeout, Exception):  # noqa: BLE001
                    results[key] = None
                    report["sources_unavailable"].append(key)

        score = 100
        blacklist_results: List[BlacklistResult] = results.get("blacklists") or []
        for item in blacklist_results:
            report["blacklists"].append(asdict(item))
            (report["sources_available"] if item.available
             else report["sources_unavailable"]).append(item.source)
        hits = self._blacklists.hit_count(blacklist_results)
        if hits:
            score -= min(70, 45 * hits)
            report["negative_signals"].append(
                f"Listed on {hits} community threat feed(s)")
        elif any(b.available for b in blacklist_results):
            report["positive_signals"].append("No blacklist hits")

        analysis = results.get("domain")
        if analysis is not None:
            report["domain_analysis"] = asdict(analysis)
            score -= min(60, analysis.risk_points)
            report["reasons"].extend(analysis.explanations)
            if not analysis.explanations:
                report["positive_signals"].append(
                    "Domain structure shows no impersonation or randomness signals")

        # Cloud-hosting awareness (append-only): a cloud host is benign by
        # itself; it only reduces the score when combined with phishing signals.
        if ioc.ioc_type in ("url", "domain"):
            cloud = self._cloud.analyze(indicator, report.get("domain_analysis"))
            if cloud.is_cloud_hosted:
                report["cloud_hosting"] = cloud.to_dict()
                report["reasons"].extend(cloud.reasons)
                if cloud.suspicious_context:
                    score -= min(35, cloud.risk_points)
                    report["negative_signals"].append(
                        f"Cloud hosting ({cloud.provider}) abused with phishing signals")
                else:
                    report["positive_signals"].append(
                        f"Hosted on {cloud.provider} with no phishing signals")

        intel = results.get("intel")
        if intel:
            report["network_intelligence"] = intel
            report["sources_available"].extend(intel.keys())
            score += self._intel_adjustment(intel, report)

        # Non-domain IOCs (hash/wallet/phone) have no reputation sources here:
        # report them honestly as unscored rather than falsely "trusted".
        scored = bool(report["blacklists"]) or bool(report["domain_analysis"]) \
            or bool(report["network_intelligence"])
        score = max(0, min(100, score))
        if not scored:
            report["reputation_score"] = None
            report["reputation_level"] = "unknown"
            report["negative_signals"].append(
                "No reputation source available for this indicator type")
        else:
            report["reputation_score"] = score
            report["reputation_level"] = (
                "trusted" if score >= 85 else "neutral" if score >= 60
                else "suspicious" if score >= 35 else "hostile")
        report["recommendations"] = self._recommend(score, ioc.ioc_type)
        # Append-only: structured indicators derived from already-gathered
        # signals (no new network calls; backward compatible).
        report["indicators"] = self._indicators.generate(report)
        report["processing_time_ms"] = round((time.perf_counter() - started) * 1000, 1)

        self._cache.set(cache_key, report)
        return report

    # ---------------------------------------------------------------- internal

    @staticmethod
    def _default_intel() -> Any:
        """Existing aggregator, if importable (graceful otherwise)."""
        try:
            from src.intelligence.aggregator import IntelligenceAggregator
            return IntelligenceAggregator()
        except Exception:  # noqa: BLE001 - optional dependency path
            return None

    def _safe_intel(self, domain: str) -> Optional[Dict[str, Any]]:
        try:
            return self._cache.get_or_compute(
                f"intel:{domain}", lambda: self._intel.gather_dict(domain))
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _domain_for(ioc) -> str:
        if ioc.ioc_type == "url":
            return normalize_domain(
                normalize_url(ioc.value).split("://", 1)[-1].split("/", 1)[0].split(":")[0])
        if ioc.ioc_type == "domain":
            return normalize_domain(ioc.value)
        if ioc.ioc_type == "email":
            return normalize_domain(ioc.value.split("@", 1)[1])
        return ""

    @staticmethod
    def _intel_adjustment(intel: Dict[str, Any], report: Dict[str, Any]) -> int:
        """Score adjustments from WHOIS/DNS/SSL signals (best-effort keys)."""
        delta = 0
        flat = str(intel).lower()
        checks = [
            ("age" in flat and any(k in flat for k in ("year", "old")), 5,
             "Established domain age", None),
            ("spf" in flat, 3, "SPF configured", None),
            ("dmarc" in flat, 3, "DMARC configured", None),
            ("valid" in flat and "ssl" in flat, 4, "Valid SSL certificate", None),
        ]
        for condition, points, positive, _ in checks:
            if condition:
                delta += points
                report["positive_signals"].append(positive)
        return min(delta, 15)

    @staticmethod
    def _recommend(score: int, ioc_type: str) -> List[str]:
        if score < 35:
            return [
                "Treat this indicator as hostile; do not interact with it.",
                "Preserve the evidence and record the reputation report in the case file.",
                "Check entities.csv for other evidence referencing the same indicator.",
            ]
        if score < 60:
            return [
                "Exercise caution: several risk signals are present.",
                "Corroborate with the ML phishing prediction before concluding.",
            ]
        return ["No immediate action required; retain the report for completeness."]
