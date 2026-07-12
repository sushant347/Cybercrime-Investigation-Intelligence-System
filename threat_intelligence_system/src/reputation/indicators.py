"""Structured Threat Indicator generation (Feature 8) - additive, offline.

Derives named, severity-graded Indicators of Attack from the signals the
Reputation Engine already computes (domain analysis, blacklist hits, and any
available WHOIS/DNS/SSL intelligence). Each indicator is a self-contained,
auditable finding an investigator can cite verbatim:

    {name, severity, reason, confidence, recommendation}

No new network calls are made - indicators are a pure re-projection of data
already gathered, so generating them is free and fully deterministic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

# Severity ranking used for ordering and fusion weighting.
_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


@dataclass(frozen=True)
class ThreatIndicator:
    """One structured, investigator-readable finding."""

    name: str
    severity: str          # critical | high | medium | low | info
    reason: str
    confidence: float      # 0.0 - 1.0
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IndicatorGenerator:
    """Maps reputation signals to structured threat indicators."""

    def generate(self, reputation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return indicators (severity-sorted) for a reputation report."""
        indicators: List[ThreatIndicator] = []
        domain = reputation.get("domain_analysis") or {}
        intel = reputation.get("network_intelligence") or {}
        blacklists = reputation.get("blacklists") or []

        indicators += self._domain_indicators(domain)
        indicators += self._blacklist_indicators(blacklists)
        indicators += self._intel_indicators(intel)
        indicators += self._cloud_indicators(reputation.get("cloud_hosting") or {})

        indicators.sort(key=lambda i: (-_SEVERITY_RANK.get(i.severity, 0),
                                       -i.confidence))
        return [i.to_dict() for i in indicators]

    def _cloud_indicators(self, cloud: Dict[str, Any]) -> List[ThreatIndicator]:
        """Cloud-abuse indicator: only when cloud hosting meets phishing signals."""
        if not cloud.get("is_cloud_hosted") or not cloud.get("suspicious_context"):
            return []
        signals = ", ".join(cloud.get("signals", []))
        return [ThreatIndicator(
            "Cloud Abuse", "high",
            f"Hosted on {cloud.get('provider', 'a cloud service')} together with "
            f"phishing signals ({signals}).", 0.7,
            "Legitimate cloud hosting is being abused to serve a phishing page; "
            "treat the URL as high-risk despite the reputable host.")]

    # ---------------------------------------------------------------- domain

    def _domain_indicators(self, d: Dict[str, Any]) -> List[ThreatIndicator]:
        out: List[ThreatIndicator] = []
        if d.get("impersonated_brand"):
            out.append(ThreatIndicator(
                "Brand Impersonation", "critical",
                f"The domain embeds the brand '{d['impersonated_brand']}' without "
                "being its official domain.", 0.9,
                "Treat as a spoofing attempt targeting that brand's users."))
        if d.get("typosquat_of"):
            out.append(ThreatIndicator(
                "Typosquatting", "high",
                f"The domain is one edit away from '{d['typosquat_of']}'.", 0.85,
                "Warn users who may have mistyped the legitimate address."))
        if d.get("unicode_attack"):
            out.append(ThreatIndicator(
                "Unicode / Homograph Attack", "critical",
                "The domain uses non-Latin look-alike characters to imitate a "
                "legitimate name.", 0.9,
                "Block; verify the punycode form before any interaction."))
        elif d.get("homograph_suspect"):
            out.append(ThreatIndicator(
                "Homograph Suspect", "medium",
                "The domain changes under Unicode compatibility folding.", 0.6,
                "Inspect the canonical form for visual spoofing."))
        if d.get("suspicious_tld"):
            out.append(ThreatIndicator(
                "Suspicious Hosting Zone", "medium",
                "The domain uses a low-cost TLD frequently abused for phishing.",
                0.55, "Weight alongside other signals; not conclusive alone."))
        if float(d.get("random_domain_score") or 0) >= 0.6:
            out.append(ThreatIndicator(
                "Random / High-Entropy Domain", "medium",
                "The domain name is highly random, typical of auto-generated "
                "phishing or malware infrastructure.", 0.6,
                "Correlate with blacklist and hosting signals."))
        if int(d.get("subdomain_depth") or 0) >= 3:
            out.append(ThreatIndicator(
                "Deep Subdomain Nesting", "low",
                "An unusually deep subdomain chain is used to look official.",
                0.5, "Inspect the true registrable domain."))
        return out

    # ------------------------------------------------------------ blacklist

    def _blacklist_indicators(self, blacklists: List[Dict[str, Any]]) -> List[ThreatIndicator]:
        listed = [b for b in blacklists if b.get("available") and b.get("listed")]
        if not listed:
            return []
        sources = ", ".join(b.get("source", "?") for b in listed)
        return [ThreatIndicator(
            "Community Blacklist Hit", "critical",
            f"Listed on {len(listed)} community threat feed(s): {sources}.",
            0.95, "Strong external corroboration; treat the indicator as hostile.")]

    # ---------------------------------------------------------------- intel

    def _intel_indicators(self, intel: Dict[str, Any]) -> List[ThreatIndicator]:
        """Best-effort indicators from optional WHOIS/DNS/SSL intel (schema-
        tolerant: only fires when the relevant keys are actually present)."""
        out: List[ThreatIndicator] = []
        flat = {k.lower(): v for k, v in self._flatten(intel).items()}

        age = self._find(flat, ("domain_age_days", "age_days"))
        if isinstance(age, (int, float)) and age < 30:
            out.append(ThreatIndicator(
                "Newly Registered Domain", "high",
                f"The domain was registered {int(age)} day(s) ago; phishing "
                "domains are frequently brand-new.", 0.75,
                "Treat recent registration as a strong risk multiplier."))

        ssl_valid = self._find(flat, ("ssl_valid", "certificate_valid"))
        if ssl_valid is False:
            out.append(ThreatIndicator(
                "Expired or Invalid SSL", "high",
                "The site's SSL certificate is expired or invalid.", 0.7,
                "Do not submit credentials; the connection is not trustworthy."))
        if self._find(flat, ("ssl_self_signed", "self_signed")) is True:
            out.append(ThreatIndicator(
                "Self-Signed SSL", "medium",
                "The certificate is self-signed rather than CA-issued.", 0.6,
                "Unusual for legitimate consumer services."))

        if self._find(flat, ("spf", "has_spf")) is False:
            out.append(ThreatIndicator(
                "Missing SPF", "low",
                "No SPF record: the domain can be spoofed in email.", 0.5,
                "Note for email-borne phishing correlation."))
        if self._find(flat, ("dmarc", "has_dmarc")) is False:
            out.append(ThreatIndicator(
                "Missing DMARC", "low",
                "No DMARC record: spoofed mail from this domain is not rejected.",
                0.5, "Note for email-borne phishing correlation."))
        return out

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
        flat: Dict[str, Any] = {}
        if isinstance(obj, dict):
            for key, value in obj.items():
                flat.update(IndicatorGenerator._flatten(value, str(key)))
        else:
            flat[prefix] = obj
        return flat

    @staticmethod
    def _find(flat: Dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in flat:
                return flat[key]
        return None
