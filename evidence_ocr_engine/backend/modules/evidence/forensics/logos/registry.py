"""Config-driven brand registry for logo detection.

Brand definitions are loaded from ``data/logo_brands.json`` (editable without
code changes - configuration-driven architecture). Each brand carries:

* ``keywords``  - words whose presence in OCR text indicates the brand
* ``hsv_ranges`` - dominant brand colours as HSV ranges (OpenCV scale:
  H 0-179, S/V 0-255) for the colour-signature detector
* optional template images in ``<logo_template_dir>/<brand_key>/`` used by
  the multi-scale template matcher when investigators provide real logo
  assets (binary assets are not shipped with the codebase).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ...logger import get_logger
from ...utils import EvidenceError

_DATA_FILE = Path(__file__).resolve().parent / "data" / "logo_brands.json"


@dataclass(frozen=True)
class BrandDefinition:
    """One supported brand."""

    key: str
    display_name: str
    keywords: tuple = ()
    #: List of [[h_lo, s_lo, v_lo], [h_hi, s_hi, v_hi]] HSV ranges.
    hsv_ranges: tuple = ()


class BrandRegistry:
    """Loads and serves brand definitions."""

    def __init__(self, data_file: Optional[Path] = None) -> None:
        self._log = get_logger("forensics.logos.registry")
        self._brands: Dict[str, BrandDefinition] = {}
        self._load(data_file or _DATA_FILE)

    def all(self) -> List[BrandDefinition]:
        return list(self._brands.values())

    def get(self, key: str) -> Optional[BrandDefinition]:
        return self._brands.get(key)

    def _load(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceError(f"Cannot load brand registry '{path}': {exc}") from exc
        for key, spec in raw.get("brands", {}).items():
            self._brands[key] = BrandDefinition(
                key=key,
                display_name=spec.get("display_name", key),
                keywords=tuple(k.lower() for k in spec.get("keywords", [])),
                hsv_ranges=tuple(tuple(map(tuple, r)) for r in spec.get("hsv_ranges", [])),
            )
        self._log.info("brand registry loaded: %d brands", len(self._brands))
