"""
Abstract base class for feature extractors in the Phishing URL Detection Engine.

All feature extractors inherit from ``BaseFeatureExtractor`` to guarantee
a uniform interface consumed by the ``FeaturePipeline``.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.parser.url_parser import ParsedURL
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseFeatureExtractor(ABC):
    """
    Abstract base class that every feature extractor must subclass.

    Defines the contract for feature extraction: each extractor must
    implement ``extract()`` which receives a ``ParsedURL`` and returns
    a flat dictionary of named features.

    Subclasses should:
        1. Override the ``name`` property to return a unique human-readable
           identifier (e.g., 'length', 'entropy', 'brand').
        2. Implement ``extract()`` to compute and return features.
        3. Implement ``get_feature_names()`` to declare the list of feature
           names that ``extract()`` will produce.

    Usage:
        >>> class MyExtractor(BaseFeatureExtractor):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_features"
        ...     def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        ...         return {"my_feature_1": 42}
        ...     def get_feature_names(self) -> list[str]:
        ...         return ["my_feature_1"]
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the unique name identifier for this extractor.

        Returns:
            A short, descriptive name string (e.g., 'length', 'entropy').
        """

    @abstractmethod
    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Extract features from a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` dataclass instance containing
                        the decomposed URL components.

        Returns:
            A dictionary mapping feature names (str) to their computed
            values (int, float, bool, str, etc.).
        """

    @abstractmethod
    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of feature names this extractor produces.

        This enables the ``FeaturePipeline`` to build a consistent
        feature schema without invoking ``extract()``.

        Returns:
            List of feature name strings.
        """
