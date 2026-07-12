"""
URL text preprocessor for transformer models.

Handles URL tokenization, character-level encoding, and subword preparation
for feeding URLs into transformer models.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PreprocessedURL:
    """
    Container for a preprocessed URL ready for model consumption.

    Attributes:
        original_url: The original URL string.
        cleaned_url: URL after cleaning and normalization.
        tokens: List of character or subword tokens.
        char_ids: List of character-level integer IDs.
        token_count: Number of tokens.
    """

    original_url: str
    cleaned_url: str
    tokens: list[str] = field(default_factory=list)
    char_ids: list[int] = field(default_factory=list)
    token_count: int = 0


class URLTextPreprocessor:
    """
    Preprocessor that transforms raw URLs into formats suitable for ML models.

    Supports three modes:
    1. Character-level tokenization -- splits URL into individual characters.
    2. Subword tokenization -- uses special URL-aware splitting.
    3. HuggingFace tokenization -- delegates to a HuggingFace tokenizer.

    The preprocessor is designed to be used in the data pipeline before
    feeding URLs into transformer or deep learning models.

    Attributes:
        max_length: Maximum sequence length (characters or tokens).
        mode: Tokenization mode ('char', 'subword', or 'huggingface').
    """

    # Character vocabulary for char-level encoding
    CHAR_VOCAB = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        ".-/:?=&#%+_~@!$'()*,;[]{}|\\^`<>\""
    )

    def __init__(
        self,
        max_length: int = 256,
        mode: str = "subword",
    ) -> None:
        """
        Initialize the URL text preprocessor.

        Args:
            max_length: Maximum sequence length for tokenization.
            mode: Tokenization mode -- 'char', 'subword', or 'huggingface'.
        """
        self.max_length = max_length
        self.mode = mode

        # Build character-to-id mapping
        self._char_to_id: dict[str, int] = {
            "<PAD>": 0,
            "<UNK>": 1,
        }
        for i, char in enumerate(self.CHAR_VOCAB, start=2):
            self._char_to_id[char] = i

        self._vocab_size = len(self._char_to_id)
        logger.debug("URLTextPreprocessor initialized with mode=%s, max_length=%d", mode, max_length)

    @property
    def vocab_size(self) -> int:
        """Get the vocabulary size for character-level encoding."""
        return self._vocab_size

    def clean_url(self, url: str) -> str:
        """
        Clean a URL for preprocessing.

        Steps:
        1. Strip whitespace.
        2. Remove protocol prefix for character models (optional).
        3. Truncate to max_length.

        Args:
            url: Raw URL string.

        Returns:
            Cleaned URL string.
        """
        url = url.strip()
        if len(url) > self.max_length * 4:
            url = url[:self.max_length * 4]
        return url

    def tokenize_chars(self, url: str) -> list[str]:
        """
        Tokenize a URL at the character level.

        Args:
            url: URL string.

        Returns:
            List of character tokens, padded or truncated to max_length.
        """
        chars = list(url[:self.max_length])

        # Pad if shorter than max_length
        if len(chars) < self.max_length:
            chars.extend(["<PAD>"] * (self.max_length - len(chars)))

        return chars

    def tokenize_subword(self, url: str) -> list[str]:
        """
        Tokenize a URL using URL-aware subword splitting.

        Splits on protocol separators, domain dots, path separators,
        query delimiters, and other URL-specific boundaries.

        Args:
            url: URL string.

        Returns:
            List of subword tokens, padded or truncated to max_length.
        """
        # Split on URL-specific boundaries while preserving delimiters
        tokens = re.split(r'(://|/|\?|&|=|#|\.|-|_|@|:)', url)
        tokens = [t for t in tokens if t]  # Remove empty strings

        # Truncate
        if len(tokens) > self.max_length:
            tokens = tokens[:self.max_length]

        # Pad
        if len(tokens) < self.max_length:
            tokens.extend(["<PAD>"] * (self.max_length - len(tokens)))

        return tokens

    def encode_chars(self, url: str) -> list[int]:
        """
        Encode a URL as a sequence of character IDs.

        Args:
            url: URL string.

        Returns:
            List of integer character IDs, padded to max_length.
        """
        cleaned = self.clean_url(url)
        ids = []
        for char in cleaned[:self.max_length]:
            ids.append(self._char_to_id.get(char, self._char_to_id["<UNK>"]))

        # Pad
        while len(ids) < self.max_length:
            ids.append(self._char_to_id["<PAD>"])

        return ids

    def preprocess(self, url: str) -> PreprocessedURL:
        """
        Preprocess a single URL for model consumption.

        Args:
            url: Raw URL string.

        Returns:
            PreprocessedURL with tokens and character IDs.
        """
        cleaned = self.clean_url(url)

        if self.mode == "char":
            tokens = self.tokenize_chars(cleaned)
        elif self.mode == "subword":
            tokens = self.tokenize_subword(cleaned)
        else:
            tokens = self.tokenize_subword(cleaned)

        char_ids = self.encode_chars(cleaned)

        return PreprocessedURL(
            original_url=url,
            cleaned_url=cleaned,
            tokens=tokens,
            char_ids=char_ids,
            token_count=len([t for t in tokens if t != "<PAD>"]),
        )

    def preprocess_batch(self, urls: list[str]) -> list[PreprocessedURL]:
        """
        Preprocess a batch of URLs.

        Args:
            urls: List of raw URL strings.

        Returns:
            List of PreprocessedURL instances.
        """
        return [self.preprocess(url) for url in urls]

    def to_char_matrix(self, urls: list[str]) -> np.ndarray:
        """
        Convert a batch of URLs to a character ID matrix.

        Args:
            urls: List of URL strings.

        Returns:
            NumPy array of shape (len(urls), max_length) with character IDs.
        """
        matrix = np.zeros((len(urls), self.max_length), dtype=np.int32)
        for i, url in enumerate(urls):
            ids = self.encode_chars(url)
            matrix[i] = ids
        return matrix

    def prepare_for_transformer(
        self,
        urls: list[str],
        tokenizer: Any,
    ) -> dict[str, Any]:
        """
        Prepare URLs for a HuggingFace transformer model.

        Args:
            urls: List of URL strings.
            tokenizer: HuggingFace tokenizer instance.

        Returns:
            Dictionary with 'input_ids', 'attention_mask', and optionally 'token_type_ids'.
        """
        cleaned_urls = [self.clean_url(url) for url in urls]

        encodings = tokenizer(
            cleaned_urls,
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
            return_tensors="np",
        )

        return dict(encodings)
