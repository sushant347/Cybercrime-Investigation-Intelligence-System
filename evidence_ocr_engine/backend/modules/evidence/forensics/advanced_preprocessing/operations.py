"""Pure image operations used by the advanced preprocessing engine.

Every function takes an RGB uint8 numpy array and returns a *new* array plus
a human-readable detail string. No function ever touches disk or mutates its
input - the original evidence is untouchable by design.
"""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from ..config import ForensicsConfig

Result = Tuple[np.ndarray, str]


def adaptive_denoise(image: np.ndarray, cfg: ForensicsConfig, noise_level: float) -> Result:
    """Non-local-means denoising with strength scaled to the measured noise."""
    strength = float(np.clip(noise_level * 0.9, 3.0, cfg.denoise_strength_max))
    out = cv2.fastNlMeansDenoisingColored(
        image, None, h=strength, hColor=strength,
        templateWindowSize=7, searchWindowSize=21,
    )
    return out, f"non_local_means(h={strength:.1f})"


def clahe(image: np.ndarray, cfg: ForensicsConfig) -> Result:
    """CLAHE on the LAB luminance channel."""
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l_channel, a, b = cv2.split(lab)
    enhancer = cv2.createCLAHE(
        clipLimit=cfg.clahe_clip_limit,
        tileGridSize=(cfg.clahe_tile_grid, cfg.clahe_tile_grid),
    )
    merged = cv2.merge((enhancer.apply(l_channel), a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2RGB), (
        f"clahe(clip={cfg.clahe_clip_limit}, tiles={cfg.clahe_tile_grid})"
    )


def illumination_correction(image: np.ndarray, cfg: ForensicsConfig) -> Result:
    """Flatten uneven lighting by dividing by a heavily blurred background."""
    kernel = max(31, int(min(image.shape[:2]) * cfg.illumination_kernel_frac) | 1)
    gray_bg = cv2.GaussianBlur(image, (kernel, kernel), 0).astype(np.float32) + 1.0
    corrected = image.astype(np.float32) / gray_bg
    corrected = cv2.normalize(corrected, None, 0, 255, cv2.NORM_MINMAX)
    return corrected.astype(np.uint8), f"background_division(kernel={kernel})"


def shadow_removal(image: np.ndarray, cfg: ForensicsConfig) -> Result:
    """Classic per-channel shadow removal: dilate -> median -> difference."""
    kernel = np.ones((cfg.shadow_dilate_kernel, cfg.shadow_dilate_kernel), np.uint8)
    planes = []
    for channel in cv2.split(image):
        background = cv2.medianBlur(cv2.dilate(channel, kernel), cfg.shadow_median_kernel)
        diff = 255 - cv2.absdiff(channel, background)
        planes.append(cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX))
    return cv2.merge(planes).astype(np.uint8), (
        f"dilate_median_diff(dilate={cfg.shadow_dilate_kernel}, "
        f"median={cfg.shadow_median_kernel})"
    )


def deskew(image: np.ndarray, angle_deg: float) -> Result:
    """Rotate around the centre, expanding the canvas to avoid cropping."""
    h, w = image.shape[:2]
    centre = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(centre, angle_deg, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w, new_h = int(h * sin + w * cos), int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - centre[0]
    matrix[1, 2] += new_h / 2 - centre[1]
    out = cv2.warpAffine(image, matrix, (new_w, new_h),
                         flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, f"rotate({angle_deg:.2f}deg)"


def perspective_correction(image: np.ndarray, cfg: ForensicsConfig) -> Tuple[np.ndarray, str, bool]:
    """Warp a photographed page flat when a dominant quadrilateral exists.

    Returns ``(image, detail, applied)`` - unlike the other operations this
    one is conditional on document geometry being detected.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, "no contours", False
    frame_area = image.shape[0] * image.shape[1]
    best = max(contours, key=cv2.contourArea)
    if cv2.contourArea(best) < cfg.perspective_min_area_frac * frame_area:
        return image, "no dominant quadrilateral", False
    peri = cv2.arcLength(best, True)
    approx = cv2.approxPolyDP(best, 0.02 * peri, True)
    if len(approx) != 4:
        return image, "dominant contour not 4-sided", False
    pts = approx.reshape(4, 2).astype(np.float32)
    ordered = _order_corners(pts)
    tl, tr, br, bl = ordered
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 50 or height < 50:
        return image, "target too small", False
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
                   dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(ordered, dst)
    return (cv2.warpPerspective(image, matrix, (width, height)),
            f"warp({width}x{height})", True)


def morphological_cleanup(image: np.ndarray, cfg: ForensicsConfig) -> Result:
    """Gentle open+close on luminance to knock out speckles and fill pinholes."""
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (cfg.morph_kernel_size, cfg.morph_kernel_size)
    )
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l_channel, a, b = cv2.split(lab)
    opened = cv2.morphologyEx(l_channel, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
    out = cv2.cvtColor(cv2.merge((closed, a, b)), cv2.COLOR_LAB2RGB)
    return out, f"open_close(kernel={cfg.morph_kernel_size})"


def edge_enhancement(image: np.ndarray, cfg: ForensicsConfig) -> Result:
    """Unsharp masking with configurable amount (gentler than kernel sharpen)."""
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=2.0)
    amount = cfg.edge_enhance_amount
    out = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)
    return out, f"unsharp_mask(amount={amount})"


def super_resolution(image: np.ndarray, cfg: ForensicsConfig) -> Result:
    """Upscale small captures. Uses Lanczos resampling (deterministic and
    dependency-free); a DNN super-resolution model can be plugged in later
    behind the same signature without touching callers."""
    h, w = image.shape[:2]
    smallest = min(h, w)
    scale = min(cfg.super_resolution_max_scale,
                cfg.super_resolution_trigger_px / max(1, smallest))
    scale = max(1.0, scale)
    out = cv2.resize(image, (int(w * scale), int(h * scale)),
                     interpolation=cv2.INTER_LANCZOS4)
    return out, f"lanczos_x{scale:.2f}"


def _order_corners(pts: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]
    ordered[1] = pts[np.argmin(d)]
    ordered[3] = pts[np.argmax(d)]
    return ordered
