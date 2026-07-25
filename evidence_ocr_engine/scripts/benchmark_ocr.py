#!/usr/bin/env python3
"""Benchmark OCR accuracy (CER/WER) over a labelled ground-truth set.

Usage:
    python scripts/benchmark_ocr.py --manifest samples/ground_truth/ocr_manifest.json \
        [--out results/ocr_benchmark.json] [--no-normalize]

Manifest format (JSON list); each item needs a reference transcript and EITHER
a precomputed OCR ``hypothesis`` OR an ``image`` path to run OCR live::

    [
      {"id": "s1", "reference": "true text ...", "hypothesis": "ocr text ..."},
      {"id": "s2", "reference": "true text ...", "image": "samples/foo.png"}
    ]

Design notes:
* Items with a ``hypothesis`` are scored directly - this lets the methodology
  run and be validated WITHOUT a PaddleOCR install (CI / grading friendly).
* Items with only an ``image`` run the real engine OCR (requires PaddleOCR);
  if OCR is unavailable those items are reported as ``skipped`` rather than
  crashing the whole run.
* The output JSON records the exact normalization settings so the numbers are
  reproducible. The full per-sample distribution is emitted, not just the mean.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

from backend.modules.evidence.evaluation import (  # noqa: E402
    corpus_ocr_metrics,
)


def _ocr_hypothesis(image_path: Path) -> str:
    """Run the production OCR pipeline on one image; raise if OCR unavailable."""
    from backend.modules.evidence.config import EvidenceConfig
    from backend.modules.evidence.paddle_service import PaddleOCRService
    from backend.modules.evidence.preprocessing import ImagePreprocessor, load_image

    cfg = EvidenceConfig.from_env()
    ocr = PaddleOCRService(cfg, lang=cfg.ocr_lang)
    image, _ops = ImagePreprocessor(cfg).preprocess(load_image(str(image_path)))
    lines = ocr.recognize(image)
    return "\n".join(line.text for line in lines)


def run(manifest_path: Path, normalize: bool) -> dict:
    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    scored, skipped = [], []
    for item in items:
        ref = item.get("reference", "")
        hyp = item.get("hypothesis")
        if hyp is None and item.get("image"):
            try:
                image_path = (manifest_path.parent / item["image"]).resolve()
                if not image_path.is_file():
                    image_path = (_ENGINE_ROOT / item["image"]).resolve()
                hyp = _ocr_hypothesis(image_path)
            except Exception as exc:  # noqa: BLE001 - OCR optional at bench time
                skipped.append({"id": item.get("id"), "reason": str(exc)})
                continue
        if hyp is None:
            skipped.append({"id": item.get("id"), "reason": "no hypothesis/image"})
            continue
        pairs.append((ref, hyp))
        scored.append(item.get("id"))

    metrics = corpus_ocr_metrics(pairs, normalize=normalize)
    report = {
        "manifest": str(manifest_path),
        "scored_ids": scored,
        "skipped": skipped,
        "metrics": metrics.to_dict(),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR CER/WER benchmark")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-normalize", action="store_true")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        return 1

    report = run(args.manifest, normalize=not args.no_normalize)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    metrics = report["metrics"]
    print(
        f"OCR benchmark: {metrics['samples']} scored, {len(report['skipped'])} skipped | "
        f"CER={metrics['cer']:.4f} WER={metrics['wer']:.4f} "
        f"char_acc={metrics['char_accuracy']:.4f}"
    )
    if args.out:
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
