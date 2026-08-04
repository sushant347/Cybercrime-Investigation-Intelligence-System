"""Re-extract entities and rebuild the cross-case index for every case.

Run this after an entity-normalization rule changes (for example when money
normalization was introduced: previously-stored cases still carry raw values
like ``rs 2,000`` / ``rs 2000`` in ``entities.csv`` and in the cross-case
index, so identical amounts sit in different buckets and never match).

For each known case this script:

  1. re-runs the post-OCR chain (cleaning -> enhancement -> semantic) from
     the stored raw text — no OCR, no originals needed — which rewrites the
     case's rows in ``entities.csv`` with current normalization;
  2. re-indexes the case into the cross-case entity index (the service drops
     the case's stale slice first);
  3. refreshes the live correlation / cross-case / timeline / graph artifacts.

Reports are NOT regenerated (run a full case analysis from the app for that).

Usage (from the repo root, inside the platform venv)::

    ./.venv-platform/bin/python evidence_ocr_engine/reindex_entities.py
    # or on Windows Git Bash:
    ./.venv-platform/Scripts/python.exe evidence_ocr_engine/reindex_entities.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Importing the package puts the upstream OCR engine on sys.path, so it must
# come before any ``backend.modules.evidence`` import. Keep it in this block -
# an import sorter would otherwise file it after ``backend`` and break startup.
import ciis_timeline_report  # noqa: E402,F401  (chains the upstream bootstraps)

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from backend.modules.evidence.semantic.orchestrator import (  # noqa: E402
    EvidenceProcessingOrchestrator,
)
from ciis_timeline_report.pipeline import build_default_pipeline  # noqa: E402
from ciis_correlation.core.text import count_of


def main() -> int:
    ecfg = EvidenceConfig()
    if not ecfg.cases_csv.is_file():
        print("No cases.csv - nothing to do.")
        return 0

    import csv

    with open(ecfg.cases_csv, encoding="utf-8") as handle:
        case_ids = [row["case_id"] for row in csv.DictReader(handle)]
    print(f"{count_of(len(case_ids), 'case')}: {', '.join(case_ids)}")

    orchestrator = EvidenceProcessingOrchestrator(ecfg)
    pipeline = build_default_pipeline()

    # Pass 1: re-extract + re-index EVERY case before refreshing any artifact,
    # otherwise the first case's cross-case artifact is computed against the
    # other cases' still-stale index entries and shows too few links.
    failures = 0
    processed: list[str] = []
    for case_id in case_ids:
        print(f"\n== {case_id} (re-extract)")
        try:
            summary = orchestrator.process_case(case_id)
            print(f"   re-extracted entities for "
                  f"{count_of(summary['stages'].get('cleaning', 0), 'evidence item')}")
            processed.append(case_id)
        except Exception as exc:  # noqa: BLE001 - continue with other cases
            # Typical benign cause: a case created in the app but with no
            # successfully processed evidence yet (no JSON document).
            print(f"   -- skipped: {exc}")

    # Pass 2: refresh artifacts. refresh_timeline_graph re-indexes the case
    # (idempotent) and recomputes correlation, cross-case, timeline and graph.
    for case_id in processed:
        print(f"\n== {case_id} (refresh artifacts)")
        try:
            refreshed = pipeline.refresh_timeline_graph(case_id)
            cross = refreshed["cross_case"]
            print(f"   {count_of(cross.link_count, 'cross-case link')} "
                  f"-> {', '.join(cross.related_case_ids) or 'none'}")
        except Exception as exc:  # noqa: BLE001
            print(f"   !! artifact refresh failed: {exc}")
            failures += 1

    print(f"\nDone. failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
