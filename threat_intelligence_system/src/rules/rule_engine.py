"""
Deterministic rule-based pre-filter for the Phishing URL Detection Engine.

The ``RuleEngine`` evaluates a parsed URL and its extracted features against
a set of hard-coded, config-driven rules that flag known phishing patterns.
Each rule that fires produces a ``RuleFinding``.  The aggregate
``RuleResult`` summarises whether any rule fired and the combined
signal strength.

Rule checks implemented
-----------------------
1.  is_ip_based           -- Direct IP address instead of domain name.
2.  is_url_shortener      -- Known URL-shortening service hostname.
3.  is_punycode           -- Internationalised domain name (IDN / Punycode).
4.  has_homograph_chars   -- Unicode characters that visually mimic ASCII.
5.  suspicious_tld        -- TLD on the high-abuse list.
6.  brand_in_subdomain    -- Exact brand name embedded in the subdomain.
7.  brand_in_domain       -- Exact brand name embedded in the domain (not the
                             brand's own official domain).
8.  typosquatting         -- Domain edit-distance ≤ 2 from a known brand.
9.  excessive_subdomains  -- More subdomain levels than the threshold.
10. suspicious_keywords   -- ≥ 2 phishing-associated keywords in the URL.
11. long_url              -- URL length exceeds the threshold.
12. no_https              -- Plain HTTP when the domain is non-local.
13. double_slash_in_path  -- ``//`` inside the URL path (redirect trick).
14. at_symbol_in_url      -- ``@`` character before the host (credential
                             stuffing camouflage).
15. data_or_js_uri        -- ``data:`` or ``javascript:`` pseudo-scheme.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.settings import get_settings
from src.parser.url_parser import ParsedURL
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RuleFinding:
    """A single rule that fired during evaluation.

    Attributes:
        rule_id: Short snake_case identifier for the rule.
        description: Human-readable explanation.
        severity: ``'critical'``, ``'high'``, ``'medium'``, or ``'low'``.
        score_contribution: Additive contribution to the overall rule score
            (0.0 – 1.0).
    """

    rule_id: str
    description: str
    severity: str  # 'critical' | 'high' | 'medium' | 'low'
    score_contribution: float

    def to_dict(self) -> dict[str, Any]:
        """Serialise the finding to a plain dictionary."""
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "severity": self.severity,
            "score_contribution": self.score_contribution,
        }


@dataclass
class RuleResult:
    """Aggregate result of running the rule engine against a URL.

    Attributes:
        url: The URL that was evaluated.
        findings: List of rules that fired.
        rule_score: Normalised rule-based risk score (0.0 – 1.0).
        is_definite_phishing: ``True`` when one or more *critical* rules fire.
        is_suspicious: ``True`` when one or more rules of any severity fire.
    """

    url: str
    findings: list[RuleFinding] = field(default_factory=list)
    rule_score: float = 0.0
    is_definite_phishing: bool = False
    is_suspicious: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "url": self.url,
            "findings": [f.to_dict() for f in self.findings],
            "rule_score": round(self.rule_score, 4),
            "is_definite_phishing": self.is_definite_phishing,
            "is_suspicious": self.is_suspicious,
            "finding_count": len(self.findings),
        }


# ---------------------------------------------------------------------------
# Severity weights used to aggregate the rule score
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
}


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

class RuleEngine:
    """Deterministic, config-driven rule engine for phishing URL detection.

    Each rule is a private method that receives a ``ParsedURL`` instance and
    the extracted feature dictionary.  Rules append ``RuleFinding`` objects to
    an accumulating list; the aggregate score and flags are then derived from
    that list.

    All thresholds are loaded from application settings so they can be
    adjusted via environment variables or a ``.env`` file without code
    changes.

    Usage::

        engine = RuleEngine()
        result = engine.evaluate(parsed_url, features)
        print(result.is_definite_phishing)  # True / False
        print([f.rule_id for f in result.findings])
    """

    # Maximum number of subdomain parts before "excessive_subdomains" fires.
    _DEFAULT_MAX_SUBDOMAINS: int = 3

    # URL length above which "long_url" fires.
    _DEFAULT_MAX_URL_LENGTH: int = 75

    # Minimum number of suspicious keywords before the keyword rule fires.
    _MIN_SUSPICIOUS_KEYWORDS: int = 2

    def __init__(self, brand_engine: Any | None = None) -> None:
        """Initialise the rule engine and cache reference data from settings.

        Args:
            brand_engine: Optional injected ``BrandIntelligenceEngine``.
                When *None* a default instance is created lazily on first
                use; when construction fails the brand-intelligence rules
                degrade gracefully to no-ops.
        """
        settings = get_settings()
        self._brand_engine: Any | None = brand_engine
        self._brand_engine_failed: bool = False
        self._known_brands: list[str] = [
            b.lower() for b in settings.threat.known_brands
        ]
        self._suspicious_tlds: list[str] = list(settings.threat.suspicious_tlds)
        self._url_shorteners: list[str] = list(settings.threat.url_shorteners)
        self._suspicious_keywords: list[str] = [
            kw.lower() for kw in settings.threat.suspicious_keywords
        ]
        logger.debug(
            "RuleEngine initialised: %d brands, %d suspicious TLDs, "
            "%d URL shorteners, %d keywords",
            len(self._known_brands),
            len(self._suspicious_tlds),
            len(self._url_shorteners),
            len(self._suspicious_keywords),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> RuleResult:
        """Evaluate a parsed URL against all rules.

        Args:
            parsed_url: Pre-parsed ``ParsedURL`` object.
            features: Flat feature dictionary from ``FeaturePipeline.extract``.

        Returns:
            ``RuleResult`` containing all fired findings and aggregate scores.
        """
        findings: list[RuleFinding] = []

        # Execute all rule checks
        self._rule_ip_based(findings, parsed_url, features)
        self._rule_url_shortener(findings, parsed_url, features)
        self._rule_punycode(findings, features)
        self._rule_homograph(findings, features)
        self._rule_suspicious_tld(findings, features)
        self._rule_brand_in_subdomain(findings, parsed_url, features)
        self._rule_brand_in_domain(findings, parsed_url, features)
        self._rule_typosquatting(findings, features)
        self._rule_excessive_subdomains(findings, parsed_url, features)
        self._rule_suspicious_keywords(findings, parsed_url, features)
        self._rule_long_url(findings, parsed_url, features)
        self._rule_no_https(findings, parsed_url, features)
        self._rule_double_slash_in_path(findings, parsed_url, features)
        self._rule_at_symbol(findings, parsed_url, features)
        self._rule_data_or_js_uri(findings, parsed_url, features)
        self._rule_brand_intelligence(findings, parsed_url, features)

        # Derive aggregate score (capped at 1.0)
        raw_score: float = sum(f.score_contribution for f in findings)
        rule_score: float = min(1.0, raw_score)

        is_definite = any(f.severity == "critical" for f in findings)
        is_suspicious = len(findings) > 0

        result = RuleResult(
            url=parsed_url.raw_url,
            findings=findings,
            rule_score=round(rule_score, 4),
            is_definite_phishing=is_definite,
            is_suspicious=is_suspicious,
        )

        logger.debug(
            "RuleEngine: url=%s findings=%d score=%.3f definite=%s",
            parsed_url.raw_url[:60],
            len(findings),
            rule_score,
            is_definite,
        )

        return result

    # ------------------------------------------------------------------
    # Individual rule implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_ip_based(
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: URL uses a raw IP address as the hostname."""
        is_ip = bool(
            features.get("is_ip_based", False)
            or features.get("is_ip_address", False)
            or parsed_url.is_ip_based
        )
        if is_ip:
            findings.append(
                RuleFinding(
                    rule_id="is_ip_based",
                    description=(
                        "The URL uses a raw IP address instead of a domain name. "
                        "Legitimate services rarely expose direct IP URLs."
                    ),
                    severity="high",
                    score_contribution=0.75,
                )
            )

    def _rule_url_shortener(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: URL uses a known URL-shortening service."""
        is_short = bool(features.get("is_url_shortener", False))
        if not is_short:
            # Also check the raw hostname directly
            hostname = (parsed_url.hostname or "").lower()
            is_short = any(s in hostname for s in self._url_shorteners)
        if is_short:
            findings.append(
                RuleFinding(
                    rule_id="is_url_shortener",
                    description=(
                        "The URL routes through a URL-shortening service, "
                        "which is commonly used to obscure phishing destinations."
                    ),
                    severity="medium",
                    score_contribution=0.50,
                )
            )

    @staticmethod
    def _rule_punycode(
        findings: list[RuleFinding],
        features: dict[str, Any],
    ) -> None:
        """Rule: Domain contains Punycode (IDN homograph potential)."""
        if features.get("is_punycode", False):
            findings.append(
                RuleFinding(
                    rule_id="is_punycode",
                    description=(
                        "The domain is Punycode-encoded (internationalized domain "
                        "name). Attackers use look-alike Unicode characters to "
                        "impersonate legitimate domains."
                    ),
                    severity="high",
                    score_contribution=0.70,
                )
            )

    @staticmethod
    def _rule_homograph(
        findings: list[RuleFinding],
        features: dict[str, Any],
    ) -> None:
        """Rule: Domain contains Unicode homograph characters."""
        if features.get("has_homograph_chars", False):
            count = int(features.get("homograph_char_count", 1))
            findings.append(
                RuleFinding(
                    rule_id="has_homograph_chars",
                    description=(
                        f"The URL contains {count} Unicode character(s) that visually "
                        f"resemble ASCII letters — a classic IDN homograph attack."
                    ),
                    severity="critical",
                    score_contribution=1.0,
                )
            )

    def _rule_suspicious_tld(
        self,
        findings: list[RuleFinding],
        features: dict[str, Any],
    ) -> None:
        """Rule: TLD is on the high-abuse list."""
        is_suspicious = bool(features.get("is_suspicious_tld", False))
        tld_risk = float(features.get("tld_risk_score", 0.0))
        if is_suspicious or tld_risk >= 0.7:
            tld = str(features.get("tld", features.get("suffix", ""))).lstrip(".")
            findings.append(
                RuleFinding(
                    rule_id="suspicious_tld",
                    description=(
                        f"The top-level domain '.{tld}' has a high abuse rate "
                        f"and is frequently used in phishing and spam campaigns."
                    ),
                    severity="high",
                    score_contribution=0.65,
                )
            )

    def _rule_brand_in_subdomain(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: Known brand name found in the subdomain."""
        if features.get("brand_in_subdomain", False):
            subdomain = parsed_url.subdomain.lower()
            matched = [b for b in self._known_brands if b in subdomain]
            brand = matched[0] if matched else "a known brand"
            findings.append(
                RuleFinding(
                    rule_id="brand_in_subdomain",
                    description=(
                        f"The subdomain contains '{brand}', a well-known brand name. "
                        f"Attackers exploit subdomains to make phishing URLs look "
                        f"legitimate (e.g., paypal.malicious.xyz)."
                    ),
                    severity="high",
                    score_contribution=0.80,
                )
            )

    def _rule_brand_in_domain(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: Known brand name found in the domain (but not the official domain)."""
        if features.get("brand_in_domain", False):
            domain_lower = (parsed_url.domain or parsed_url.hostname or "").lower()
            matched = [
                b for b in self._known_brands
                if b in domain_lower
                and domain_lower not in (
                    f"{b}.com", f"{b}.net", f"{b}.org",
                    f"www.{b}.com", f"www.{b}.net",
                )
            ]
            brand = matched[0] if matched else "a known brand"
            if brand:
                findings.append(
                    RuleFinding(
                        rule_id="brand_in_domain",
                        description=(
                            f"The domain contains '{brand}' but is not the "
                            f"official {brand}.com domain — a common brand "
                            f"impersonation technique."
                        ),
                        severity="high",
                        score_contribution=0.70,
                    )
                )

    @staticmethod
    def _rule_typosquatting(
        findings: list[RuleFinding],
        features: dict[str, Any],
    ) -> None:
        """Rule: Domain is very close (edit distance ≤ 2) to a known brand."""
        if features.get("is_typosquatting", False):
            dist = int(features.get("brand_levenshtein_distance", "?"))
            closest = features.get("closest_brand", "a known brand")
            findings.append(
                RuleFinding(
                    rule_id="typosquatting",
                    description=(
                        f"The domain closely resembles '{closest}' "
                        f"(Levenshtein distance: {dist}). "
                        f"This is a hallmark of typosquatting attacks."
                    ),
                    severity="critical",
                    score_contribution=0.95,
                )
            )

    def _rule_excessive_subdomains(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: URL has an excessive number of subdomain levels."""
        count = int(features.get("subdomain_count", parsed_url.subdomain_count))
        if count >= self._DEFAULT_MAX_SUBDOMAINS:
            findings.append(
                RuleFinding(
                    rule_id="excessive_subdomains",
                    description=(
                        f"The URL has {count} subdomain levels, which can be used "
                        f"to disguise the true registered domain from casual inspection."
                    ),
                    severity="medium",
                    score_contribution=0.45,
                )
            )

    def _rule_suspicious_keywords(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: URL contains multiple phishing-associated keywords."""
        kw_count = int(features.get("suspicious_keyword_count", 0))
        if kw_count == 0:
            # Count manually from the URL string
            url_lower = parsed_url.raw_url.lower()
            kw_count = sum(1 for kw in self._suspicious_keywords if kw in url_lower)

        if kw_count >= self._MIN_SUSPICIOUS_KEYWORDS:
            findings.append(
                RuleFinding(
                    rule_id="suspicious_keywords",
                    description=(
                        f"The URL contains {kw_count} keyword(s) associated with "
                        f"phishing pages (e.g., 'login', 'verify', 'secure', 'account')."
                    ),
                    severity="medium" if kw_count < 4 else "high",
                    score_contribution=min(0.55, 0.15 * kw_count),
                )
            )
        elif kw_count == 1 and features.get("contains_suspicious_keyword", False):
            findings.append(
                RuleFinding(
                    rule_id="suspicious_keyword_single",
                    description=(
                        "The URL contains a keyword commonly associated with "
                        "phishing or credential-harvesting pages."
                    ),
                    severity="low",
                    score_contribution=0.20,
                )
            )

    def _rule_long_url(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: URL exceeds the length threshold."""
        url_len = int(features.get("url_length", len(parsed_url.raw_url)))
        if url_len >= self._DEFAULT_MAX_URL_LENGTH:
            findings.append(
                RuleFinding(
                    rule_id="long_url",
                    description=(
                        f"The URL is {url_len} characters long, significantly above "
                        f"the typical length for legitimate URLs."
                    ),
                    severity="low",
                    score_contribution=0.25,
                )
            )

    @staticmethod
    def _rule_no_https(
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: URL uses plain HTTP instead of HTTPS."""
        is_https = bool(features.get("is_https", parsed_url.scheme == "https"))
        # Don't penalise local/private networks
        hostname = (parsed_url.hostname or "").lower()
        is_local = hostname in ("localhost", "127.0.0.1", "") or hostname.startswith(
            "192.168."
        )
        if not is_https and not is_local:
            findings.append(
                RuleFinding(
                    rule_id="no_https",
                    description=(
                        "The URL uses HTTP instead of HTTPS. Data transmitted "
                        "to or from this URL is not encrypted."
                    ),
                    severity="low",
                    score_contribution=0.20,
                )
            )

    @staticmethod
    def _rule_double_slash_in_path(
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: ``//`` found inside the URL path (open redirect trick)."""
        has_double = bool(
            features.get("has_double_slash_in_path", False)
            or parsed_url.has_double_slash_in_path
        )
        if has_double:
            findings.append(
                RuleFinding(
                    rule_id="double_slash_in_path",
                    description=(
                        "The URL path contains '//' which can be used to "
                        "disguise an open redirect or confuse URL parsers."
                    ),
                    severity="medium",
                    score_contribution=0.40,
                )
            )

    @staticmethod
    def _rule_at_symbol(
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: ``@`` symbol in the URL (credential camouflage)."""
        has_at = bool(
            features.get("has_at_symbol", False) or parsed_url.has_at_symbol
        )
        if has_at:
            findings.append(
                RuleFinding(
                    rule_id="at_symbol_in_url",
                    description=(
                        "The URL contains an '@' symbol before the host portion. "
                        "Browsers ignore everything before '@', which attackers use "
                        "to display a trusted-looking URL while redirecting elsewhere."
                    ),
                    severity="critical",
                    score_contribution=0.90,
                )
            )

    @staticmethod
    def _rule_data_or_js_uri(
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rule: ``data:`` or ``javascript:`` pseudo-scheme detected."""
        has_data = bool(features.get("has_data_uri", False))
        has_js = bool(features.get("has_javascript_uri", False))
        scheme = parsed_url.scheme.lower()
        if has_data or has_js or scheme in ("data", "javascript"):
            findings.append(
                RuleFinding(
                    rule_id="data_or_js_uri",
                    description=(
                        "The URL uses a 'data:' or 'javascript:' pseudo-scheme. "
                        "These schemes are almost exclusively used in malicious "
                        "content injection and phishing."
                    ),
                    severity="critical",
                    score_contribution=1.0,
                )
            )

    # ------------------------------------------------------------------
    # Brand Intelligence rules (additive - Phase 5)
    # ------------------------------------------------------------------

    def _get_brand_engine(self) -> Any | None:
        """Lazily create the injected/default BrandIntelligenceEngine."""
        if self._brand_engine is None and not self._brand_engine_failed:
            try:
                from src.intelligence.brand_intelligence import (
                    BrandIntelligenceEngine,
                )
                self._brand_engine = BrandIntelligenceEngine()
            except Exception as exc:  # noqa: BLE001 -- rules must degrade
                logger.warning(
                    "BrandIntelligenceEngine unavailable - brand rules "
                    "disabled: %s", exc,
                )
                self._brand_engine_failed = True
        return self._brand_engine

    def _rule_brand_intelligence(
        self,
        findings: list[RuleFinding],
        parsed_url: ParsedURL,
        features: dict[str, Any],
    ) -> None:
        """Rules: brand impersonation findings from the Brand Intelligence
        Engine (official-domain mismatch, typosquatting, Unicode spoofing,
        fake login infrastructure and cloud-hosted impersonation).

        Official domains produce no findings; cloud providers are never
        flagged on their own. All findings are additive and explainable.
        """
        engine = self._get_brand_engine()
        if engine is None:
            return
        try:
            analysis = engine.analyze(parsed_url)
        except Exception as exc:  # noqa: BLE001 -- rules must never break
            logger.warning("Brand intelligence analysis failed: %s", exc)
            return
        # Skip only when the domain is official AND clean. Official domains
        # may still raise Brand Conflict findings (a trusted domain that
        # references a DIFFERENT protected brand), which must be reported.
        if not analysis.findings:
            return

        emitted: set[str] = set()
        for bf in analysis.findings:
            rule_id, severity, contribution = {
                "official_domain_mismatch": (
                    "bi_official_domain_mismatch", "high", 0.60),
                "typosquatting": (
                    "bi_typosquatting", bf.severity, 0.85),
                "homoglyph": (
                    "bi_unicode_spoofing", "critical", 0.90),
                "misleading_affix": (
                    "bi_brand_impersonation", "high", 0.45),
                "cloud_hosted_impersonation": (
                    "bi_cloud_hosted_impersonation", "high", 0.50),
                "brand_conflict": (
                    "bi_brand_conflict", "high", 0.45),
            }.get(bf.finding_type, (None, None, 0.0))
            if rule_id is None or rule_id in emitted:
                continue
            emitted.add(rule_id)
            findings.append(RuleFinding(
                rule_id=rule_id,
                description=bf.detail,
                severity=severity,
                score_contribution=contribution,
            ))

        # Fake login infrastructure: brand mismatch + credential signals in
        # the URL itself (independent of cloud hosting).
        has_mismatch = any(
            f.finding_type in (
                "official_domain_mismatch", "typosquatting", "homoglyph")
            for f in analysis.findings
        )
        text = f"{parsed_url.subdomain} {parsed_url.path} {parsed_url.query}".lower()
        login_signals = [
            kw for kw in ("login", "signin", "sign-in", "log-in", "password",
                          "verify", "auth", "credential", "webscr", "otp")
            if kw in text
        ]
        if (has_mismatch and login_signals
                and "bi_fake_login_infrastructure" not in emitted):
            brand_name = (
                engine.display_name(analysis.brands_detected[0])
                if analysis.brands_detected else "a protected brand"
            )
            findings.append(RuleFinding(
                rule_id="bi_fake_login_infrastructure",
                description=(
                    f"URL imitates {brand_name} and contains "
                    f"credential-collection signals "
                    f"({', '.join(login_signals[:3])}) - consistent with a "
                    f"fake login page."
                ),
                severity="high",
                score_contribution=0.55,
            ))
