"""
Entropy-based feature extraction for the Phishing URL Detection Engine.

Computes Shannon entropy and related information-theoretic metrics for
various URL components.  Random-looking phishing URLs tend to have
higher entropy than legitimate branded URLs.
"""

import math
from collections import Counter
from typing import Any

from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.helpers import safe_division
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EntropyFeatureExtractor(BaseFeatureExtractor):
    """
    Extract entropy-based features from parsed URLs.

    Shannon entropy measures the information density (randomness) of a
    string.  Phishing URLs often contain randomly generated hostnames,
    hex-encoded payloads, or otherwise high-entropy strings that differ
    from the low-entropy patterns of legitimate brand domains.

    Features computed:
        - Shannon entropy of the full URL, hostname, domain, path,
          subdomain, and query.
        - Digit entropy ratio (entropy contribution from digits).
        - Vowel-to-consonant ratio of the full URL.

    Usage:
        >>> extractor = EntropyFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["url_entropy"])
        3.812
    """

    _VOWELS: frozenset[str] = frozenset("aeiouAEIOU")
    _CONSONANTS: frozenset[str] = frozenset(
        "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ"
    )

    _FEATURE_NAMES: list[str] = [
        "url_entropy",
        "hostname_entropy",
        "domain_entropy",
        "path_entropy",
        "subdomain_entropy",
        "query_entropy",
        "digit_entropy_ratio",
        "vowel_consonant_ratio",
    ]

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'entropy'.
        """
        return "entropy"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute entropy features for a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of 8 entropy-based features.
        """
        url_str = parsed_url.normalized_url

        url_entropy = self._shannon_entropy(url_str)
        hostname_entropy = self._shannon_entropy(parsed_url.hostname)
        domain_entropy = self._shannon_entropy(parsed_url.domain)
        path_entropy = self._shannon_entropy(parsed_url.path)
        subdomain_entropy = self._shannon_entropy(parsed_url.subdomain)
        query_entropy = self._shannon_entropy(parsed_url.query)

        # Digit entropy ratio: entropy of digit-only characters / total entropy
        digits_in_url = "".join(ch for ch in url_str if ch.isdigit())
        digit_ent = self._shannon_entropy(digits_in_url)
        digit_entropy_ratio = safe_division(digit_ent, url_entropy, default=0.0)

        # Vowel to consonant ratio
        vowel_count = sum(1 for ch in url_str if ch in self._VOWELS)
        consonant_count = sum(1 for ch in url_str if ch in self._CONSONANTS)
        vowel_consonant_ratio = safe_division(
            vowel_count, consonant_count, default=0.0
        )

        features: dict[str, Any] = {
            "url_entropy": round(url_entropy, 4),
            "hostname_entropy": round(hostname_entropy, 4),
            "domain_entropy": round(domain_entropy, 4),
            "path_entropy": round(path_entropy, 4),
            "subdomain_entropy": round(subdomain_entropy, 4),
            "query_entropy": round(query_entropy, 4),
            "digit_entropy_ratio": round(digit_entropy_ratio, 4),
            "vowel_consonant_ratio": round(vowel_consonant_ratio, 4),
        }

        logger.debug(
            "EntropyFeatureExtractor: url_entropy=%.4f, hostname_entropy=%.4f",
            features["url_entropy"],
            features["hostname_entropy"],
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of entropy feature names.

        Returns:
            List of 8 feature name strings.
        """
        return list(self._FEATURE_NAMES)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _shannon_entropy(text: str) -> float:
        """
        Compute Shannon entropy (in bits) for a string.

        Shannon entropy measures the average information content per
        character.  A perfectly uniform distribution of *n* distinct
        characters yields ``log2(n)`` bits, while a single repeated
        character yields 0 bits.

        Args:
            text: Input string.

        Returns:
            Shannon entropy value (>= 0.0).  Returns 0.0 for empty
            strings.
        """
        if not text:
            return 0.0

        length = len(text)
        counts = Counter(text)
        entropy = 0.0

        for count in counts.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy
