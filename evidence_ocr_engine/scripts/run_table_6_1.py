"""Table 6.1 (OCR) — CER / WER / entity-preservation across the 3 pipeline stages.

For each corpus image, runs the three stages that map onto the table's rows and
scores each against the human transcript:

  * Raw                    — PaddleOCRService.recognize() (+ ImagePreprocessor)
  * + Preprocessing        — CleaningPipeline.clean().cleaned_text
  * + Confidence-gated      — EnhancementPipeline.enhance().enhanced_text
    correction

Produces numbers ONLY from a real, human-annotated manifest (30-100 samples,
English + Nepali/Devanagari). The bundled ``ocr_manifest_example.json`` is a
worked example whose numbers are illustrative, not thesis data — the script
refuses to treat it as the corpus unless you pass --allow-example.

    python scripts/run_table_6_1.py --manifest samples/ground_truth/ocr_corpus.json \
        --gold-entities samples/ground_truth/entities_gold.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.modules.evidence.evaluation.ocr_metrics import (  # noqa: E402
    corpus_ocr_metrics,
    entity_preservation_rate,
)

_ENGINE_ROOT = Path(__file__).resolve().parents[1]


def _stages(image_path: Path) -> dict:
    """Return {'raw':..., 'preprocessed':..., 'enhanced':...} text for one image."""
    from backend.modules.evidence.cleaning.cleaning_pipeline import CleaningPipeline
    from backend.modules.evidence.config import EvidenceConfig
    from backend.modules.evidence.enhancement.enhancement_pipeline import EnhancementPipeline
    from backend.modules.evidence.paddle_service import PaddleOCRService
    from backend.modules.evidence.preprocessing import ImagePreprocessor, load_image

    cfg = EvidenceConfig.from_env()
    ocr = PaddleOCRService(cfg, lang=cfg.ocr_lang)
    image = ImagePreprocessor(cfg).process(load_image(str(image_path)))
    raw = "\n".join(line.text for line in ocr.recognize(image))
    cleaned = CleaningPipeline(cfg).clean(raw).cleaned_text
    enhanced = EnhancementPipeline(cfg).enhance(cleaned).enhanced_text
    return {"raw": raw, "preprocessed": cleaned, "enhanced": enhanced}


def main() -> None:
    parser = argparse.ArgumentParser(description="Table 6.1 OCR evaluation (3 stages).")
    parser.add_argument("--manifest", required=True,
                        help="[{id, reference, image}] JSON")
    parser.add_argument("--gold-entities",
                        help="optional {id: [entity strings]} for preservation-%")
    parser.add_argument("--allow-example", action="store_true",
                        help="permit the illustrative example manifest")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if manifest_path.name.endswith("_example.json") and not args.allow_example:
        print("Refusing to report the *_example manifest as a result — its numbers")
        print("are illustrative only. Build a real 30-100 sample bilingual corpus")
        print("(see samples/ground_truth/README.md), or pass --allow-example to")
        print("smoke-test the harness.")
        return

    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    gold_entities = (json.loads(Path(args.gold_entities).read_text())
                     if args.gold_entities else {})

    # stage -> list of (reference, hypothesis); and per-stage preservation rates.
    stage_pairs = {"raw": [], "preprocessed": [], "enhanced": []}
    stage_pres = {"raw": [], "preprocessed": [], "enhanced": []}
    skipped = []
    for item in items:
        ref = item.get("reference", "")
        if not item.get("image"):
            skipped.append({"id": item.get("id"), "reason": "no image"})
            continue
        image_path = (manifest_path.parent / item["image"]).resolve()
        if not image_path.is_file():
            image_path = (_ENGINE_ROOT / item["image"]).resolve()
        try:
            texts = _stages(image_path)
        except Exception as exc:  # noqa: BLE001 - OCR optional / heavy
            skipped.append({"id": item.get("id"), "reason": str(exc)})
            continue
        gold_ents = gold_entities.get(str(item.get("id")), [])
        for stage, hyp in texts.items():
            stage_pairs[stage].append((ref, hyp))
            if gold_ents:
                stage_pres[stage].append(
                    entity_preservation_rate(gold_ents, hyp)["rate"])

    print("Table 6.1 — OCR accuracy by pipeline stage")
    print(f"{'Stage':<24}{'CER':>8}{'WER':>8}{'CharAcc':>9}{'EntPres%':>10}{'n':>5}")
    print("-" * 64)
    for stage, label in (("raw", "Raw"),
                         ("preprocessed", "+ Preprocessing"),
                         ("enhanced", "+ Correction")):
        pairs = stage_pairs[stage]
        if not pairs:
            continue
        m = corpus_ocr_metrics(pairs).to_dict()
        pres = stage_pres[stage]
        pres_pct = round(100 * sum(pres) / len(pres), 1) if pres else "—"
        print(f"{label:<24}{m['cer']:>8}{m['wer']:>8}{m['char_accuracy']:>9}"
              f"{str(pres_pct):>10}{m['samples']:>5}")
    if skipped:
        print(f"\nskipped {len(skipped)}: {skipped[:5]}{' ...' if len(skipped) > 5 else ''}")


if __name__ == "__main__":
    main()
