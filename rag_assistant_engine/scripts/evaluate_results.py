"""Calculate retrieval/citation metrics from a human-labelled result file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from ciis_rag.evaluation import citation_metrics, retrieval_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", help="JSON with a queries array")
    args = parser.parse_args()
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    expected = {
        row["id"]: set(row.get("expected_evidence_ids", []))
        for row in data.get("queries", [])
    }
    retrieved = {
        row["id"]: list(row.get("retrieved_evidence_ids", []))
        for row in data.get("queries", [])
    }
    citations_expected = set().union(*expected.values()) if expected else set()
    citations_predicted = set().union(*(
        set(row.get("cited_evidence_ids", [])) for row in data.get("queries", [])
    )) if data.get("queries") else set()
    print(json.dumps({
        "retrieval": retrieval_metrics(expected, retrieved),
        "citations": citation_metrics(citations_expected, citations_predicted),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
