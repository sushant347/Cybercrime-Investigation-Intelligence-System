"""Run the real acquisition/OCR pipeline on the bundled multi-file case.

The validation is deliberately non-destructive: all generated case records,
originals, logs, and JSON artifacts live in a temporary directory that is
deleted after the summary is printed. Existing repository storage and sample
files are only read.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.modules.evidence import (  # noqa: E402
    EvidenceConfig,
    EvidencePipeline,
    PaddleOCRService,
)


SAMPLE_FILES = (
    "phishing_email_screenshot.png",
    "scam_sms_screenshot.png",
    "police_scan_report.pdf",
    "whatsapp_chat_export.txt",
    "bank_transactions.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--language",
        default="ne",
        help="PaddleOCR language identifier (default: ne, the project default)",
    )
    args = parser.parse_args()

    samples = ROOT / "samples"
    missing = [name for name in SAMPLE_FILES if not (samples / name).is_file()]
    if missing:
        parser.error(f"missing bundled samples: {', '.join(missing)}")

    original_storage = os.environ.get("EVIDENCE_STORAGE_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="ciis-ocr-validation-") as temp:
            os.environ["EVIDENCE_STORAGE_DIR"] = str(Path(temp) / "storage")
            config = EvidenceConfig.from_env()
            pipeline = EvidencePipeline(
                config,
                PaddleOCRService(config, lang=args.language),
            )

            case_id = ""
            summaries = []
            for index, name in enumerate(SAMPLE_FILES):
                result = pipeline.process_file(
                    samples / name,
                    case_id=case_id or None,
                    case_title=(
                        "Bundled multi-evidence OCR validation" if index == 0 else ""
                    ),
                    notes="read-only bundled sample validation",
                )
                case_id = result.case_id
                summaries.append({
                    "file": name,
                    "evidence_id": result.evidence_id,
                    "pages": len(result.pages),
                    "text_characters": len(result.raw_text),
                    "average_confidence": result.average_confidence,
                    "hash_verified": result.hash_verified,
                    "ocr_engine": result.ocr_engine,
                })

            valid = (
                len(summaries) == len(SAMPLE_FILES)
                and len({item["evidence_id"] for item in summaries}) == len(summaries)
                and all(item["hash_verified"] for item in summaries)
                and all(item["text_characters"] > 0 for item in summaries)
            )
            print(json.dumps({
                "valid": valid,
                "case_id": case_id,
                "evidence_count": len(summaries),
                "temporary_storage": temp,
                "evidence": summaries,
            }, indent=2))
            return 0 if valid else 1
    finally:
        if original_storage is None:
            os.environ.pop("EVIDENCE_STORAGE_DIR", None)
        else:
            os.environ["EVIDENCE_STORAGE_DIR"] = original_storage


if __name__ == "__main__":
    raise SystemExit(main())
