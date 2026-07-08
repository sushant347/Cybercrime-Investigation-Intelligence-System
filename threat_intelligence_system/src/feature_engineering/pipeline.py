"""
Feature extraction pipeline for the Phishing URL Detection Engine.

Orchestrates all registered ``BaseFeatureExtractor`` implementations,
parsing a raw URL once and running every extractor to produce a single
flat feature dictionary.  Supports single-URL and batch extraction,
plus DataFrame generation for ML training pipelines.
"""

from typing import Any

import pandas as pd

from src.feature_engineering.base import BaseFeatureExtractor
from src.feature_engineering.brand_features import BrandFeatureExtractor
from src.feature_engineering.character_features import CharacterFeatureExtractor
from src.feature_engineering.entropy_features import EntropyFeatureExtractor
from src.feature_engineering.length_features import LengthFeatureExtractor
from src.feature_engineering.lexical_features import LexicalFeatureExtractor
from src.feature_engineering.security_features import SecurityFeatureExtractor
from src.feature_engineering.structural_features import StructuralFeatureExtractor
from src.feature_engineering.tld_features import TLDFeatureExtractor
from src.parser.url_parser import URLParser
from src.utils.exceptions import FeatureExtractionError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FeaturePipeline:
    """
    Unified feature extraction pipeline.

    Manages a registry of ``BaseFeatureExtractor`` instances and
    executes them against parsed URLs to produce a flat feature
    dictionary suitable for ML model consumption.

    If no extractors are supplied at construction, all built-in
    extractors are registered automatically:
        - LengthFeatureExtractor
        - EntropyFeatureExtractor
        - CharacterFeatureExtractor
        - StructuralFeatureExtractor
        - LexicalFeatureExtractor
        - BrandFeatureExtractor
        - SecurityFeatureExtractor
        - TLDFeatureExtractor

    Usage:
        >>> pipeline = FeaturePipeline()
        >>> features = pipeline.extract("https://example.com/path?q=1")
        >>> print(len(features))
        72
        >>> df = pipeline.get_feature_dataframe(["https://a.com", "https://b.com"])
    """

    def __init__(
        self, extractors: list[BaseFeatureExtractor] | None = None
    ) -> None:
        """
        Initialize the feature pipeline.

        Args:
            extractors: Optional list of extractor instances. If None,
                        all default extractors are registered.
        """
        self._extractors: list[BaseFeatureExtractor] = []
        self._parser: URLParser = URLParser()

        if extractors is not None:
            for ext in extractors:
                self.register(ext)
        else:
            self._register_defaults()

        logger.info(
            "FeaturePipeline initialized with %d extractors: %s",
            len(self._extractors),
            [e.name for e in self._extractors],
        )

    def _register_defaults(self) -> None:
        """
        Register all built-in default feature extractors.

        This method is called automatically when no custom extractor
        list is provided at construction time.
        """
        default_extractors: list[BaseFeatureExtractor] = [
            LengthFeatureExtractor(),
            EntropyFeatureExtractor(),
            CharacterFeatureExtractor(),
            StructuralFeatureExtractor(),
            LexicalFeatureExtractor(),
            BrandFeatureExtractor(),
            SecurityFeatureExtractor(),
            TLDFeatureExtractor(),
        ]
        for ext in default_extractors:
            self.register(ext)

    def register(self, extractor: BaseFeatureExtractor) -> None:
        """
        Register a feature extractor with the pipeline.

        Args:
            extractor: An instance of a ``BaseFeatureExtractor`` subclass.

        Raises:
            TypeError: If the extractor is not a BaseFeatureExtractor.
        """
        if not isinstance(extractor, BaseFeatureExtractor):
            raise TypeError(
                f"Expected BaseFeatureExtractor, got {type(extractor).__name__}"
            )
        self._extractors.append(extractor)
        logger.debug("Registered extractor: %s", extractor.name)

    def extract(self, url: str) -> dict[str, Any]:
        """
        Parse a URL and extract all features.

        Parses the URL once using ``URLParser``, then invokes every
        registered extractor and merges the results into a single
        flat dictionary.

        Args:
            url: Raw URL string.

        Returns:
            Combined dictionary of all features from all extractors.

        Raises:
            FeatureExtractionError: If parsing or extraction fails.
        """
        try:
            parsed_url = self._parser.parse(url)
        except Exception as exc:
            raise FeatureExtractionError(
                url=url,
                extractor="URLParser",
                reason=f"Failed to parse URL: {exc}",
            ) from exc

        combined: dict[str, Any] = {}

        for extractor in self._extractors:
            try:
                features = extractor.extract(parsed_url)
                combined.update(features)
            except Exception as exc:
                logger.error(
                    "Extractor '%s' failed for URL '%s': %s",
                    extractor.name,
                    url[:80],
                    exc,
                )
                # Fill with None for failed extractors to maintain schema
                for feature_name in extractor.get_feature_names():
                    combined[feature_name] = None

        logger.debug(
            "Extracted %d features for URL '%s'",
            len(combined),
            url[:80],
        )

        return combined

    def extract_batch(self, urls: list[str]) -> list[dict[str, Any]]:
        """
        Extract features for a batch of URLs.

        Processes each URL independently, logging errors for individual
        failures without aborting the entire batch.

        Args:
            urls: List of raw URL strings.

        Returns:
            List of feature dictionaries, one per URL.  Failed URLs
            produce dictionaries with all feature values set to None.
        """
        results: list[dict[str, Any]] = []

        for idx, url in enumerate(urls):
            try:
                features = self.extract(url)
                results.append(features)
            except FeatureExtractionError as exc:
                safe_exc = str(exc).encode("ascii", errors="replace").decode("ascii")
                logger.warning(
                    "Batch extraction failed for URL %d/%d %r: %s",
                    idx + 1,
                    len(urls),
                    url[:80],
                    safe_exc,
                )
                # Produce a null-filled row to keep alignment
                null_row = {name: None for name in self.get_feature_names()}
                results.append(null_row)

        logger.info(
            "Batch extraction complete: %d/%d URLs processed successfully",
            sum(1 for r in results if any(v is not None for v in r.values())),
            len(urls),
        )

        return results

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of all feature names across all extractors.

        Returns:
            List of feature name strings.
        """
        names: list[str] = []
        for extractor in self._extractors:
            names.extend(extractor.get_feature_names())
        return names

    def get_feature_dataframe(self, urls: list[str]) -> pd.DataFrame:
        """
        Extract features for a list of URLs and return as a DataFrame.

        Convenience method for ML training pipelines that expect
        tabular data.  The resulting DataFrame has one row per URL
        and one column per feature, plus a 'url' column.

        Args:
            urls: List of raw URL strings.

        Returns:
            pandas DataFrame with features as columns and URLs as rows.
        """
        batch_features = self.extract_batch(urls)

        df = pd.DataFrame(batch_features, columns=self.get_feature_names())
        df.insert(0, "url", urls)

        logger.info(
            "Feature DataFrame created: %d rows x %d columns",
            len(df),
            len(df.columns),
        )

        return df
