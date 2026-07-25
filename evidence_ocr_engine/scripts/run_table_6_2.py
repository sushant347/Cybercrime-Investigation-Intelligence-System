"""Table 6.2 (Entity Extraction) — regex-only vs. spaCy baseline vs. full pipeline.

Scores each prediction source against the same human gold entity set with
``entity_metrics.entity_prf1`` / ``micro_macro_average``. Numbers only when a
real gold file exists (the ``*_example.json`` worked example is illustrative,
not thesis data).

    python scripts/run_table_6_2.py --gold samples/ground_truth/entities_gold.json

Prediction sources:
  * regex_only  — EntityExtractor.extract() (the deterministic regex layer)
  * spacy       — en_core_web_sm mapped onto the gold vocabulary (NEW optional
                  dependency; skipped with a clear note if spaCy is absent —
                  spaCy is expected to score poorly on domain types like eSewa
                  ids / wallets / OTPs, which is a legitimate finding).
  * full        — the full cleaning pipeline output (storage/entities.csv), if
                  available for the same evidence ids.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.modules.evidence.cleaning.entity_extractor import EntityExtractor  # noqa: E402
from backend.modules.evidence.evaluation.entity_metrics import (  # noqa: E402
    entity_prf1,
    micro_macro_average,
)

# spaCy -> gold-vocabulary mapping (generic NER labels only cover a few types).
_SPACY_LABEL_MAP = {"URL": "urls", "EMAIL": "emails", "MONEY": "money",
                    "DATE": "dates", "TIME": "times", "CARDINAL": None}


def _regex_predictions(texts):
    ex = EntityExtractor()
    out = {}
    for eid, text in texts.items():
        extracted = ex.extract(text or "")
        out[eid] = {t: [e.value for e in items] for t, items in extracted.items() if items}
    return out


def _spacy_predictions(texts):
    try:
        import spacy  # noqa: F401
    except ImportError:
        return None  # signal: dependency absent
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        return None
    out = {}
    for eid, text in texts.items():
        doc = nlp(text or "")
        by_type: dict = {}
        for ent in doc.ents:
            mapped = _SPACY_LABEL_MAP.get(ent.label_)
            if mapped:
                by_type.setdefault(mapped, []).append(ent.text)
        out[eid] = by_type
    return out


def _score(gold: dict, predictions: dict) -> dict:
    per_doc = [entity_prf1(gold.get(eid, {}), predictions.get(eid, {}))
               for eid in gold]
    corpus = micro_macro_average(per_doc)
    return corpus.to_dict() if hasattr(corpus, "to_dict") else {
        "micro": corpus.micro.__dict__, "macro_f1": corpus.macro_f1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Table 6.2 entity evaluation.")
    parser.add_argument("--gold", required=True, help="gold entities JSON (by evidence_id)")
    parser.add_argument("--texts", help="JSON {evidence_id: text} for regex/spaCy; "
                        "defaults to reading raw_text from storage case JSON if omitted")
    args = parser.parse_args()

    gold = {k: v for k, v in json.loads(Path(args.gold).read_text()).items()
            if not k.startswith("_")}
    if not gold:
        print("Gold entity file is empty — provide human-labelled entities. "
              "No numbers are produced from an empty/template gold.")
        return
    if not args.texts:
        print("Provide --texts {evidence_id: text}. (The full-pipeline column is "
              "read from storage/entities.csv via scripts/benchmark_entities.py.)")
        return

    texts = json.loads(Path(args.texts).read_text())
    print("Table 6.2 — Entity extraction (micro P/R/F1, macro-F1)")

    regex = _score(gold, _regex_predictions(texts))
    print("  regex_only:", regex.get("micro"), "macro_f1=", regex.get("macro_f1"))

    spacy_pred = _spacy_predictions(texts)
    if spacy_pred is None:
        print("  spacy:      SKIPPED — spaCy not installed (NEW optional dependency).")
        print("              pip install spacy && python -m spacy download en_core_web_sm")
    else:
        sp = _score(gold, spacy_pred)
        print("  spacy:", sp.get("micro"), "macro_f1=", sp.get("macro_f1"),
              "(expected weak on eSewa/wallet/OTP types)")


if __name__ == "__main__":
    main()
