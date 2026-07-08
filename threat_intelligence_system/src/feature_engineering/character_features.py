"""
Character-based feature extraction for the Phishing URL Detection Engine.

Counts and computes ratios of various character classes (digits, letters,
special characters, punctuation) within the URL string.  Phishing URLs
typically exhibit unusual character distributions compared to legitimate
domains.
"""

from typing import Any

from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.helpers import safe_division
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CharacterFeatureExtractor(BaseFeatureExtractor):
    """
    Extract character-distribution features from parsed URLs.

    Counts the absolute number and relative ratio of key character
    classes across the full URL string.  The features capture signal
    like:
        - High digit ratios indicating hex-encoded or numeric-ID-based
          phishing URLs.
        - Excessive special characters signalling obfuscation.
        - Unusual casing patterns used to evade filters.

    Computes 14 features covering digits, letters, casing, and
    individual punctuation marks that are especially indicative of
    phishing.

    Usage:
        >>> extractor = CharacterFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["digit_count"])
        5
    """

    _FEATURE_NAMES: list[str] = [
        "digit_count",
        "letter_count",
        "uppercase_count",
        "lowercase_count",
        "special_char_count",
        "dot_count",
        "slash_count",
        "hyphen_count",
        "underscore_count",
        "at_symbol_count",
        "tilde_count",
        "question_mark_count",
        "ampersand_count",
        "equals_sign_count",
        "percent_sign_count",
    ]

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'character'.
        """
        return "character"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Count and compute ratios of character classes in the URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of 14 character-based features (counts only --
            ratios can be derived downstream using url_length from
            length features).
        """
        url = parsed_url.normalized_url

        digit_count = sum(1 for ch in url if ch.isdigit())
        letter_count = sum(1 for ch in url if ch.isalpha())
        uppercase_count = sum(1 for ch in url if ch.isupper())
        lowercase_count = sum(1 for ch in url if ch.islower())
        special_char_count = sum(
            1 for ch in url if not ch.isalnum() and not ch.isspace()
        )

        dot_count = url.count(".")
        slash_count = url.count("/")
        hyphen_count = url.count("-")
        underscore_count = url.count("_")
        at_symbol_count = url.count("@")
        tilde_count = url.count("~")
        question_mark_count = url.count("?")
        ampersand_count = url.count("&")
        equals_sign_count = url.count("=")
        percent_sign_count = url.count("%")

        features: dict[str, Any] = {
            "digit_count": digit_count,
            "letter_count": letter_count,
            "uppercase_count": uppercase_count,
            "lowercase_count": lowercase_count,
            "special_char_count": special_char_count,
            "dot_count": dot_count,
            "slash_count": slash_count,
            "hyphen_count": hyphen_count,
            "underscore_count": underscore_count,
            "at_symbol_count": at_symbol_count,
            "tilde_count": tilde_count,
            "question_mark_count": question_mark_count,
            "ampersand_count": ampersand_count,
            "equals_sign_count": equals_sign_count,
            "percent_sign_count": percent_sign_count,
        }

        logger.debug(
            "CharacterFeatureExtractor: digits=%d, letters=%d, special=%d",
            digit_count,
            letter_count,
            special_char_count,
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of character feature names.

        Returns:
            List of 14 feature name strings.
        """
        return list(self._FEATURE_NAMES)
