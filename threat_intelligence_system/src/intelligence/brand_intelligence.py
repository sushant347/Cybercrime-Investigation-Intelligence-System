"""
Brand Intelligence Engine for the Phishing URL Detection Engine.

Detects phishing websites impersonating legitimate organisations by
combining several offline, explainable analyses around a maintainable
brand database (``config/brand_intelligence.yaml``):

* **Registrable-domain comparison** - hostnames are reduced to their
  registrable domain via the Public Suffix List (``tldextract`` through the
  existing ``URLParser``), never compared raw.  ``login.microsoft.com``
  therefore maps to ``microsoft.com`` while ``secure-login-paypal.com`` and
  ``edge-origin-whatsapp.com.cn`` remain themselves.
* **Brand token detection** in hostname, subdomains, path and query.
* **Official-domain verification** - a mentioned brand is only trusted when
  the registrable domain is in the brand's official-domain list.
* **Typosquatting detection** - Damerau-Levenshtein distance, leetspeak
  normalisation (``paypa1``, ``micros0ft``), keyboard-adjacent substitutions,
  repeated / missing / extra characters (``arnazon``, ``whatsaap``).
* **Homoglyph detection** - Unicode NFKC normalisation plus a confusables
  map (Cyrillic/Greek look-alikes such as ``раypal``/``gοοgle``).
* **Prefix / suffix detection** - misleading affix combinations such as
  ``secure-google`` or ``verify-paypal``.
* **Cloud-hosting context** - reuses the existing ``CloudHostingDetector``
  (dependency injection); cloud providers are never malicious by themselves,
  suspicion rises only for brand mismatch combined with credential signals.
* **Brand Risk Score** - a configurable weighted combination of every
  signal, plus optional external context (domain age, SSL, WHOIS,
  suspicious keywords), with human-readable reasons.

The engine is pure/offline (no network), never raises from ``analyze`` and
integrates additively: the existing predictor, ML models, checkpoints and
JSON outputs are untouched.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from src.config.settings import get_settings
from src.parser.url_parser import ParsedURL, URLParser
from src.reputation.cloud_hosting import CloudHostingDetector
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Default configuration file (relative to the project config directory).
DEFAULT_CONFIG_FILENAME = "brand_intelligence.yaml"

#: Leetspeak / visual ASCII substitutions used by typosquatters.
_LEET_MAP: dict[str, str] = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t",
    "8": "b", "9": "g", "@": "a", "$": "s", "!": "i",
}

#: Multi-character visual confusions (checked before single-char mapping).
_MULTI_CONFUSIONS: tuple[tuple[str, str], ...] = (
    ("rn", "m"), ("vv", "w"), ("cl", "d"), ("nn", "m"),
)

#: QWERTY adjacency map for keyboard-slip substitutions.
_KEYBOARD_ADJACENT: dict[str, str] = {
    "q": "wa", "w": "qes", "e": "wrd", "r": "etf", "t": "ryg", "y": "tuh",
    "u": "yij", "i": "uok", "o": "ipl", "p": "ol", "a": "qsz", "s": "adwx",
    "d": "sfec", "f": "dgr", "g": "fht", "h": "gjy", "j": "hku", "k": "jli",
    "l": "kop", "z": "asx", "x": "zsc", "c": "xdv", "v": "cfb", "b": "vgn",
    "n": "bhm", "m": "nj",
}

#: Unicode confusables mapped to their ASCII equivalent (extends the
#: homograph map from application settings).
_EXTRA_CONFUSABLES: dict[str, str] = {
    # Greek
    "ο": "o",  # omicron
    "α": "a",  # alpha
    "ε": "e",  # epsilon
    "ι": "i",  # iota
    "κ": "k",  # kappa
    "ν": "v",  # nu
    "ρ": "p",  # rho
    "τ": "t",  # tau
    "υ": "u",  # upsilon
    "χ": "x",  # chi
    # Cyrillic (supplement to settings.homograph_map)
    "а": "a", "е": "e", "о": "o", "р": "p",
    "с": "c", "у": "y", "х": "x", "і": "i",
    "ґ": "r", "ӏ": "l", "м": "m", "н": "h",
    "т": "t", "в": "b", "к": "k",
}


@dataclass
class BrandFinding:
    """One explainable brand-intelligence finding.

    Attributes:
        finding_type: Machine-readable finding identifier.
        brand: Brand key from the database.
        brand_name: Human-readable brand name.
        detail: Human-readable explanation.
        severity: ``info`` / ``medium`` / ``high`` / ``critical``.
        score: Contribution to the brand risk score (0..1, pre-cap).
    """

    finding_type: str
    brand: str
    brand_name: str
    detail: str
    severity: str = "medium"
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


@dataclass
class BrandIntelligenceResult:
    """Aggregated brand-impersonation assessment for one URL.

    Attributes:
        url: The analysed URL.
        registrable_domain: PSL registrable domain of the hostname.
        is_official_domain: Registrable domain belongs to a protected brand.
        official_brand: Brand key when ``is_official_domain`` is True.
        brands_detected: Brand keys referenced anywhere in the URL.
        brand_locations: Mapping of brand key to URL parts it appeared in.
        findings: Explainable findings (mismatches, typosquats, ...).
        risk_score: Weighted brand risk score in [0, 1].
        risk_level: ``none`` / ``low`` / ``medium`` / ``high``.
        reasons: Human-readable reason strings.
    """

    url: str = ""
    registrable_domain: str = ""
    is_official_domain: bool = False
    official_brand: Optional[str] = None
    brands_detected: list[str] = field(default_factory=list)
    brand_locations: dict[str, list[str]] = field(default_factory=dict)
    findings: list[BrandFinding] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "none"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        payload = asdict(self)
        payload["findings"] = [f.to_dict() for f in self.findings]
        return payload

    def has_finding(self, finding_type: str) -> bool:
        """True when a finding of *finding_type* is present."""
        return any(f.finding_type == finding_type for f in self.findings)


class BrandIntelligenceEngine:
    """Configurable, explainable brand-impersonation detector.

    Args:
        config_path: Override for the brand database YAML.  Defaults to
            ``<project>/config/brand_intelligence.yaml``.
        cloud_detector: Injected ``CloudHostingDetector`` (a default
            instance is created when omitted).
        url_parser: Injected ``URLParser`` used when ``analyze`` receives a
            raw URL string.
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        cloud_detector: Optional[CloudHostingDetector] = None,
        url_parser: Optional[URLParser] = None,
    ) -> None:
        self._settings = get_settings()
        self._config = self._load_config(config_path)
        self._cloud = cloud_detector or CloudHostingDetector()
        self._parser = url_parser or URLParser()

        brands: dict[str, Any] = self._config.get("brands", {})
        self._brands: dict[str, dict[str, Any]] = {}
        self._official_index: dict[str, str] = {}
        for key, entry in brands.items():
            tokens = [str(t).lower() for t in entry.get("tokens", []) or [key]]
            domains = [str(d).lower() for d in entry.get("official_domains", [])]
            self._brands[key] = {
                "display_name": str(entry.get("display_name", key.title())),
                "tokens": tokens,
                "official_domains": set(domains),
            }
            for domain in domains:
                self._official_index[domain] = key

        self._official_suffixes: dict[str, str] = {
            str(k).lower(): str(v)
            for k, v in (self._config.get("official_suffixes") or {}).items()
        }
        self._risky_affixes: tuple[str, ...] = tuple(
            str(a).lower() for a in self._config.get("risky_affixes", [])
        )
        self._credential_signals: tuple[str, ...] = tuple(
            str(s).lower() for s in self._config.get("credential_signals", [])
        )
        scoring = self._config.get("scoring", {})
        self._weights: dict[str, float] = {
            k: float(v) for k, v in (scoring.get("weights") or {}).items()
        }
        thresholds = scoring.get("thresholds") or {}
        self._high_threshold = float(thresholds.get("high", 0.60))
        self._medium_threshold = float(thresholds.get("medium", 0.30))
        self._young_domain_days = int(scoring.get("young_domain_max_age_days", 180))

        typo_cfg = self._config.get("typosquatting") or {}
        self._typo_max_distance = int(typo_cfg.get("max_edit_distance", 2))
        self._typo_min_length = int(typo_cfg.get("min_brand_length", 5))

        # Confusables: settings homograph map + engine extensions.
        self._confusables: dict[str, str] = dict(_EXTRA_CONFUSABLES)
        self._confusables.update(self._settings.threat.homograph_map or {})

        logger.info(
            "BrandIntelligenceEngine initialised - %d brands, %d official "
            "domains, %d affixes",
            len(self._brands), len(self._official_index), len(self._risky_affixes),
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self, config_path: Path | str | None) -> dict[str, Any]:
        """Load the brand database YAML with graceful fallback."""
        path = Path(
            config_path
            if config_path is not None
            else self._settings.paths.project_root / "config" / DEFAULT_CONFIG_FILENAME
        )
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    config = yaml.safe_load(fh) or {}
                if isinstance(config, dict) and config.get("brands"):
                    return config
                logger.warning("Brand config %s is empty or malformed", path)
            except Exception as exc:  # noqa: BLE001 -- fall back below
                logger.error("Failed to load brand config %s: %s", path, exc)
        # Fallback: build a minimal database from the legacy settings registry
        logger.warning(
            "Falling back to settings.threat.official_domains for brand data"
        )
        return {
            "brands": {
                brand: {"tokens": [brand], "official_domains": domains}
                for brand, domains in self._settings.threat.official_domains.items()
            }
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def brand_count(self) -> int:
        """Number of protected brands in the database."""
        return len(self._brands)

    def display_name(self, brand: str) -> str:
        """Human-readable name of *brand* (falls back to the key)."""
        return self._brands.get(brand, {}).get("display_name", brand.title())

    def is_official_domain(self, registrable_domain: str) -> Optional[str]:
        """Return the owning brand key when *registrable_domain* is official."""
        domain = (registrable_domain or "").lower().strip(".")
        if domain in self._official_index:
            return self._official_index[domain]
        for suffix, brand in self._official_suffixes.items():
            if domain == suffix or domain.endswith("." + suffix):
                return brand
        return None

    def analyze(
        self,
        url: str | ParsedURL,
        context: Optional[Mapping[str, Any]] = None,
    ) -> BrandIntelligenceResult:
        """Run the full brand-impersonation analysis for one URL.

        Args:
            url: Raw URL string or a pre-parsed ``ParsedURL``.
            context: Optional external signals used by the risk score:
                ``domain_age_days`` (int), ``ssl_valid`` (bool),
                ``whois_private`` (bool), ``suspicious_keyword_count`` (int).

        Returns:
            ``BrandIntelligenceResult`` (never raises; returns an empty
            result on unexpected internal errors).
        """
        try:
            return self._analyze(url, context or {})
        except Exception as exc:  # noqa: BLE001 -- engine must never break callers
            raw = url.raw_url if isinstance(url, ParsedURL) else str(url)
            logger.error("Brand intelligence failed for %s: %s", raw[:80], exc)
            return BrandIntelligenceResult(url=raw)

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    def _analyze(
        self, url: str | ParsedURL, context: Mapping[str, Any]
    ) -> BrandIntelligenceResult:
        parsed = url if isinstance(url, ParsedURL) else self._parser.parse(str(url))
        result = BrandIntelligenceResult(
            url=parsed.raw_url,
            registrable_domain=(parsed.registered_domain or "").lower(),
        )

        # 1. Official-domain verification (registrable domain, never hostname)
        official_brand = self.is_official_domain(result.registrable_domain)
        if official_brand is not None:
            result.is_official_domain = True
            result.official_brand = official_brand
            result.brands_detected = [official_brand]
            owner_label = f"the official {self.display_name(official_brand)} infrastructure"

            # Brand Conflict Detection: a trusted domain that references a
            # DIFFERENT protected brand is suspicious even though the domain
            # itself is official (e.g. github.io/microsoft-login).
            conflicts = self._detect_brand_conflict(
                parsed, result, official_brand, self.display_name(official_brand)
            )
            if not conflicts:
                result.risk_level = "none"
                result.reasons.append(
                    f"Registrable domain '{result.registrable_domain}' belongs "
                    f"to {owner_label}."
                )
                return result

            self._score_conflict(result, context, owner_label)
            return result

        # 1b. Cloud-owned domains that are not protected brands are still
        # trusted infrastructure; a protected brand referenced on them is a
        # Brand Conflict (e.g. firebaseapp.com/google-login).
        cloud = self._cloud.analyze(parsed.raw_url)
        if cloud.is_cloud_hosted and self.is_official_domain(
            result.registrable_domain
        ) is None:
            conflicts = self._detect_brand_conflict(
                parsed, result, None, cloud.provider
            )
            if conflicts:
                self._detect_typosquatting(parsed, result)
                self._detect_homoglyphs(parsed, result)
                self._assess_cloud_hosting(parsed, result)
                self._score_conflict(
                    result, context, cloud.provider
                )
                return result

        # 2. Brand token detection across URL parts
        self._detect_brand_tokens(parsed, result)

        # 3. Typosquatting against domain labels
        self._detect_typosquatting(parsed, result)

        # 4. Homoglyph / Unicode look-alike detection
        self._detect_homoglyphs(parsed, result)

        # 5. Official-domain mismatch for every referenced brand
        self._verify_official_domains(result)

        # 6. Misleading prefix / suffix combinations
        self._detect_prefix_suffix(parsed, result)

        # 7. Cloud-hosting impersonation context
        self._assess_cloud_hosting(parsed, result)

        # 8. Weighted brand risk score + reasons
        self._score(result, context)
        return result

    # ------------------------------------------------------------------
    # Detection stages
    # ------------------------------------------------------------------

    def _scan_brand_tokens(self, parsed: ParsedURL) -> dict[str, list[str]]:
        """Return ``{brand: [locations]}`` for every protected brand token
        found in the hostname, subdomain, path or query (pure, no mutation)."""
        surfaces = {
            "hostname": (parsed.hostname or "").lower(),
            "subdomain": (parsed.subdomain or "").lower(),
            "path": (parsed.path or "").lower(),
            "query": (parsed.query or "").lower(),
        }
        detected: dict[str, list[str]] = {}
        for brand, entry in self._brands.items():
            locations: list[str] = []
            for token in entry["tokens"]:
                if len(token) < 4:
                    continue  # short aliases would be false-positive prone
                for surface, text in surfaces.items():
                    if token in text and surface not in locations:
                        locations.append(surface)
            if locations:
                detected[brand] = locations
        return detected

    def _detect_brand_tokens(
        self, parsed: ParsedURL, result: BrandIntelligenceResult
    ) -> None:
        """Find brand tokens in hostname, subdomains, path and query."""
        for brand, locations in self._scan_brand_tokens(parsed).items():
            result.brands_detected.append(brand)
            result.brand_locations[brand] = locations

    def _risk_level_for(self, score: float) -> str:
        """Map a bounded risk score to a discrete risk level."""
        if score >= self._high_threshold:
            return "high"
        if score >= self._medium_threshold:
            return "medium"
        return "low" if score > 0 else "none"

    def _detect_brand_conflict(
        self,
        parsed: ParsedURL,
        result: BrandIntelligenceResult,
        owner_brand: Optional[str],
        owner_label: str,
    ) -> list[str]:
        """Detect a *different* protected brand referenced by a trusted domain.

        A Brand Conflict occurs when the registrable domain belongs to one
        trusted organisation (an official brand domain or a recognised cloud
        provider) yet the hostname, subdomain, path or query references a
        DIFFERENT protected brand. Example: ``github.io/microsoft-login`` -
        the domain owner is GitHub but the URL references Microsoft.

        False-positive protection: a token belonging to the domain owner
        itself (``github`` on github.io, ``whatsapp`` on whatsapp.com,
        aliases such as ``outlook`` on a Microsoft domain) is never a
        conflict.

        Args:
            parsed: The parsed URL.
            result: Result accumulator to append findings to.
            owner_brand: Brand key owning the registrable domain, or *None*
                when the owner is a cloud provider that is not a protected
                brand.
            owner_label: Human-readable owner name (brand or cloud provider).

        Returns:
            The list of conflicting brand keys detected.
        """
        owner_tokens = set(self._brands.get(owner_brand, {}).get("tokens", [])) \
            if owner_brand else set()
        conflicts: list[str] = []
        for brand, locations in self._scan_brand_tokens(parsed).items():
            if brand == owner_brand:
                continue  # same organisation - not a conflict
            # Guard against alias overlap (e.g. two keys sharing a token).
            if owner_tokens and set(self._brands[brand]["tokens"]) & owner_tokens:
                continue
            conflicts.append(brand)
            if brand not in result.brands_detected:
                result.brands_detected.append(brand)
                result.brand_locations[brand] = locations
            in_domain = any(loc in ("hostname", "subdomain") for loc in locations)
            severity = "high" if in_domain else "medium"
            # A brand impersonated at the DOMAIN level (hostname/subdomain) is
            # more deceptive than one merely mentioned in a path/query, so it
            # carries additional weight.
            conflict_score = self._weights.get("brand_conflict", 0.35)
            if in_domain:
                conflict_score += self._weights.get("brand_token", 0.10)
            brand_name = self.display_name(brand)
            result.findings.append(BrandFinding(
                finding_type="brand_conflict",
                brand=brand,
                brand_name=brand_name,
                detail=(
                    f"Protected brand '{brand_name}' detected inside the URL "
                    f"({'/'.join(locations)}), but the registrable domain "
                    f"'{result.registrable_domain}' belongs to {owner_label}. "
                    f"The URL references a different trusted organisation than "
                    f"the domain owner - possible brand impersonation or "
                    f"deceptive content."
                ),
                severity=severity,
                score=conflict_score,
            ))
        return conflicts

    def _detect_typosquatting(
        self, parsed: ParsedURL, result: BrandIntelligenceResult
    ) -> None:
        """Detect domain labels within edit distance of a protected brand."""
        import jellyfish

        labels = self._candidate_labels(parsed)
        for label in labels:
            normalised = self._normalise_leet(label)
            collapsed = re.sub(r"(.)\1+", r"\1", normalised)  # repeated chars
            for brand, entry in self._brands.items():
                tokens = entry["tokens"]
                # Exact match of the RAW label to any brand token is a
                # genuine brand reference (handled by token detection), not a
                # typosquat. A leetspeak-normalised match still counts.
                if label in tokens:
                    continue
                for token in tokens:
                    if len(token) < self._typo_min_length:
                        continue
                    if label == token:
                        continue  # exact token handled by token detection
                    # Distance from the raw label, and from its transformed
                    # forms (leetspeak undo + repeated-char collapse). A
                    # transformed form reaching the brand exactly (distance 0)
                    # is itself a strong typosquat signal; the raw label must
                    # differ from the brand by 1..max edits.
                    raw_dist = jellyfish.damerau_levenshtein_distance(label, token)
                    transformed_forms = {normalised, collapsed} - {label}
                    transformed_dist = min(
                        (jellyfish.damerau_levenshtein_distance(c, token)
                         for c in transformed_forms),
                        default=self._typo_max_distance + 1,
                    )
                    hit = (
                        (1 <= raw_dist <= self._typo_max_distance)
                        or (transformed_dist <= self._typo_max_distance)
                    )
                    if hit:
                        best = min(raw_dist, transformed_dist)
                        keyboard = self._is_keyboard_slip(normalised, token)
                        severity = "critical" if best == 1 else "high"
                        result.findings.append(BrandFinding(
                            finding_type="typosquatting",
                            brand=brand,
                            brand_name=self.display_name(brand),
                            detail=(
                                f"Domain label '{label}' is within edit distance "
                                f"{best} of protected brand '{token}'"
                                + (" (keyboard-adjacent substitution)" if keyboard else "")
                                + (" after leetspeak normalisation"
                                   if normalised != label else "")
                                + "."
                            ),
                            severity=severity,
                            score=self._weights.get("typosquatting", 0.30),
                        ))
                        if brand not in result.brands_detected:
                            result.brands_detected.append(brand)
                            result.brand_locations.setdefault(brand, []).append(
                                "hostname"
                            )
                        break  # one finding per label/brand pair

    def _detect_homoglyphs(
        self, parsed: ParsedURL, result: BrandIntelligenceResult
    ) -> None:
        """Detect Unicode look-alike substitutions of protected brands."""
        hostname = parsed.hostname or ""
        if hostname.isascii():
            return
        nfkc = unicodedata.normalize("NFKC", hostname).lower()
        folded = "".join(self._confusables.get(ch, ch) for ch in nfkc)
        if folded == nfkc.lower():
            return  # non-ASCII but no known confusables (e.g. genuine IDN)
        for brand, entry in self._brands.items():
            for token in entry["tokens"]:
                if len(token) < 4 or token in nfkc:
                    continue
                if token in folded:
                    substituted = [
                        ch for ch in hostname
                        if ch in self._confusables and not ch.isascii()
                    ]
                    result.findings.append(BrandFinding(
                        finding_type="homoglyph",
                        brand=brand,
                        brand_name=self.display_name(brand),
                        detail=(
                            f"Hostname uses Unicode look-alike characters "
                            f"({', '.join(repr(c) for c in substituted[:5])}) that "
                            f"render as protected brand '{token}'. This is a "
                            f"homoglyph spoofing attack."
                        ),
                        severity="critical",
                        score=self._weights.get("homoglyph", 0.30),
                    ))
                    if brand not in result.brands_detected:
                        result.brands_detected.append(brand)
                        result.brand_locations.setdefault(brand, []).append("hostname")
                    break

    def _verify_official_domains(self, result: BrandIntelligenceResult) -> None:
        """Emit a mismatch finding for every referenced non-official brand."""
        for brand in result.brands_detected:
            locations = result.brand_locations.get(brand, [])
            domain_level = any(
                loc in ("hostname", "subdomain") for loc in locations
            ) or result.has_finding("typosquatting") or result.has_finding("homoglyph")
            severity = "high" if domain_level else "info"
            weight = (
                self._weights.get("official_domain_mismatch", 0.30)
                if domain_level
                else self._weights.get("brand_token", 0.10)
            )
            result.findings.append(BrandFinding(
                finding_type=(
                    "official_domain_mismatch" if domain_level else "brand_token_reference"
                ),
                brand=brand,
                brand_name=self.display_name(brand),
                detail=(
                    f"Brand '{self.display_name(brand)}' referenced in "
                    f"{'/'.join(locations) or 'URL'}, but registrable domain "
                    f"'{result.registrable_domain}' does not belong to the "
                    f"official {self.display_name(brand)} infrastructure."
                ),
                severity=severity,
                score=weight,
            ))

    def _detect_prefix_suffix(
        self, parsed: ParsedURL, result: BrandIntelligenceResult
    ) -> None:
        """Detect misleading affix + brand combinations (secure-google, ...)."""
        host_labels = "-".join(self._candidate_labels(parsed, include_subdomains=True))
        for brand in result.brands_detected:
            tokens = self._brands[brand]["tokens"]
            for token in tokens:
                if token not in host_labels:
                    continue
                matched = [
                    affix for affix in self._risky_affixes
                    if affix != token and affix in host_labels
                ]
                if matched:
                    result.findings.append(BrandFinding(
                        finding_type="misleading_affix",
                        brand=brand,
                        brand_name=self.display_name(brand),
                        detail=(
                            f"Domain combines protected brand '{token}' with "
                            f"misleading term(s): {', '.join(sorted(set(matched))[:4])}. "
                            f"Patterns like 'secure-{token}' or '{token}-login' "
                            f"imitate official services."
                        ),
                        severity="high",
                        score=self._weights.get("prefix_suffix", 0.15),
                    ))
                    break

    def _assess_cloud_hosting(
        self, parsed: ParsedURL, result: BrandIntelligenceResult
    ) -> None:
        """Raise suspicion for brand impersonation hosted on cloud platforms."""
        cloud = self._cloud.analyze(parsed.raw_url)
        if not cloud.is_cloud_hosted:
            return
        # Cloud hosting alone is NEVER malicious.
        brand_mismatch = any(
            f.finding_type in (
                "official_domain_mismatch", "typosquatting", "homoglyph",
                "brand_conflict",
            )
            for f in result.findings
        )
        text = f"{parsed.subdomain} {parsed.path} {parsed.query}".lower()
        credential_context = any(sig in text for sig in self._credential_signals)
        if brand_mismatch and credential_context:
            brand = result.brands_detected[0]
            result.findings.append(BrandFinding(
                finding_type="cloud_hosted_impersonation",
                brand=brand,
                brand_name=self.display_name(brand),
                detail=(
                    f"Brand impersonation combined with credential-collection "
                    f"signals hosted on {cloud.provider}. Attackers abuse "
                    f"trusted cloud platforms to serve fake login pages."
                ),
                severity="high",
                score=self._weights.get("cloud_hosted_brand", 0.15),
            ))

    # ------------------------------------------------------------------
    # Scoring & explainability
    # ------------------------------------------------------------------

    def _score_conflict(
        self,
        result: BrandIntelligenceResult,
        context: Mapping[str, Any],
        owner_label: str,
    ) -> None:
        """Score a Brand Conflict on a trusted (official or cloud) domain.

        Unlike :meth:`_score`, this keeps the domain's trusted status intact
        and frames the risk as a *conflict* (the domain owner differs from the
        referenced brand) rather than an impersonating registrable domain.
        External context can amplify an existing high/critical concern.
        """
        score = sum(f.score for f in result.findings)

        if any(f.severity in ("high", "critical") for f in result.findings):
            age = context.get("domain_age_days")
            if age is not None and 0 <= int(age) < self._young_domain_days:
                score += self._weights.get("young_domain", 0.10)
                result.reasons.append(
                    f"Domain is only {int(age)} days old."
                )
            if context.get("ssl_valid") is False:
                score += self._weights.get("no_ssl", 0.05)
                result.reasons.append("No valid SSL certificate.")
            if context.get("whois_private") is True:
                score += self._weights.get("whois_hidden", 0.05)
                result.reasons.append("WHOIS ownership is hidden.")
            keyword_count = int(context.get("suspicious_keyword_count", 0) or 0)
            if keyword_count >= 2:
                score += self._weights.get("suspicious_keywords", 0.10)
                result.reasons.append(
                    f"URL contains {keyword_count} credential-harvesting keywords."
                )

        result.risk_score = round(min(1.0, score), 4)
        result.risk_level = self._risk_level_for(result.risk_score)

        conflicting = ", ".join(
            self.display_name(b) for b in result.brands_detected
            if b != result.official_brand
        )
        result.reasons.insert(0, (
            f"Brand conflict: the registrable domain "
            f"'{result.registrable_domain}' belongs to {owner_label}, but the "
            f"URL references a different trusted organisation "
            f"({conflicting}). Possible brand impersonation or deceptive "
            f"content (brand risk: {result.risk_level})."
        ))
        for finding in result.findings:
            if finding.detail not in result.reasons:
                result.reasons.append(finding.detail)

    def _score(
        self, result: BrandIntelligenceResult, context: Mapping[str, Any]
    ) -> None:
        """Compute the weighted brand risk score and generate reasons."""
        score = sum(f.score for f in result.findings)

        # External context only amplifies an existing brand concern.
        if result.findings and any(
            f.severity in ("high", "critical") for f in result.findings
        ):
            age = context.get("domain_age_days")
            if age is not None and 0 <= int(age) < self._young_domain_days:
                score += self._weights.get("young_domain", 0.10)
                result.reasons.append(
                    f"Domain is only {int(age)} days old - newly registered "
                    f"domains are common in brand impersonation campaigns."
                )
            if context.get("ssl_valid") is False:
                score += self._weights.get("no_ssl", 0.05)
                result.reasons.append(
                    "No valid SSL certificate for a page referencing a "
                    "protected brand."
                )
            if context.get("whois_private") is True:
                score += self._weights.get("whois_hidden", 0.05)
                result.reasons.append(
                    "WHOIS ownership is hidden while impersonating a brand."
                )
            keyword_count = int(context.get("suspicious_keyword_count", 0) or 0)
            if keyword_count >= 2:
                score += self._weights.get("suspicious_keywords", 0.10)
                result.reasons.append(
                    f"URL contains {keyword_count} credential-harvesting keywords."
                )

        result.risk_score = round(min(1.0, score), 4)
        if result.risk_score >= self._high_threshold:
            result.risk_level = "high"
        elif result.risk_score >= self._medium_threshold:
            result.risk_level = "medium"
        elif result.risk_score > 0:
            result.risk_level = "low"
        else:
            result.risk_level = "none"

        for finding in result.findings:
            result.reasons.append(finding.detail)
        if result.findings:
            brands = ", ".join(
                self.display_name(b) for b in result.brands_detected[:3]
            )
            result.reasons.insert(0, (
                f"Detected protected brand reference(s): {brands}. Observed "
                f"registrable domain '{result.registrable_domain}' is not "
                f"official. Possible brand impersonation "
                f"(brand risk: {result.risk_level})."
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_labels(
        parsed: ParsedURL, include_subdomains: bool = True
    ) -> list[str]:
        """Hyphen-split labels of the domain (and optionally subdomains)."""
        labels: list[str] = []
        domain = (parsed.domain or "").lower()
        if domain:
            labels.append(domain)
            labels.extend(p for p in domain.split("-") if p)
        if include_subdomains:
            for part in parsed.subdomain_parts or []:
                part = part.lower()
                if part and part != "www":
                    labels.append(part)
                    labels.extend(p for p in part.split("-") if p)
        # Deduplicate, preserve order
        seen: set[str] = set()
        unique = []
        for label in labels:
            if label not in seen and len(label) >= 3:
                seen.add(label)
                unique.append(label)
        return unique

    @staticmethod
    def _normalise_leet(text: str) -> str:
        """Undo leetspeak / visual ASCII substitutions."""
        result = text.lower()
        for pattern, replacement in _MULTI_CONFUSIONS:
            result = result.replace(pattern, replacement)
        return "".join(_LEET_MAP.get(ch, ch) for ch in result)

    @staticmethod
    def _is_keyboard_slip(candidate: str, target: str) -> bool:
        """True when the strings differ by one keyboard-adjacent substitution."""
        if len(candidate) != len(target):
            return False
        diffs = [
            (c, t) for c, t in zip(candidate, target) if c != t
        ]
        if len(diffs) != 1:
            return False
        c, t = diffs[0]
        return c in _KEYBOARD_ADJACENT.get(t, "")
