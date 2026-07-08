"""Generate example outputs for Prompt 2.5 (enhancement framework).

Ingests one demonstration evidence item whose stub OCR output contains
typical low-confidence Nepali + English recognition errors, runs Prompt 2
(clean) and Prompt 2.5 (enhance), and prints where the outputs landed.

The stub engine exists only to make the repository examples reproducible
offline; with PaddleOCR installed the same flow runs on real screenshots
(`python cli.py ingest ... && python cli.py clean ... && python cli.py enhance ...`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.modules.evidence import BaseOCR, EvidenceConfig, EvidencePipeline  # noqa: E402
from backend.modules.evidence.cleaning import CleaningService  # noqa: E402
from backend.modules.evidence.enhancement import EnhancementService  # noqa: E402
from backend.modules.evidence.models import OCRLine  # noqa: E402

#: (text with typical OCR errors, simulated recognition confidence)
OCR_LINES: List[tuple[str, float]] = [
    ("बोड सदस्यको प्रतिवद्वता अनुसार पुजी बृद्धि गर्ने निर्णय भयो", 0.41),
    ("कार्वदल स्थापना गरी दीर्वकालीन योजना बनाइनेछ", 0.38),
    ("Your acc0unt has been suspended, contact SUPP0RT", 0.52),
    ("Please 1ogin at http//nabil-verify.scam.top/verify", 0.58),
    ("send details to supp0rt@fake-bank.com with 0TP c0de", 0.47),
]


class LowConfidenceStubOCR(BaseOCR):
    """Deterministic stub emitting the demonstration lines above."""

    name = "demo-stub-low-confidence"

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        return [
            OCRLine(text=text, confidence=confidence,
                    bbox=[[10.0, 20.0 + i * 30], [600.0, 20.0 + i * 30],
                          [600.0, 44.0 + i * 30], [10.0, 44.0 + i * 30]])
            for i, (text, confidence) in enumerate(OCR_LINES)
        ]


def main() -> int:
    config = EvidenceConfig.from_env()
    samples = ROOT / "samples"
    samples.mkdir(exist_ok=True)
    source = samples / "low_quality_scan_demo.png"
    image = Image.new("RGB", (660, 220), "white")
    draw = ImageDraw.Draw(image)
    for index, (text, _conf) in enumerate(OCR_LINES):
        draw.text((10, 20 + index * 30), text, fill="black")
    image.save(source)

    pipeline = EvidencePipeline(config, LowConfidenceStubOCR())
    ocr_result = pipeline.process_file(
        source, case_title="Demo: low-quality scan (Prompt 2.5 example)",
        notes="synthetic low-confidence OCR for enhancement demonstration",
    )
    case_id = ocr_result.case_id
    CleaningService(config).clean_case(case_id)
    results = EnhancementService(config).enhance_case(case_id)

    stats = results[0].correction_statistics
    print(f"\ncase {case_id}: {stats.total_corrections} corrections "
          f"({stats.nepali_corrections} nepali, {stats.english_corrections} "
          f"english), see:")
    print(f"  {config.json_dir / (case_id + '.json')}  (enhancement section)")
    print(f"  {config.storage_dir / 'ocr_corrections.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
