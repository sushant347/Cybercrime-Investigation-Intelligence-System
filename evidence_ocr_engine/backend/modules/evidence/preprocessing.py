"""Adaptive image preprocessing for OCR.

The preprocessor first *assesses* image quality (blur, brightness, contrast,
noise, skew, resolution) and then applies only the corrective steps that the
assessment indicates. Every applied step is recorded so the forensic audit
trail shows exactly how the working copy was enhanced.

The original evidence file is **never** modified - all operations run on an
in-memory working copy.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import EvidenceConfig
from .logger import get_logger
from .models import ImageQualityReport
from .utils import InvalidImageError


def load_image(path: Path | str) -> np.ndarray:
    """Load an evidence image as an RGB numpy array.

    Applies EXIF orientation correction (photos from phones are frequently
    stored rotated) and converts any mode (RGBA, palette, grayscale) to RGB.

    Raises:
        InvalidImageError: If the file cannot be decoded as an image.
    """
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)  # correct EXIF orientation
            rgb = img.convert("RGB")            # normalise mode
            return np.asarray(rgb)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError(f"Cannot decode image '{path}': {exc}") from exc


class ImagePreprocessor:
    """Quality-driven preprocessing pipeline.

    Usage::

        preprocessor = ImagePreprocessor(config)
        processed, steps = preprocessor.preprocess(image)
    """

    def __init__(self, config: EvidenceConfig) -> None:
        self._cfg = config
        self._log = get_logger("preprocessing")

    # ------------------------------------------------------------------ public

    def assess_quality(self, image: np.ndarray) -> ImageQualityReport:
        """Measure objective quality metrics used to select preprocessing steps."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        contrast = float(gray.std())
        noise_level = self._estimate_noise(gray)
        skew_angle = self._estimate_skew(gray)
        report = ImageQualityReport(
            width=image.shape[1],
            height=image.shape[0],
            blur_score=blur_score,
            brightness=brightness,
            contrast=contrast,
            noise_level=noise_level,
            skew_angle=skew_angle,
        )
        self._log.debug("quality: %s", report)
        return report

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """Run the adaptive pipeline and return (processed_rgb, steps_applied)."""
        steps: List[str] = ["convert_rgb", "exif_orientation"]
        cfg = self._cfg
        quality = self.assess_quality(image)

        # 1. Resize extremely large images (speeds up OCR, bounds memory).
        image, applied = self._resize_if_large(image)
        if applied:
            steps.append("resize_large")

        # 2. Resolution enhancement for very small captures (e.g. SMS crops).
        image, applied = self._upscale_if_small(image)
        if applied:
            steps.append("resolution_enhancement")

        # 3. Perspective correction for photographed documents.
        image, applied = self._perspective_correction(image)
        if applied:
            steps.append("perspective_correction")

        # 4. Deskew (small rotation) when a measurable skew is present.
        if abs(quality.skew_angle) >= cfg.deskew_min_angle:
            image = self._rotate(image, quality.skew_angle)
            steps.append(f"deskew({quality.skew_angle:.2f}deg)")

        # 5. Noise removal - median blur for salt & pepper, Gaussian when heavy.
        if quality.noise_level > cfg.noise_threshold:
            image = cv2.medianBlur(image, 3)
            steps.append("median_blur")
            if quality.noise_level > cfg.noise_threshold * 2:
                image = cv2.GaussianBlur(image, (3, 3), 0)
                steps.append("gaussian_blur")

        # 6. CLAHE contrast enhancement for dark or low-contrast images.
        if quality.contrast < cfg.low_contrast_threshold or quality.brightness < cfg.dark_brightness_threshold:
            image = self._clahe(image)
            steps.append("clahe")

        # 7. Sharpening when the capture is blurry.
        if quality.blur_score < cfg.blur_threshold:
            image = self._sharpen(image)
            steps.append("sharpen")

        # 8. Border removal + whitespace trim (scanner edges, letterboxing).
        image, applied = self._trim_borders(image)
        if applied:
            steps.append("border_removal+whitespace_trim")

        # 9. Adaptive thresholding is applied only for document-like scans
        #    (near-grayscale, adequate contrast). Colour screenshots are left
        #    in RGB because binarisation destroys anti-aliased UI text.
        if self._looks_like_document_scan(image):
            image = self._adaptive_threshold(image)
            steps.append("adaptive_threshold")

        self._log.info("preprocessing steps applied: %s", ", ".join(steps))
        return image, steps

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _estimate_noise(gray: np.ndarray) -> float:
        """Noise estimate: mean absolute residual after a median filter."""
        denoised = cv2.medianBlur(gray, 3)
        return float(np.mean(cv2.absdiff(gray, denoised)))

    @staticmethod
    def _estimate_skew(gray: np.ndarray) -> float:
        """Estimate global text skew via the minimum-area rectangle of ink pixels."""
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = cv2.findNonZero(thresh)
        if coords is None or len(coords) < 100:
            return 0.0
        angle = cv2.minAreaRect(coords)[-1]
        if angle > 45.0:
            angle -= 90.0
        # Ignore implausible estimates: real evidence skew is small.
        return float(angle) if abs(angle) <= 15.0 else 0.0

    def _resize_if_large(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        h, w = image.shape[:2]
        largest = max(h, w)
        if largest <= self._cfg.max_image_dimension:
            return image, False
        scale = self._cfg.max_image_dimension / largest
        resized = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        return resized, True

    def _upscale_if_small(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        h, w = image.shape[:2]
        largest = max(h, w)
        if largest >= self._cfg.min_image_dimension:
            return image, False
        scale = min(3.0, self._cfg.min_image_dimension / largest)
        upscaled = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        return upscaled, True

    @staticmethod
    def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate around the centre, expanding the canvas to avoid cropping."""
        h, w = image.shape[:2]
        centre = (w / 2, h / 2)
        matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
        cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)
        matrix[0, 2] += new_w / 2 - centre[0]
        matrix[1, 2] += new_h / 2 - centre[1]
        return cv2.warpAffine(
            image, matrix, (new_w, new_h),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
        )

    def _perspective_correction(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Warp a photographed page to a flat rectangle if a dominant
        quadrilateral (>=55% of frame area) is detected."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 60, 180)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image, False
        frame_area = image.shape[0] * image.shape[1]
        best = max(contours, key=cv2.contourArea)
        if cv2.contourArea(best) < 0.55 * frame_area:
            return image, False
        peri = cv2.arcLength(best, True)
        approx = cv2.approxPolyDP(best, 0.02 * peri, True)
        if len(approx) != 4:
            return image, False
        pts = approx.reshape(4, 2).astype(np.float32)
        ordered = self._order_corners(pts)
        (tl, tr, br, bl) = ordered
        width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
        if width < 50 or height < 50:
            return image, False
        dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(ordered, dst)
        return cv2.warpPerspective(image, matrix, (width, height)), True

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
        ordered = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).ravel()
        ordered[0] = pts[np.argmin(s)]   # top-left
        ordered[2] = pts[np.argmax(s)]   # bottom-right
        ordered[1] = pts[np.argmin(d)]   # top-right
        ordered[3] = pts[np.argmax(d)]   # bottom-left
        return ordered

    @staticmethod
    def _clahe(image: np.ndarray) -> np.ndarray:
        """Contrast-limited adaptive histogram equalisation on the L channel."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l_channel, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        merged = cv2.merge((clahe.apply(l_channel), a, b))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)

    @staticmethod
    def _sharpen(image: np.ndarray) -> np.ndarray:
        """Unsharp masking - gentler than a kernel sharpen, fewer artefacts."""
        blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=2.0)
        return cv2.addWeighted(image, 1.5, blurred, -0.5, 0)

    @staticmethod
    def _trim_borders(image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Crop uniform dark scanner borders / white margins around content."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        # Content mask: pixels that differ from both pure white and pure black.
        mask = cv2.inRange(gray, 12, 243)
        coords = cv2.findNonZero(mask)
        if coords is None:
            return image, False
        x, y, w, h = cv2.boundingRect(coords)
        full_h, full_w = gray.shape
        # Only crop when it removes a meaningful margin but keeps most content.
        if w < 0.35 * full_w or h < 0.35 * full_h:
            return image, False
        if w >= full_w - 4 and h >= full_h - 4:
            return image, False
        pad = 8
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(full_w, x + w + pad), min(full_h, y + h + pad)
        return image[y0:y1, x0:x1], True

    @staticmethod
    def _looks_like_document_scan(image: np.ndarray) -> bool:
        """Heuristic: near-grayscale images with bright background are scans."""
        b, g, r = image[..., 2].astype(np.int16), image[..., 1].astype(np.int16), image[..., 0].astype(np.int16)
        colourfulness = float(np.mean(np.abs(r - g)) + np.mean(np.abs(g - b)))
        brightness = float(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).mean())
        return colourfulness < 4.0 and brightness > 150.0

    @staticmethod
    def _adaptive_threshold(image: np.ndarray) -> np.ndarray:
        """Binarise a document scan; returned as 3-channel RGB for the OCR API."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
