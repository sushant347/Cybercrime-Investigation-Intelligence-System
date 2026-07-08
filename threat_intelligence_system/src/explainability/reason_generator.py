"""
Human-readable explainability engine for phishing predictions.

Examines extracted URL features and threat-intelligence data to produce a list
of concise, user-facing English sentences that explain *why* a URL was
classified as phishing (or legitimate).

Only reasons that actually apply to the analysed URL are included.
"""

from __future__ import annotations

import math
import re
from typing import Any

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReasonGenerator:
    """Generator for human-readable prediction explanations.

    Each public call to :meth:`generate` returns a list of plain-English
    reason strings derived from URL features, threat-intelligence data, and
    the AI prediction itself.

    The generator is stateless; all relevant context is passed to
    :meth:`generate` at call-time.
    """

    def __init__(self) -> None:
        """Initialise the reason generator and load reference data from settings."""
        settings = get_settings()
        self._known_brands: list[str] = list(settings.threat.known_brands)
        self._suspicious_tlds: list[str] = list(settings.threat.suspicious_tlds)
        self._suspicious_keywords: list[str] = list(settings.threat.suspicious_keywords)
        self._url_shorteners: list[str] = list(settings.threat.url_shorteners)
        self._homograph_map: dict[str, str] = dict(settings.threat.homograph_map)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        features: dict[str, Any],
        intelligence: dict[str, Any],
        prediction: str,
        confidence: float,
        final_prediction: Optional[str] = None,
        risk_score: Optional[int] = None,
    ) -> list[str]:
        """Generate a list of human-readable reasons for the prediction.

        Each individual check method appends to the internal *reasons* list
        only when its condition is satisfied, so the output contains **only**
        relevant explanations.

        Args:
            features: Extracted URL feature dictionary.
            intelligence: Flat intelligence dictionary (e.g. from
                ``IntelligenceAggregator.gather_dict``).
            prediction: AI model prediction label (``'phishing'`` or
                ``'legitimate'``).
            confidence: AI model confidence (0.0-1.0).
            final_prediction: Optional final hybrid prediction class.
            risk_score: Optional final composite risk score.

        Returns:
            Ordered list of reason strings.
        """
        reasons: list[str] = []

        # AI-model signal
        self._check_ai_prediction(reasons, prediction, confidence)

        # Domain-age & WHOIS
        self._check_young_domain(reasons, intelligence)

        # TLD
        self._check_suspicious_tld(reasons, features)

        # Brand impersonation
        self._check_brand_impersonation(reasons, features)

        # SSL
        self._check_missing_ssl(reasons, intelligence)
        self._check_ssl_issues(reasons, intelligence)

        # URL structure
        self._check_ip_based_url(reasons, features)
        self._check_url_shortener(reasons, features)
        self._check_punycode_homograph(reasons, features)
        self._check_long_url(reasons, features)
        self._check_many_subdomains(reasons, features)
        self._check_no_https(reasons, features)
        self._check_high_entropy(reasons, features)
        self._check_suspicious_keywords(reasons, features)

        # External intelligence
        self._check_virustotal_detections(reasons, intelligence)

        # DNS hygiene
        self._check_dns_issues(reasons, intelligence)

        # Prepend Final Explanation if provided
        if final_prediction is not None and risk_score is not None:
            raw_ml_phishing = (prediction.lower() == "phishing")
            final_legit = (final_prediction.lower() == "legitimate")
            final_phish = (final_prediction.lower() == "phishing")
            final_suspicious = (final_prediction.lower() == "suspicious")
            
            explanation = ""
            if raw_ml_phishing and final_legit:
                explanation = (
                    "Although the ML model indicated phishing, the hybrid decision engine "
                    "determined this URL is legitimate because trusted signals outweighed the ML prediction."
                )
            elif not raw_ml_phishing and final_phish:
                explanation = (
                    "Although the ML model indicated the URL is legitimate, the hybrid decision engine "
                    "determined it is phishing because malicious signals or rule engine matches outweighed the ML prediction."
                )
            elif final_suspicious:
                explanation = (
                    "The hybrid decision engine flagged this URL as suspicious due to mixed signals "
                    "between the ML model, active rules, and threat intelligence."
                )
            elif raw_ml_phishing and final_phish:
                explanation = (
                    "The hybrid decision engine confirmed this URL is phishing based on agreement "
                    "between the ML model and threat indicators."
                )
            else:
                explanation = (
                    "The hybrid decision engine confirmed this URL is legitimate based on trusted signals "
                    "and ML model agreement."
                )
            
            reasons.insert(0, explanation)

        logger.debug(
            "Generated %d reasons for prediction=%s, confidence=%.2f",
            len(reasons), prediction, confidence,
        )

        return reasons

    # ------------------------------------------------------------------
    # Individual reason checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_ai_prediction(
        reasons: list[str], prediction: str, confidence: float
    ) -> None:
        """Add a reason based on the AI model's raw output.

        Args:
            reasons: Accumulating list of reasons.
            prediction: Model prediction label.
            confidence: Model confidence.
        """
        pct = int(round(confidence * 100))
        if prediction.lower() == "phishing":
            reasons.append(
                f"AI model classified this URL as phishing with {pct}% confidence."
            )
        else:
            if confidence < 0.6:
                reasons.append(
                    f"AI model classified this URL as legitimate but with low "
                    f"confidence ({pct}%)."
                )

    @staticmethod
    def _check_young_domain(
        reasons: list[str], intelligence: dict[str, Any]
    ) -> None:
        """Flag domains registered less than 30 days ago.

        Args:
            reasons: Accumulating list of reasons.
            intelligence: Flat intelligence dictionary.
        """
        age_days: int | None = intelligence.get("whois_domain_age_days")
        if age_days is not None and age_days < 30:
            reasons.append(
                f"The domain was registered only {age_days} day(s) ago, which "
                f"is common for phishing sites."
            )

    def _check_suspicious_tld(
        self, reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag TLDs known for high abuse rates.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        is_suspicious = features.get("is_suspicious_tld", 0)
        if is_suspicious:
            tld_risk = features.get("tld_risk_score", 0.5)
            reasons.append(
                f"The top-level domain is frequently associated with "
                f"phishing and spam campaigns (risk score: {tld_risk:.1f})."
            )

    def _check_brand_impersonation(
        self, reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs that appear to impersonate a known brand.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        closest_brand = features.get("closest_brand", "")
        brand_in_domain = features.get("brand_in_domain", 0)
        brand_in_subdomain = features.get("brand_in_subdomain", 0)
        brand_in_path = features.get("brand_in_path", 0)
        is_typosquatting = features.get("is_typosquatting", 0)
        similarity = features.get("brand_similarity_score", 0.0)

        if is_typosquatting:
            reasons.append(
                f"The domain closely resembles the brand '{closest_brand}' "
                f"(similarity: {similarity:.0%}) -- possible typosquatting."
            )
        elif brand_in_domain:
            reasons.append(
                f"The domain contains the brand name '{closest_brand}' but is not the "
                f"official domain -- possible brand impersonation."
            )
        elif brand_in_subdomain:
            reasons.append(
                f"The subdomain contains the brand name '{closest_brand}' -- "
                f"possible brand impersonation."
            )
        elif brand_in_path:
            reasons.append(
                f"The URL path contains the brand name '{closest_brand}' -- "
                f"possible phishing lure."
            )

    @staticmethod
    def _check_missing_ssl(
        reasons: list[str], intelligence: dict[str, Any]
    ) -> None:
        """Flag domains with missing or unverifiable SSL certificates.

        Args:
            reasons: Accumulating list of reasons.
            intelligence: Flat intelligence dictionary.
        """
        if "ssl_success" not in intelligence:
            return

        ssl_success = intelligence.get("ssl_success", False)
        has_ssl = intelligence.get("ssl_has_ssl")
        ssl_status = intelligence.get("ssl_ssl_status", "UNKNOWN")

        if ssl_success:
            if ssl_status == "UNKNOWN" or has_ssl == "unknown":
                reasons.append("SSL status could not be verified.")
            elif has_ssl is False or ssl_status == "INVALID":
                reasons.append(
                    "The domain does not have a valid SSL/TLS certificate, meaning "
                    "connections are unencrypted."
                )
        else:
            reasons.append("SSL status could not be verified.")

    @staticmethod
    def _check_ssl_issues(
        reasons: list[str], intelligence: dict[str, Any]
    ) -> None:
        """Flag expired or self-signed SSL certificates.

        Args:
            reasons: Accumulating list of reasons.
            intelligence: Flat intelligence dictionary.
        """
        if intelligence.get("ssl_is_expired", False):
            reasons.append("The domain's SSL certificate has expired.")

        if intelligence.get("ssl_is_self_signed", False):
            reasons.append(
                "The domain uses a self-signed SSL certificate, which is not "
                "trusted by browsers."
            )

    @staticmethod
    def _check_ip_based_url(
        reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs where the hostname is a raw IP address.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        is_ip = bool(features.get("is_ip_based", features.get("is_ip_address", False)))

        if is_ip:
            reasons.append(
                "The URL uses a raw IP address instead of a domain name, "
                "which is uncommon for legitimate sites."
            )

    def _check_url_shortener(
        self, reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs that use a known URL-shortening service.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        if features.get("is_url_shortener", 0):
            reasons.append(
                "The URL uses a known URL shortening service, which "
                "can obscure the true destination."
            )

    def _check_punycode_homograph(
        self, reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag domains containing punycode or homograph characters.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        if features.get("is_punycode", 0):
            reasons.append(
                "The domain uses Punycode (internationalized domain name), "
                "which may be a homograph attack."
            )
            return

        if features.get("has_homograph_chars", 0):
            count = features.get("homograph_char_count", 0)
            reasons.append(
                f"The URL contains {count} Unicode character(s) that visually resemble "
                f"ASCII letters (homograph attack)."
            )

    @staticmethod
    def _check_long_url(
        reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag unusually long URLs (>= 75 characters).

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        url_length: int = int(features.get("url_length", 0))
        if url_length == 0:
            url_length = len(str(features.get("url", "")))

        if url_length >= 75:
            reasons.append(
                f"The URL is unusually long ({url_length} characters), which "
                f"is a common phishing indicator."
            )

    @staticmethod
    def _check_many_subdomains(
        reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs with 3 or more subdomain levels.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        subdomain_count: int = int(features.get("subdomain_count", 0))
        if subdomain_count == 0:
            # Fallback: count dots in hostname
            hostname: str = str(features.get("hostname", features.get("domain", "")))
            subdomain_count = max(0, hostname.count(".") - 1)

        if subdomain_count >= 3:
            reasons.append(
                f"The URL has {subdomain_count} subdomain levels, which may be "
                f"used to disguise the true domain."
            )

    @staticmethod
    def _check_no_https(
        reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs served over plain HTTP.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        is_https = features.get("is_https", 1)

        if not is_https:
            reasons.append(
                "The URL does not use HTTPS, meaning data is transmitted "
                "without encryption."
            )

    @staticmethod
    def _check_high_entropy(
        reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs or domains with high Shannon entropy.

        Entropy above 4.0 on the domain or 4.5 on the full URL suggests
        randomly-generated strings common in phishing infrastructure.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        domain_entropy: float = float(features.get("domain_entropy", 0.0))
        url_entropy: float = float(features.get("url_entropy", 0.0))

        # Compute entropy if not provided but domain string is available
        if domain_entropy == 0.0 and url_entropy == 0.0:
            domain: str = str(features.get("domain", ""))
            if domain:
                domain_entropy = _shannon_entropy(domain)

        if domain_entropy > 4.0 or url_entropy > 4.5:
            reasons.append(
                "The domain or URL has high character entropy, suggesting a "
                "randomly-generated string often used in phishing."
            )

    def _check_suspicious_keywords(
        self, reasons: list[str], features: dict[str, Any]
    ) -> None:
        """Flag URLs containing phishing-associated keywords.

        Args:
            reasons: Accumulating list of reasons.
            features: Extracted URL features.
        """
        has_keywords = features.get("contains_suspicious_keyword", 0)
        keyword_count = features.get("suspicious_keyword_count", 0)

        if has_keywords and keyword_count >= 3:
            reasons.append(
                f"The URL contains {keyword_count} suspicious keywords "
                f"commonly seen in phishing pages."
            )
        elif has_keywords and keyword_count >= 1:
            reasons.append(
                f"The URL contains suspicious keyword(s) associated "
                f"with phishing."
            )

    @staticmethod
    def _check_virustotal_detections(
        reasons: list[str], intelligence: dict[str, Any]
    ) -> None:
        """Flag domains with VirusTotal detections.

        Args:
            reasons: Accumulating list of reasons.
            intelligence: Flat intelligence dictionary.
        """
        if not intelligence.get("virustotal_success", False):
            return

        positives: int = int(intelligence.get("virustotal_positives", 0))
        total: int = int(intelligence.get("virustotal_total_scanners", 0))

        if positives > 0 and total > 0:
            reasons.append(
                f"VirusTotal flagged this domain as malicious by {positives} "
                f"out of {total} security scanners."
            )

    @staticmethod
    def _check_dns_issues(
        reasons: list[str], intelligence: dict[str, Any]
    ) -> None:
        """Flag domains lacking email-authentication DNS records.

        Args:
            reasons: Accumulating list of reasons.
            intelligence: Flat intelligence dictionary.
        """
        if not intelligence.get("dns_success", False):
            return

        missing: list[str] = []

        if not intelligence.get("dns_has_spf", False):
            missing.append("SPF")
        if not intelligence.get("dns_has_dmarc", False):
            missing.append("DMARC")

        if missing:
            records = " and ".join(missing)
            reasons.append(
                f"The domain is missing {records} email-authentication "
                f"record(s), which legitimate organisations typically configure."
            )



    def generate_indicators(
        self,
        features: dict[str, Any],
        intelligence: dict[str, Any],
        prediction: str,
        confidence: float,
        risk_score: Optional[int] = None,
    ) -> dict[str, list[str]]:
        """Generate categorized positive, negative, and neutral trust indicators.

        Args:
            features: Extracted URL features.
            intelligence: Flat threat-intelligence dictionary.
            prediction: Hybrid prediction class ('Legitimate', 'Suspicious', 'Phishing').
            confidence: Decision confidence value (0.0-1.0).
            risk_score: Optional composite score (0-100).

        Returns:
            Dictionary with keys 'positive_indicators', 'negative_indicators',
            'neutral_indicators' mapping to lists of string descriptions.
        """
        positive: list[str] = []
        negative: list[str] = []
        neutral: list[str] = []

        # 1. Brand Impersonation Indicators
        official_match = features.get("official_domain_match", False)
        brand = features.get("brand_detected")
        if official_match:
            positive.append(f"✓ Official registered domain of trusted brand: {brand}")
        elif brand is not None:
            loc = features.get("brand_location", "domain")
            negative.append(f"✗ Impersonates known brand: {brand} (found in {loc})")

        if features.get("is_typosquatting", 0) == 1:
            negative.append("✗ Domain typosquats a trusted brand")

        # 2. SSL/TLS Indicators
        ssl_status = intelligence.get("ssl_ssl_status", "UNKNOWN")
        if ssl_status == "VALID":
            positive.append("✓ Valid SSL certificate")
            if intelligence.get("ssl_has_hsts", False):
                positive.append("✓ HTTPS Strict-Transport-Security (HSTS) active")
        elif ssl_status == "INVALID":
            if intelligence.get("ssl_is_expired", False):
                negative.append("✗ SSL certificate is expired")
            elif intelligence.get("ssl_is_self_signed", False):
                negative.append("✗ SSL certificate is self-signed (untrusted)")
            else:
                negative.append("✗ Missing or invalid SSL certificate")
        else:
            neutral.append("• SSL lookup timeout/failure")

        # HTTP check
        if not features.get("is_https", 1):
            negative.append("✗ Plain HTTP protocol used (unencrypted connections)")

        # 3. Domain Age & Registry Indicators
        age_days = intelligence.get("whois_domain_age_days")
        whois_success = intelligence.get("whois_success", False)
        if whois_success:
            if age_days is not None:
                if age_days >= 365:
                    years = round(age_days / 365.25, 1)
                    positive.append(f"✓ Established domain age ({years} years old)")
                elif age_days < 90:
                    negative.append(f"✗ Recently registered domain (age {age_days} days)")
                else:
                    positive.append(f"✓ Domain registered {age_days} days ago")
            
            registrar = intelligence.get("whois_registrar")
            if registrar:
                positive.append(f"✓ Registered with trusted registrar ({registrar})")
            
            dnssec = intelligence.get("whois_dnssec")
            if dnssec and isinstance(dnssec, str) and "unsigned" not in dnssec.lower():
                positive.append("✓ DNSSEC cryptographic validation active")
        else:
            whois_error = intelligence.get("whois_error") or "Unknown connection error"
            neutral.append(f"• WHOIS lookup unavailable ({whois_error})")

        # 4. DNS Hygiene
        dns_success = intelligence.get("dns_success", False)
        if dns_success:
            if intelligence.get("dns_has_spf", False):
                positive.append("✓ SPF email authentication configured")
            else:
                negative.append("✗ Missing SPF record (facilitates email spoofing)")

            if intelligence.get("dns_has_dmarc", False):
                positive.append("✓ DMARC email authentication configured")
            else:
                negative.append("✗ Missing DMARC record (facilitates email spoofing)")
        else:
            neutral.append("• DNS query check failed or timed out")

        # 5. Domain Trust & ASN Popularity
        asn_org = str(intelligence.get("geoip_asn_org", "")).lower()
        trusted_asns = ["google", "amazon", "microsoft", "cloudflare", "facebook", "fastly", "akamai"]
        if any(t in asn_org for t in trusted_asns):
            positive.append(f"✓ Hosted on a trusted enterprise network ({intelligence.get('geoip_asn_org')})")

        tld = str(features.get("tld", features.get("suffix", ""))).lstrip(".")
        tld_suffix = f" (.{tld})" if tld else ""
        if features.get("is_suspicious_tld", 0) == 1:
            negative.append(f"✗ High-abuse top-level domain{tld_suffix}")

        if features.get("is_url_shortener", 0) == 1:
            negative.append("✗ URL shortener link used (obscures destination)")

        subdomains = features.get("subdomain_count", 0)
        if subdomains >= 3:
            negative.append(f"✗ Excessive subdomain depth ({subdomains} levels)")

        # Entropy / Random strings
        if features.get("url_entropy", 0.0) > 4.5 or features.get("domain_entropy", 0.0) > 4.0:
            negative.append("✗ High character entropy (suspicious random string)")

        if features.get("contains_suspicious_keyword", 0) == 1:
            negative.append("✗ Phishing-associated keyword(s) in URL")

        # 6. Reputation & VirusTotal Detections
        vt_success = intelligence.get("virustotal_success", False)
        if vt_success:
            positives = intelligence.get("virustotal_positives", 0)
            if positives > 0:
                negative.append(f"✗ Malicious reputation: flagged by {positives} VirusTotal scanner(s)")
            else:
                positive.append("✓ Clean reputation (0 detections on VirusTotal)")
        else:
            neutral.append("• VirusTotal lookup skipped (no API key configured)")

        return {
            "positive_indicators": positive,
            "negative_indicators": negative,
            "neutral_indicators": neutral,
        }


# --------------------------------------------------------------------------
# Module-level helpers
# --------------------------------------------------------------------------

def _shannon_entropy(text: str) -> float:
    """Calculate the Shannon entropy of *text*.

    Args:
        text: Input string.

    Returns:
        Entropy value (bits per character).
    """
    if not text:
        return 0.0

    freq: dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1

    length = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)

    return entropy
