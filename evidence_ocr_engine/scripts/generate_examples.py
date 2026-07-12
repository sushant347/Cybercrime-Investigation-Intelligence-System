"""Generate sample evidence files and example outputs for the repository.

Runs the real acquisition pipeline end-to-end with a deterministic stub OCR
engine so the repository ships with reproducible example CSV/JSON outputs on
machines where PaddleOCR is not installed. With PaddleOCR installed, pass
``--paddle`` to produce genuine OCR output instead.

Usage::

    python scripts/generate_examples.py            # stub OCR engine
    python scripts/generate_examples.py --paddle   # real PaddleOCR 3.x
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.modules.evidence import (  # noqa: E402
    BaseOCR,
    EvidenceConfig,
    EvidencePipeline,
)
from backend.modules.evidence.models import OCRLine  # noqa: E402

SAMPLES = ROOT / "samples"

PHISHING_LINES = [
    "From: security@nabil-bank-alerts.com",
    "Subject: URGENT - Your account has been suspended",
    "Dear customer, unusual activity was detected.",
    "Verify now: http://nabil-verify.example-scam.top/login",
    "Failure to verify within 24 hours locks your account.",
]

SMS_LINES = [
    "eSewa Alert: You won Rs 5,00,000 lottery!",
    "Send Rs 2,000 processing fee to ID 98XXXXXXXX",
    "Claim code: ESW-2026-77413",
]


class DemoStubOCR(BaseOCR):
    """Deterministic stand-in used ONLY to generate repository examples.

    Returns the exact text rendered into the sample images, with plausible
    confidences and bounding boxes, so example outputs are realistic and
    reproducible without downloading PaddleOCR models.
    """

    name = "demo-stub (BaseOCR reference implementation)"

    def __init__(self) -> None:
        self._queue: List[List[str]] = []

    def enqueue(self, lines: List[str]) -> None:
        self._queue.append(lines)

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        texts = self._queue.pop(0) if self._queue else ["(no queued text)"]
        rng = np.random.default_rng(seed=len(texts))
        lines: List[OCRLine] = []
        for index, text in enumerate(texts):
            y0 = 24.0 + index * 34.0
            width = 12.0 * len(text)
            lines.append(
                OCRLine(
                    text=text,
                    confidence=round(float(0.90 + rng.random() * 0.09), 4),
                    bbox=[[16.0, y0], [16.0 + width, y0],
                          [16.0 + width, y0 + 26.0], [16.0, y0 + 26.0]],
                )
            )
        return lines


def _make_image(path: Path, title: str, lines: List[str], size=(760, 260)) -> None:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size[0], 34], fill=(25, 60, 130))
    draw.text((14, 10), title, fill="white")
    for index, line in enumerate(lines):
        draw.text((16, 54 + index * 34), line, fill="black")
    img.save(path)


def _make_pdf(path: Path) -> List[List[str]]:
    import fitz

    page_texts = [
        ["POLICE REPORT - CYBER BUREAU", "Complaint No: CB-2026-0142",
         "Victim reports fraudulent bank transfer of Rs 250,000."],
        ["ANNEX A - TRANSACTION TRACE", "Beneficiary account: 0071-XXXX-9912",
         "Transfer executed via compromised mobile banking session."],
    ]
    doc = fitz.open()
    for texts in page_texts:
        page = doc.new_page()
        for index, text in enumerate(texts):
            page.insert_text((72, 100 + index * 40), text, fontsize=14)
    doc.save(str(path))
    doc.close()
    return page_texts


def build_samples() -> dict:
    SAMPLES.mkdir(exist_ok=True)
    _make_image(SAMPLES / "phishing_email_screenshot.png",
                "Nabil Bank - Secure Message", PHISHING_LINES)
    _make_image(SAMPLES / "scam_sms_screenshot.png",
                "Messages", SMS_LINES, size=(680, 220))
    (SAMPLES / "whatsapp_chat_export.txt").write_text(
        "[2026-01-04 09:12] +977-98XXXXXXXX: Congratulations! tapaile lottery jitnu bhayo\n"
        "[2026-01-04 09:12] +977-98XXXXXXXX: पैसा पाउन Rs 2000 पठाउनुहोस्\n"
        "[2026-01-04 09:14] Victim: k ho yo? कसरी?\n"
        "[2026-01-04 09:15] +977-98XXXXXXXX: esewa id 98XXXXXXXX ma send garnus\n",
        encoding="utf-8",
    )
    (SAMPLES / "bank_transactions.csv").write_text(
        "date,description,amount_npr,channel\n"
        "2026-01-04,IBFT transfer to 0071-XXXX-9912,-250000,mobile_banking\n"
        "2026-01-04,Balance inquiry,0,mobile_banking\n"
        "2026-01-03,Salary credit,85000,branch\n",
        encoding="utf-8",
    )
    pdf_pages = _make_pdf(SAMPLES / "police_scan_report.pdf")
    return {"pdf_pages": pdf_pages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paddle", action="store_true",
                        help="use real PaddleOCR instead of the demo stub")
    args = parser.parse_args()

    meta = build_samples()
    config = EvidenceConfig.from_env()

    if args.paddle:
        from backend.modules.evidence import PaddleOCRService
        engine: BaseOCR = PaddleOCRService(config)
    else:
        stub = DemoStubOCR()
        stub.enqueue(PHISHING_LINES)
        stub.enqueue(SMS_LINES)
        for page in meta["pdf_pages"]:
            stub.enqueue(page)
        engine = stub

    pipeline = EvidencePipeline(config, engine)
    result = pipeline.process_file(
        SAMPLES / "phishing_email_screenshot.png",
        case_title="Demo: bank phishing investigation",
        notes="sample evidence shipped with the repository",
    )
    case_id = result.case_id
    for name in ("scam_sms_screenshot.png", "police_scan_report.pdf",
                 "whatsapp_chat_export.txt", "bank_transactions.csv"):
        pipeline.process_file(SAMPLES / name, case_id=case_id)

    print(f"\nExamples generated under {config.storage_dir} (case {case_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
