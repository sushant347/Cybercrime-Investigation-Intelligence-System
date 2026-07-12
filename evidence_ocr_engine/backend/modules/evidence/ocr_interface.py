"""OCR abstraction layer.

:class:`BaseOCR` defines the contract every OCR engine must satisfy, allowing
new engines to be plugged in without changing the pipeline (Open/Closed
principle, Dependency Injection). :class:`FutureOCRService` documents how a
second engine (e.g. EasyOCR, cloud OCR, a fine-tuned model) will be added in
later research iterations.

Engines must return recognised text **verbatim** - no translation,
autocorrection or normalisation is permitted at this layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np

from .models import OCRLine


class BaseOCR(ABC):
    """Abstract OCR engine interface.

    Implementations receive a preprocessed RGB image (numpy array, HxWx3,
    uint8) and return the recognised lines with confidences and 4-point
    bounding polygons in pixel coordinates of the given image.
    """

    #: Human-readable engine identifier stored with every result.
    name: str = "base"

    @abstractmethod
    def recognize(self, image: np.ndarray) -> List[OCRLine]:
        """Run OCR on one image and return recognised lines in reading order.

        Args:
            image: RGB image (H x W x 3, uint8).

        Returns:
            Recognised lines. Text must be the engine's raw output -
            unmodified, untranslated, uncorrected.

        Raises:
            OCRTimeoutError: If recognition exceeds the configured timeout.
            EvidenceError: For engine-specific unrecoverable failures.
        """

    def warmup(self) -> None:
        """Optionally pre-load models so the first evidence item is not slow."""
        return None


class FutureOCRService(BaseOCR):
    """Placeholder for the next OCR engine of the research project.

    Kept deliberately unimplemented: it demonstrates that the pipeline depends
    only on :class:`BaseOCR`, so integrating another engine requires
    implementing a single method - no pipeline changes.
    """

    name = "future-ocr"

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        raise NotImplementedError(
            "FutureOCRService is a research placeholder. Implement `recognize` "
            "to integrate an additional OCR engine (e.g. EasyOCR, TrOCR)."
        )
