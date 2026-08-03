"""Table 6.5 (Timeline) — score the LIVE timeline service vs. gold.

Runs ``ciis_correlation/timeline/service.py``, the production
adapter for ``timeline_reconstruction/``, and reports order accuracy + timestamp
accuracy + unresolved rate against human gold, plus the naive upload-time-order
baseline. Numbers only when real gold exists.

    python scripts/run_table_6_5.py --gold samples/ground_truth/timeline_gold.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importing the package puts the upstream OCR engine on sys.path, so it must
# come before any ``backend.modules.evidence`` import. Keep it in this block -
# an import sorter would otherwise file it after ``backend`` and break startup.
import ciis_correlation  # noqa: E402,F401  (bootstraps the OCR engine root)

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from ciis_correlation.core.audit import InvestigationAuditTrail  # noqa: E402
from ciis_correlation.core.config import InvestigationConfig  # noqa: E402
from ciis_correlation.core.data_access import CaseDataRepository  # noqa: E402
from ciis_correlation.evaluation.gold_labels import load_timeline_gold  # noqa: E402
from ciis_correlation.evaluation.timeline_eval import (  # noqa: E402
    evaluate_timeline,
    evaluate_timestamp_accuracy,
    predicted_order,
    predicted_timestamps,
)
from ciis_correlation.core.repository import InvestigationReportRepository  # noqa: E402
from ciis_correlation.timeline.service import TimelineService  # noqa: E402


def _services():
    ecfg = EvidenceConfig.from_env()
    icfg = InvestigationConfig.from_env(ecfg)
    icfg.ensure_directories()
    data = CaseDataRepository(icfg)
    repo = InvestigationReportRepository(icfg)
    audit = InvestigationAuditTrail(icfg)
    return data, TimelineService(icfg, data, repo, audit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Table 6.5 timeline evaluation.")
    parser.add_argument("--gold", required=True, help="timeline gold JSON")
    args = parser.parse_args()

    gold = load_timeline_gold(args.gold)
    if gold.is_template():
        print("Gold labels are empty (this is the template).")
        print("Fill 'order' and 'timestamps' in", args.gold, "then re-run.")
        print("No numbers are produced from a template.")
        return

    data, timeline = _services()
    print("Table 6.5 — Timeline (live four-tier engine vs. upload-time baseline)")

    for case_id, gold_order in gold.order.items():
        if not data.case_exists(case_id):
            print(f"{case_id}: no evidence in storage — skipped")
            continue
        evidence = data.load_case_evidence(case_id)
        analysis = timeline.analyze(case_id, evidence, persist=False)

        live_order = predicted_order(analysis)
        upload_order = [c.evidence_id for c in
                        sorted(evidence, key=lambda c: c.upload_time or "")]
        gold_ts = gold.timestamps.get(case_id, {})

        live_ord = evaluate_timeline(gold_order, live_order).to_dict()
        base_ord = evaluate_timeline(gold_order, upload_order).to_dict()
        live_ts = evaluate_timestamp_accuracy(gold_ts, predicted_timestamps(analysis)).to_dict()

        print(f"\n{case_id}:")
        print(f"  order accuracy   live={live_ord['pairwise_accuracy']}  "
              f"upload-baseline={base_ord['pairwise_accuracy']}")
        print(f"  timestamp accuracy (live): MAE={live_ts['mae_seconds']}s  "
              f"median={live_ts['median_ae_seconds']}s  "
              f"within<=60s={live_ts['within_tolerance'].get('<= 60s')}  "
              f"unresolved_rate={live_ts['unresolved_rate']}")


if __name__ == "__main__":
    main()
