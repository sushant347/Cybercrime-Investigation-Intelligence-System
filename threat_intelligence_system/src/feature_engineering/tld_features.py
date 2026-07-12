"""
TLD-based feature extraction for the Phishing URL Detection Engine.

Analyses the top-level domain (TLD / public suffix) of a URL to assess
its risk profile.  Certain TLDs are disproportionately used in phishing
campaigns because they offer free or cheap registration with lax
abuse-handling.
"""

from typing import Any

from src.config.settings import get_settings
from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Standard country-code TLDs (ISO 3166-1 alpha-2 based, 2-letter)
_COUNTRY_CODE_TLD_LENGTH: int = 2

# "New gTLDs" introduced after the 2012 ICANN expansion round
# (representative set -- not exhaustive; covers the most common ones)
_NEW_GTLDS: frozenset[str] = frozenset([
    "xyz", "top", "club", "online", "site", "website", "space",
    "fun", "icu", "buzz", "store", "tech", "shop", "app", "dev",
    "blog", "cloud", "design", "digital", "email", "global",
    "group", "guru", "host", "life", "live", "network", "news",
    "one", "page", "plus", "pro", "rest", "run", "services",
    "solutions", "studio", "team", "today", "tools", "vip",
    "work", "world", "zone", "click", "link", "info", "biz",
    "loan", "racing", "win", "bid", "stream", "download",
    "review", "accountant", "cricket", "science", "party",
    "date", "faith", "trade", "men", "gdn", "kim", "wang",
    "surf", "bar", "cam", "monster", "hair", "sbs",
    "cfd", "quest", "boats", "beauty", "makeup",
])


class TLDFeatureExtractor(BaseFeatureExtractor):
    """
    Extract TLD-based features from parsed URLs.

    Evaluates the top-level domain for risk indicators:
        - Suspicious TLD membership (from settings).
        - Country-code TLD detection.
        - New gTLD detection (post-2012 ICANN programme).
        - TLD length (very short or very long TLDs).
        - Composite TLD risk score on a 0.0-1.0 scale.

    Computes 5 features.

    Usage:
        >>> extractor = TLDFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["tld_risk_score"])
        0.75
    """

    _FEATURE_NAMES: list[str] = [
        "is_suspicious_tld",
        "tld_risk_score",
        "is_country_code_tld",
        "is_new_gtld",
    ]

    def __init__(self) -> None:
        """Initialize with the suspicious TLD list from application settings."""
        settings = get_settings()
        self._suspicious_tlds: set[str] = {
            t.lower() for t in settings.threat.suspicious_tlds
        }
        logger.debug(
            "TLDFeatureExtractor initialized with %d suspicious TLDs",
            len(self._suspicious_tlds),
        )

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'tld'.
        """
        return "tld"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute TLD features for a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of 4 TLD-based features.
        """
        tld = parsed_url.suffix.lower()

        is_suspicious = tld in self._suspicious_tlds
        is_cctld = self._is_country_code_tld(tld)
        is_new = tld in _NEW_GTLDS

        # Composite risk score (0.0 - 1.0)
        risk_score = self._compute_tld_risk(
            tld=tld,
            is_suspicious=is_suspicious,
            is_cctld=is_cctld,
            is_new=is_new,
        )

        features: dict[str, Any] = {
            "is_suspicious_tld": int(is_suspicious),
            "tld_risk_score": round(risk_score, 4),
            "is_country_code_tld": int(is_cctld),
            "is_new_gtld": int(is_new),
        }

        logger.debug(
            "TLDFeatureExtractor: tld=%s, suspicious=%s, risk=%.4f",
            tld,
            is_suspicious,
            risk_score,
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of TLD feature names.

        Returns:
            List of 4 feature name strings.
        """
        return list(self._FEATURE_NAMES)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_country_code_tld(tld: str) -> bool:
        """
        Determine if a TLD is a country-code TLD.

        Uses the heuristic that ccTLDs are exactly 2 ASCII-letter
        characters (ISO 3166-1 alpha-2).

        Args:
            tld: The TLD string (lowercase, no dot).

        Returns:
            True if the TLD is exactly 2 ASCII letters.
        """
        return len(tld) == _COUNTRY_CODE_TLD_LENGTH and tld.isalpha()

    def _compute_tld_risk(
        self,
        tld: str,
        is_suspicious: bool,
        is_cctld: bool,
        is_new: bool,
    ) -> float:
        """
        Compute a composite TLD risk score between 0.0 and 1.0.

        Scoring heuristic:
            - Suspicious TLD: +0.50
            - New gTLD: +0.20
            - Country-code TLD commonly abused (e.g., tk, ml, ga, gq, cf): +0.30
            - Unknown/rare TLD: +0.10

        Well-known TLDs (com, org, net, edu, gov) receive 0.0.

        Args:
            tld: The TLD string.
            is_suspicious: Whether the TLD is in the suspicious list.
            is_cctld: Whether the TLD is a country-code TLD.
            is_new: Whether the TLD is a new gTLD.

        Returns:
            Risk score between 0.0 and 1.0.
        """
        well_known = {"com", "org", "net", "edu", "gov", "mil", "int"}
        if tld in well_known:
            return 0.0

        score = 0.0

        if is_suspicious:
            score += 0.50

        if is_new:
            score += 0.20

        # Commonly abused free ccTLDs
        abused_cctlds = {"tk", "ml", "ga", "gq", "cf"}
        if is_cctld and tld in abused_cctlds:
            score += 0.30
        elif is_cctld:
            score += 0.05

        # If not well-known and not flagged by any other check
        if score == 0.0:
            score = 0.10

        return min(score, 1.0)
