"""Image quality assessment for OCR diagnostics.

Measures resolution, brightness, contrast, blur, sharpness and estimated
noise, and returns structured metadata plus plain-English recommendations.
It never rejects an image - forensic evidence is always processed; poor
quality is merely diagnosed so investigators can interpret low confidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np

from .config import OCRForensicConfig
from .schemas import ImageQualityMetrics


class ImageQualityAnalyzer:
    """Computes diagnostic quality metrics from an evidence image."""

    def __init__(self, config: OCRForensicConfig | None = None) -> None:
        self._cfg = config or OCRForensicConfig()

    def analyze_path(self, image_path: Path | str) -> ImageQualityMetrics:
        """Load an image from disk and assess it (never raises for images)."""
        image = cv2.imread(str(image_path))
        if image is None:
            return ImageQualityMetrics(recommendations=["Image could not be decoded for quality assessment."])
        return self.analyze_array(image)

    def analyze_array(self, image: np.ndarray) -> ImageQualityMetrics:
        """Assess a decoded image (BGR or grayscale numpy array)."""
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        height, width = gray.shape[:2]

        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        contrast = float(gray.std())
        noise = self._estimate_noise(gray)
        # Sharpness proxy: mean gradient magnitude, normalised into ~0-1.
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sharpness = float(np.mean(np.sqrt(gx * gx + gy * gy)) / 255.0)

        cfg = self._cfg
        metrics = ImageQualityMetrics(
            width=width, height=height,
            megapixels=round(width * height / 1_000_000, 3),
            brightness=round(brightness, 2),
            contrast=round(contrast, 2),
            blur_score=round(blur_score, 2),
            sharpness=round(sharpness, 4),
            estimated_noise=round(noise, 3),
            low_resolution=max(width, height) < cfg.min_dpi_dimension,
            is_blurry=blur_score < cfg.blur_warn_below,
            is_dark=brightness < cfg.dark_below,
            is_bright=brightness > cfg.bright_above,
            is_low_contrast=contrast < cfg.low_contrast_below,
            is_noisy=noise > cfg.noise_warn_above,
        )
        metrics.recommendations = self._recommend(metrics)
        return metrics

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _estimate_noise(gray: np.ndarray) -> float:
        """Mean absolute residual after a median filter (noise proxy)."""
        denoised = cv2.medianBlur(gray, 3)
        return float(np.mean(cv2.absdiff(gray, denoised)))

    @staticmethod
    def _recommend(m: ImageQualityMetrics) -> List[str]:
        tips: List[str] = []
        if m.low_resolution:
            tips.append("Low resolution: recapture at higher resolution or zoom for sharper text.")
        if m.is_blurry:
            tips.append("Image appears blurry: OCR confidence may be reduced; use a sharper capture if possible.")
        if m.is_dark:
            tips.append("Image is dark: increase brightness/contrast before re-capture for better recognition.")
        if m.is_bright:
            tips.append("Image is over-exposed: reduce glare/brightness to avoid washed-out text.")
        if m.is_low_contrast:
            tips.append("Low contrast between text and background: adjust contrast for clearer recognition.")
        if m.is_noisy:
            tips.append("High noise detected: a cleaner capture would improve recognition accuracy.")
        if not tips:
            tips.append("Image quality is adequate for OCR.")
        return tips
