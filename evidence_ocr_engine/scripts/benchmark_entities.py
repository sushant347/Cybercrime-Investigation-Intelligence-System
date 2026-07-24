#!/usr/bin/env python3
"""Benchmark entity-extraction accuracy (Precision/Recall/F1) vs a gold set.

Usage:
    python scripts/benchmark_entities.py \
        --gold samples/ground_truth/entities_gold.json \
        [--predicted storage/entities.csv] [--out results/entity_benchmark.json]

Gold format (JSON): mapping ``evidence_id -> {entity_type: [values...]}``::

    {
      "EVID_00001": {"urls": ["http://x"], "emails": ["a@b.com"]},
      "EVID_00002": {"phones": ["+9779800000000"]}
    }

Predictions come from the engine's ``storage/entities.csv`` (columns
``case_id,evidence_id,entity_type,value,normalized,...``) by default, so this
scores the SAME entities the live pipeline produced. Alternatively pass a JSON
predictions file in the gold format.

Scores are reported per evidence item, then aggregated micro + macro across the
corpus (see ``evaluation/entity_metrics.py``). The matching normalization rule
is recorded in the output.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

from backend.modules.evidence.evaluation import (  # noqa: E402
    entity_prf1,
    micro_macro_average,
)


def _load_predictions_csv(path: Path) -> dict[str, dict[str, list[str]]]:
    preds: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            eid = row.get("evidence_id", "")
            etype = row.get("entity_type", "")
            value = row.get("value") or row.get("normalized") or ""
            if eid and etype and value:
                preds[eid][etype].append(value)
    return {k: dict(v) for k, v in preds.items()}


def _load_predictions_json(path: Path) -> dict[str, dict[str, list[str]]]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(gold_path: Path, predicted_path: Path) -> dict:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    if predicted_path.suffix == ".json":
        predicted = _load_predictions_json(predicted_path)
    else:
        predicted = _load_predictions_csv(predicted_path)

    per_item = {}
    scores = []
    for evidence_id, gold_entities in gold.items():
        pred_entities = predicted.get(evidence_id, {})
        score = entity_prf1(gold_entities, pred_entities)
        per_item[evidence_id] = score.to_dict()
        scores.append(score)

    corpus = micro_macro_average(scores)
    return {
        "gold": str(gold_path),
        "predicted": str(predicted_path),
        "n_items": len(gold),
        "per_item": per_item,
        "corpus": corpus.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Entity P/R/F1 benchmark")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument(
        "--predicted", type=Path, default=_ENGINE_ROOT / "storage" / "entities.csv"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.gold.is_file():
        print(f"ERROR: gold set not found: {args.gold}", file=sys.stderr)
        return 1
    if not args.predicted.is_file():
        print(f"ERROR: predictions not found: {args.predicted}", file=sys.stderr)
        return 1

    report = run(args.gold, args.predicted)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    micro = report["corpus"]["micro"]
    print(
        f"Entity benchmark: {report['n_items']} items | "
        f"micro P={micro['precision']:.4f} R={micro['recall']:.4f} F1={micro['f1']:.4f} | "
        f"macro F1={report['corpus']['macro_f1']:.4f}"
    )
    if args.out:
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
