"""
Composite threat scoring engine.

Combines the AI model prediction confidence with signals derived from threat
intelligence (domain age, WHOIS, VirusTotal, SSL, DNS) and URL-level features
(brand similarity, TLD risk) into a single 0-100 risk score.

Each signal contributor returns a normalised 0.0-1.0 score.  The final score
is the weighted sum of all contributors, scaled to 0-100 and clamped.
"""

from __future__ import annotations

from typing import Any

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ThreatScorer:
    """Weighted composite threat scorer.

    The scorer is driven by a weight dictionary that maps signal names to
    their relative importance (floats that should sum close to 1.0).  Weights
    default to ``settings.threat.score_weights``.

    Attributes:
        weights: Copy of the active weight mapping.
        thresholds: Risk-level threshold mapping from configuration.
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        """Initialise the scorer with optional custom weights.

        Args:
            weights: Dictionary mapping signal names to weight floats.
                If ``None``, the values from ``get_settings().threat.score_weights``
                are used.
        """
        settings = get_settings()
        self.weights: dict[str, float] = dict(weights or settings.threat.score_weights)
        self.thresholds: dict[str, int] = dict(settings.threat.risk_thresholds)
        self.decision_weights: dict[str, float] = dict(settings.threat.decision_weights)

        # Caches from settings used by individual scorers
        self._known_brands: list[str] = list(settings.threat.known_brands)
        self._suspicious_tlds: list[str] = list(settings.threat.suspicious_tlds)

        logger.debug("ThreatScorer initialised with weights: %s", self.weights)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        prediction_confidence: float,
        prediction_label: str,
        features: dict[str, Any],
        intelligence: dict[str, Any],
    ) -> tuple[int, str]:
        """Compute the composite risk score and level.

        Args:
            prediction_confidence: AI model confidence (0.0-1.0).
            prediction_label: AI model prediction (``'phishing'`` or
                ``'legitimate'``).
            features: Extracted URL features dictionary.
            intelligence: Flat intelligence dictionary (e.g. from
                ``IntelligenceAggregator.gather_dict``).

        Returns:
            Tuple of ``(risk_score, risk_level)`` where *risk_score* is an
            integer 0-100 and *risk_level* is one of ``'Critical'``,
            ``'High'``, ``'Medium'``, ``'Low'``, or ``'Safe'``.
        """
        try:
            # 1. ML Score Component
            ml_prob = (
                prediction_confidence
                if prediction_label.lower() == "phishing"
                else 1.0 - prediction_confidence
            )

            # 2. Rule Engine Score Component
            rule_score = features.get("rule_score", 0.0)

            # 3. Threat Intelligence Score Component
            intel_scores: dict[str, float] = {
                "domain_age": self._score_domain_age(intelligence),
                "whois": self._score_whois(intelligence),
                "virustotal": self._score_virustotal(intelligence),
                "ssl": self._score_ssl(intelligence),
                "dns": self._score_dns(intelligence),
                "tld_risk": self._score_tld_risk(features),
                "brand_similarity": self._score_brand_similarity(features),
            }

            weighted_intel_sum: float = 0.0
            total_intel_weight: float = 0.0
            for signal, val in intel_scores.items():
                w = self.weights.get(signal, 0.10)
                weighted_intel_sum += val * w
                total_intel_weight += w

            intel_score = (
                (weighted_intel_sum / total_intel_weight)
                if total_intel_weight > 0
                else 0.0
            )

            # 4. Domain Trust Score (0-100)
            trust = 50.0  # Neutral baseline start

            # Increments (building trust)
            if features.get("official_domain_match", False):
                trust += 30.0
            if intelligence.get("ssl_ssl_status") == "VALID":
                trust += 15.0
            if intelligence.get("dns_has_spf", False):
                trust += 10.0
            if intelligence.get("dns_has_dmarc", False):
                trust += 10.0

            dnssec = intelligence.get("whois_dnssec")
            if dnssec and isinstance(dnssec, str) and "unsigned" not in dnssec.lower():
                trust += 10.0

            if intelligence.get("ssl_has_hsts", False):
                trust += 5.0

            age_days = intelligence.get("whois_domain_age_days")
            if age_days is not None:
                if age_days > 365 * 5:  # > 5 years
                    trust += 15.0
                elif age_days > 365:  # > 1 year
                    trust += 10.0

            asn_org = str(intelligence.get("geoip_asn_org", "")).lower()
            trusted_asns = ["google", "amazon", "microsoft", "cloudflare", "facebook", "fastly", "akamai"]
            if any(t in asn_org for t in trusted_asns):
                trust += 5.0

            registrar = str(intelligence.get("whois_registrar", "")).lower()
            trusted_registrars = ["godaddy", "namecheap", "gandi", "markmonitor", "network solutions", "google"]
            if any(t in registrar for t in trusted_registrars):
                trust += 5.0

            if intelligence.get("virustotal_success", False) and intelligence.get("virustotal_positives", 0) == 0:
                trust += 10.0

            # Decrements (degrading trust)
            brand_detected = features.get("brand_detected")
            official_domain_match = features.get("official_domain_match", False)
            if brand_detected is not None and not official_domain_match:
                trust -= 35.0

            if features.get("is_typosquatting", 0) == 1:
                trust -= 30.0

            if features.get("url_entropy", 0.0) > 4.5 or features.get("domain_entropy", 0.0) > 4.0:
                trust -= 15.0

            if age_days is not None and age_days < 90:
                trust -= 25.0

            if features.get("is_suspicious_tld", 0) == 1:
                trust -= 15.0

            if features.get("is_url_shortener", 0) == 1:
                trust -= 15.0

            subdomains = features.get("subdomain_count", 0)
            if subdomains >= 3:
                trust -= 10.0

            # Clamp trust score
            trust_score = max(0, min(100, int(round(trust))))
            features["trust_score"] = trust_score  # Cache on features so predictor can fetch it

            # Inverse trust score represents the risk threat contribution
            trust_threat = 1.0 - (trust_score / 100.0)

            # 5. Combined Hybrid Decision Engine
            w_ml = self.decision_weights.get("ml_probability", 0.35)
            w_rule = self.decision_weights.get("rule_engine", 0.30)
            w_intel = self.decision_weights.get("threat_intelligence", 0.20)
            w_trust = self.decision_weights.get("domain_trust_signals", 0.15)

            composite_score = (
                (ml_prob * w_ml)
                + (rule_score * w_rule)
                + (intel_score * w_intel)
                + (trust_threat * w_trust)
            )

            w_total = w_ml + w_rule + w_intel + w_trust
            if w_total > 0:
                composite_score /= w_total

            risk_score: int = max(0, min(100, int(round(composite_score * 100))))
            
            # Explicitly verified official domains are clamped to Safe/Legitimate range (max 20)
            if official_domain_match:
                risk_score = min(risk_score, 20)
                
            risk_level: str = self._get_risk_level(risk_score)

            logger.debug(
                "Threat score=%d (%s), trust_score=%d, ml=%.3f, rule=%.3f, intel=%.3f, trust_threat=%.3f",
                risk_score, risk_level, trust_score, ml_prob, rule_score, intel_score, trust_threat,
            )

            return risk_score, risk_level

        except Exception as exc:
            logger.exception("Scoring error: %s", exc)
            # Default fallback on error
            return 50, "Medium"

    # ------------------------------------------------------------------
    # Component scoring functions (each returns 0.0 - 1.0)
    # ------------------------------------------------------------------

    @staticmethod
    def _score_ai_prediction(confidence: float, label: str) -> float:
        """Score based on the AI model's prediction and confidence.

        A high-confidence *phishing* prediction drives the score towards 1.0.
        A high-confidence *legitimate* prediction drives it towards 0.0.

        Args:
            confidence: Model confidence (0.0-1.0).
            label: Predicted label string.

        Returns:
            Normalised score 0.0-1.0.
        """
        confidence = max(0.0, min(1.0, confidence))

        if label.lower() == "phishing":
            return confidence
        else:
            return 1.0 - confidence

    @staticmethod
    def _score_domain_age(intelligence: dict[str, Any]) -> float:
        """Score based on domain age in days.

        Newer domains are riskier.  Domains younger than 30 days score 1.0,
        those older than 365 days score 0.0.

        Args:
            intelligence: Flat intelligence dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        age_days: int | None = intelligence.get("whois_domain_age_days")
        if age_days is None:
            return 0.5  # unknown -> neutral

        if age_days < 0:
            return 1.0
        if age_days <= 7:
            return 1.0
        if age_days <= 30:
            return 0.85
        if age_days <= 90:
            return 0.6
        if age_days <= 180:
            return 0.4
        if age_days <= 365:
            return 0.2
        return 0.0

    @staticmethod
    def _score_whois(intelligence: dict[str, Any]) -> float:
        """Score based on WHOIS registration quality signals.

        Missing registrar, missing registrant country, or WHOIS-private domains
        raise the score.

        Args:
            intelligence: Flat intelligence dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        if not intelligence.get("whois_success", False):
            return 0.5  # data unavailable -> neutral

        risk: float = 0.0
        factors: int = 0

        # No registrar
        if not intelligence.get("whois_registrar"):
            risk += 1.0
        factors += 1

        # No registrant country
        if not intelligence.get("whois_registrant_country"):
            risk += 0.6
        factors += 1

        # DNSSEC not enabled
        dnssec = intelligence.get("whois_dnssec")
        if dnssec and isinstance(dnssec, str) and "unsigned" in dnssec.lower():
            risk += 0.3
        factors += 1

        # Privacy-protected / redacted registrar names
        registrar = str(intelligence.get("whois_registrar", "")).lower()
        privacy_keywords = ("privacy", "redacted", "proxy", "whoisguard", "protected")
        if any(kw in registrar for kw in privacy_keywords):
            risk += 0.5
        factors += 1

        return min(1.0, risk / max(factors, 1))

    @staticmethod
    def _score_virustotal(intelligence: dict[str, Any]) -> float:
        """Score based on VirusTotal detection ratio.

        More detections relative to total scanners -> higher score.

        Args:
            intelligence: Flat intelligence dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        if not intelligence.get("virustotal_success", False):
            return 0.0  # no VT data -> assume benign (conservative)

        positives: int = intelligence.get("virustotal_positives", 0)
        total: int = intelligence.get("virustotal_total_scanners", 1)

        if total <= 0:
            return 0.0

        ratio = positives / total

        if ratio >= 0.3:
            return 1.0
        if ratio >= 0.15:
            return 0.85
        if ratio >= 0.05:
            return 0.6
        if positives >= 1:
            return 0.35
        return 0.0

    @staticmethod
    def _score_ssl(intelligence: dict[str, Any]) -> float:
        """Score based on SSL/TLS certificate quality.

        Missing, expired, or self-signed certificates raise the score.
        UNKNOWN or lookup failures are assigned neutral 0.5 risk.

        Args:
            intelligence: Flat intelligence dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        if not intelligence.get("ssl_success", False):
            return 0.5

        has_ssl = intelligence.get("ssl_has_ssl", False)
        ssl_status = intelligence.get("ssl_ssl_status", "")

        # UNKNOWN lookup status (v2.0)
        if ssl_status == "UNKNOWN" or has_ssl == "unknown":
            return 0.5

        if not has_ssl:
            return 1.0

        risk: float = 0.0
        factors: int = 0

        # Expired certificate
        if intelligence.get("ssl_is_expired", False):
            risk += 1.0
        factors += 1

        # Self-signed certificate
        if intelligence.get("ssl_is_self_signed", False):
            risk += 0.9
        factors += 1

        # Short-lived or imminent expiry (≤ 30 days)
        days_until = intelligence.get("ssl_days_until_expiry")
        if isinstance(days_until, (int, float)):
            if days_until < 0:
                risk += 1.0
            elif days_until <= 7:
                risk += 0.7
            elif days_until <= 30:
                risk += 0.4
        factors += 1

        return min(1.0, risk / max(factors, 1))

    @staticmethod
    def _score_dns(intelligence: dict[str, Any]) -> float:
        """Score based on DNS hygiene signals.

        Missing SPF/DMARC records or very few DNS records raise the score.

        Args:
            intelligence: Flat intelligence dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        if not intelligence.get("dns_success", False):
            return 0.5

        risk: float = 0.0
        factors: int = 0

        if not intelligence.get("dns_has_spf", False):
            risk += 0.7
        factors += 1

        if not intelligence.get("dns_has_dmarc", False):
            risk += 0.6
        factors += 1

        record_count = intelligence.get("dns_record_count", 0)
        if record_count == 0:
            risk += 1.0
        elif record_count <= 2:
            risk += 0.5
        factors += 1

        return min(1.0, risk / max(factors, 1))

    def _score_brand_similarity(self, features: dict[str, Any]) -> float:
        """Score based on brand-name impersonation heuristics.

        Checks whether the domain or URL contains substrings of well-known
        brand names.

        Args:
            features: Extracted URL features dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        domain: str = str(features.get("domain", "")).lower()
        url: str = str(features.get("url", "")).lower()

        if not domain:
            return 0.0

        matched_brands: list[str] = []
        for brand in self._known_brands:
            # Only flag if the brand appears as a *substring* of the domain
            # but the domain itself is NOT the brand's legitimate domain.
            if brand in domain and domain not in (
                f"{brand}.com",
                f"{brand}.net",
                f"{brand}.org",
                f"www.{brand}.com",
            ):
                matched_brands.append(brand)

        if not matched_brands:
            # Also check the full URL path for brand keywords
            for brand in self._known_brands:
                if brand in url and brand not in domain:
                    matched_brands.append(brand)

        if len(matched_brands) >= 2:
            return 1.0
        if len(matched_brands) == 1:
            return 0.8
        return 0.0

    def _score_tld_risk(self, features: dict[str, Any]) -> float:
        """Score based on the top-level domain's abuse reputation.

        Args:
            features: Extracted URL features dictionary.

        Returns:
            Normalised score 0.0-1.0.
        """
        tld: str = str(features.get("tld", "")).lower().lstrip(".")

        if not tld:
            return 0.3

        if tld in self._suspicious_tlds:
            return 1.0

        # Well-known legitimate TLDs
        safe_tlds = {"com", "org", "net", "edu", "gov", "mil", "int"}
        if tld in safe_tlds:
            return 0.0

        # Country-code TLDs -- moderate risk
        if len(tld) == 2:
            return 0.2

        return 0.3

    # ------------------------------------------------------------------
    # Risk-level mapping
    # ------------------------------------------------------------------

    def _get_risk_level(self, score: int) -> str:
        """Map a numeric risk score to a human-readable risk level.

        The mapping uses the thresholds defined in
        ``settings.threat.risk_thresholds``.

        Args:
            score: Integer risk score (0-100).

        Returns:
            Risk level string: ``'Critical'``, ``'High'``, ``'Medium'``,
            ``'Low'``, or ``'Safe'``.
        """
        # Iterate from highest threshold to lowest
        for level in ("Critical", "High", "Medium", "Low"):
            threshold = self.thresholds.get(level, 0)
            if score >= threshold:
                return level
        return "Safe"
