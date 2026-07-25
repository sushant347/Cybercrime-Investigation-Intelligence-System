"""Auto-scaffold the *structure* of the gold files (a human fills the values).

There is deliberately **no** pipeline that auto-generates the ground-truth
*values* — the whole point of ground truth is that a human decides the correct
answer; deriving it from the engine's own output would be circular and would
make every metric read ~100%.

What CAN be automated is the tedious part: writing the JSON skeleton with all
the ids/paths pre-filled so you only type the transcripts / entities / pairs.
This script does exactly that from the images and cases already present.

    # OCR corpus skeleton from every image in samples/ (fill "reference"):
    python scripts/scaffold_gold.py ocr --images-dir samples --out samples/ground_truth/ocr_corpus.json

    # entity-gold + texts skeletons from an OCR manifest (fill the entity lists):
    python scripts/scaffold_gold.py entities --from-manifest samples/ground_truth/ocr_corpus.json \
        --out-gold samples/ground_truth/entities_gold.json --out-texts samples/ground_truth/texts.json

    # correlation / timeline skeletons for the cases currently in storage:
    python scripts/scaffold_gold.py correlation --out samples/ground_truth/correlation_gold.json
    python scripts/scaffold_gold.py timeline --out samples/ground_truth/timeline_gold.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".pdf"}
_NOTE = ("SCAFFOLD — a human must fill the blank fields with the TRUE values "
         "(ground truth). Empty values are refused by the runners.")


def _write(path: str, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path}")


def scaffold_ocr(images_dir: str, out: str) -> None:
    root = Path(images_dir)
    items = [{"_note": _NOTE}]
    for img in sorted(root.iterdir()):
        if img.suffix.lower() in _IMAGE_EXT:
            items.append({"id": img.stem, "reference": "", "image": f"{root.name}/{img.name}"})
    _write(out, items)
    print(f"  {len(items) - 1} images listed; fill each \"reference\" with the exact visible text.")


def scaffold_entities(manifest: str, out_gold: str, out_texts: str) -> None:
    items = json.loads(Path(manifest).read_text(encoding="utf-8"))
    gold = {"_note": _NOTE}
    texts = {"_note": _NOTE}
    for item in items:
        eid = item.get("id")
        if not eid or eid.startswith("_"):
            continue
        gold[eid] = {}                                  # fill: {"urls": [...], "phones": [...]}
        texts[eid] = item.get("reference", "")          # reuse transcript if present
    _write(out_gold, gold)
    _write(out_texts, texts)
    print("  fill each entity dict with the true entities per type.")


def _storage_cases() -> dict:
    from backend.modules.evidence.config import EvidenceConfig
    cfg = EvidenceConfig.from_env()
    cases: dict = defaultdict(list)
    if cfg.evidence_csv.is_file():
        with open(cfg.evidence_csv, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("case_id") and row.get("evidence_id"):
                    cases[row["case_id"]].append(row["evidence_id"])
    return cases


def scaffold_correlation(out: str) -> None:
    cases = _storage_cases()
    data = {"_note": _NOTE,
            "within_case": {c: {"related_pairs": []} for c in cases},
            "cross_case": {"related_pairs": []}}
    _write(out, data)
    print(f"  {len(cases)} cases listed; add related evidence-id pairs a human judges related.")


def scaffold_timeline(out: str) -> None:
    cases = _storage_cases()
    data = {"_note": _NOTE}
    for case, evidence in cases.items():
        data[case] = {"order": [], "timestamps": {eid: "" for eid in sorted(evidence)}}
    _write(out, data)
    print(f"  {len(cases)} cases listed; fill the true order + true ISO timestamps.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold gold-file structure (human fills values).")
    sub = parser.add_subparsers(dest="kind", required=True)
    p = sub.add_parser("ocr"); p.add_argument("--images-dir", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("entities"); p.add_argument("--from-manifest", required=True)
    p.add_argument("--out-gold", required=True); p.add_argument("--out-texts", required=True)
    p = sub.add_parser("correlation"); p.add_argument("--out", required=True)
    p = sub.add_parser("timeline"); p.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.kind == "ocr":
        scaffold_ocr(args.images_dir, args.out)
    elif args.kind == "entities":
        scaffold_entities(args.from_manifest, args.out_gold, args.out_texts)
    elif args.kind == "correlation":
        scaffold_correlation(args.out)
    elif args.kind == "timeline":
        scaffold_timeline(args.out)


if __name__ == "__main__":
    main()
