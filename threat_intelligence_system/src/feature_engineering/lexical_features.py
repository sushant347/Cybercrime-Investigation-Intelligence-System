"""
Lexical feature extraction for the Phishing URL Detection Engine.

Analyses the word-level and token-level properties of URLs including
token counts, token lengths, suspicious keyword presence, and
digit-to-letter ratios.
"""

from typing import Any

from src.config.settings import get_settings
from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.helpers import safe_division
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LexicalFeatureExtractor(BaseFeatureExtractor):
    """
    Extract lexical (word-level) features from parsed URLs.

    Tokenizes the URL by splitting on special characters and computes
    statistics about the resulting tokens.  Also checks for the
    presence of suspicious keywords commonly used in phishing URLs
    (e.g., 'login', 'verify', 'account', 'secure').

    Computes 7 features.

    Usage:
        >>> extractor = LexicalFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["suspicious_keyword_count"])
        2
    """

    _FEATURE_NAMES: list[str] = [
        "url_token_count",
        "avg_token_length",
        "max_token_length",
        "suspicious_keyword_count",
        "contains_suspicious_keyword",
        "longest_word_length",
        "digit_to_letter_ratio",
    ]

    def __init__(self) -> None:
        """Initialize with suspicious keywords from application settings."""
        settings = get_settings()
        self._suspicious_keywords: list[str] = list(
            settings.threat.suspicious_keywords
        )
        logger.debug(
            "LexicalFeatureExtractor initialized with %d suspicious keywords",
            len(self._suspicious_keywords),
        )

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'lexical'.
        """
        return "lexical"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute lexical features for a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of 7 lexical features.
        """
        tokens = parsed_url.url_tokens
        url_str = parsed_url.normalized_url.lower()

        # Token statistics
        token_count = len(tokens)
        token_lengths = [len(t) for t in tokens] if tokens else []
        avg_token_length = safe_division(
            sum(token_lengths), len(token_lengths), default=0.0
        )
        max_token_length = max(token_lengths) if token_lengths else 0

        # Suspicious keywords
        suspicious_count = 0
        for keyword in self._suspicious_keywords:
            if keyword in url_str:
                suspicious_count += 1

        contains_suspicious = suspicious_count > 0

        # Longest word length (same as max_token_length but explicit)
        longest_word_length = max_token_length

        # Digit-to-letter ratio
        digit_count = sum(1 for ch in url_str if ch.isdigit())
        letter_count = sum(1 for ch in url_str if ch.isalpha())
        digit_to_letter_ratio = safe_division(
            digit_count, letter_count, default=0.0
        )

        features: dict[str, Any] = {
            "url_token_count": token_count,
            "avg_token_length": round(avg_token_length, 4),
            "max_token_length": max_token_length,
            "suspicious_keyword_count": suspicious_count,
            "contains_suspicious_keyword": int(contains_suspicious),
            "longest_word_length": longest_word_length,
            "digit_to_letter_ratio": round(digit_to_letter_ratio, 4),
        }

        logger.debug(
            "LexicalFeatureExtractor: tokens=%d, suspicious=%d",
            token_count,
            suspicious_count,
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of lexical feature names.

        Returns:
            List of 7 feature name strings.
        """
        return list(self._FEATURE_NAMES)
