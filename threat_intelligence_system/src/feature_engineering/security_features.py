"""
Security-oriented feature extraction for the Phishing URL Detection Engine.

Detects security-relevant properties of URLs such as HTTPS usage,
IP-based hostnames, punycode encoding, homograph character attacks,
URL shortener usage, and dangerous URI schemes.
"""

from typing import Any

from src.config.settings import get_settings
from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityFeatureExtractor(BaseFeatureExtractor):
    """
    Extract security-related features from parsed URLs.

    These features capture whether the URL employs tactics commonly
    associated with phishing or malicious activity:
        - Lack of HTTPS encryption.
        - IP-based hostnames hiding domain identity.
        - Punycode / internationalized domain names used for homograph
          attacks.
        - Individual homograph (lookalike) characters from Cyrillic,
          Armenian, or other scripts.
        - Known URL shorteners obscuring the final destination.
        - Dangerous URI schemes (data:, javascript:).

    Computes 8 features.

    Usage:
        >>> extractor = SecurityFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["has_homograph_chars"])
        0
    """

    _FEATURE_NAMES: list[str] = [
        "is_https",
        "is_ip_based",
        "is_punycode",
        "has_homograph_chars",
        "homograph_char_count",
        "is_url_shortener",
        "has_data_uri",
        "has_javascript_uri",
    ]

    def __init__(self) -> None:
        """Initialize with homograph map and URL shortener list from settings."""
        settings = get_settings()
        self._homograph_map: dict[str, str] = dict(settings.threat.homograph_map)
        self._url_shorteners: list[str] = list(settings.threat.url_shorteners)
        logger.debug(
            "SecurityFeatureExtractor initialized: %d homograph chars, "
            "%d shortener domains",
            len(self._homograph_map),
            len(self._url_shorteners),
        )

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'security'.
        """
        return "security"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute security features for a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of 8 security features.
        """
        raw_url = parsed_url.raw_url
        raw_lower = raw_url.lower()

        # HTTPS
        is_https = parsed_url.scheme == "https"

        # IP-based hostname
        is_ip_based = parsed_url.is_ip_based

        # Punycode detection
        hostname = parsed_url.hostname
        labels = hostname.split(".") if hostname else []
        is_punycode = any(label.startswith("xn--") for label in labels)

        # Homograph character detection
        homograph_count = 0
        for char in raw_url:
            if char in self._homograph_map:
                homograph_count += 1
        has_homograph = homograph_count > 0

        # URL shortener
        hostname_lower = hostname.lower()
        is_shortener = hostname_lower in self._url_shorteners
        if not is_shortener:
            # Check registered domain
            reg_domain = parsed_url.registered_domain.lower()
            is_shortener = reg_domain in self._url_shorteners

        # Dangerous URI schemes
        has_data_uri = raw_lower.startswith("data:")
        has_javascript_uri = raw_lower.startswith("javascript:")

        features: dict[str, Any] = {
            "is_https": int(is_https),
            "is_ip_based": int(is_ip_based),
            "is_punycode": int(is_punycode),
            "has_homograph_chars": int(has_homograph),
            "homograph_char_count": homograph_count,
            "is_url_shortener": int(is_shortener),
            "has_data_uri": int(has_data_uri),
            "has_javascript_uri": int(has_javascript_uri),
        }

        logger.debug(
            "SecurityFeatureExtractor: https=%d, ip=%d, punycode=%d, "
            "homograph=%d, shortener=%d",
            features["is_https"],
            features["is_ip_based"],
            features["is_punycode"],
            features["has_homograph_chars"],
            features["is_url_shortener"],
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of security feature names.

        Returns:
            List of 8 feature name strings.
        """
        return list(self._FEATURE_NAMES)
