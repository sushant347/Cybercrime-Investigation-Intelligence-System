"""Table 6.4 (Correlation) — score the LIVE correlation service vs. gold.

Runs ``ciis_correlation/correlation/service.py`` (NOT the
deprecated ``evidence_correlation_engine/``) on real case evidence and scores
its related-pairs against human gold labels, alongside two baselines
(exact-match, unweighted). Produces numbers ONLY when real gold labels exist;
against the unfilled template it stops and tells you what to provide.

    python scripts/run_table_6_4.py --gold samples/ground_truth/correlation_gold.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make 'backend' importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importing the package puts the upstream OCR engine on sys.path, so it must
# come before any ``backend.modules.evidence`` import. Keep it in this block -
# an import sorter would otherwise file it after ``backend`` and break startup.
import ciis_correlation  # noqa: E402,F401  (bootstraps the OCR engine root)

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from ciis_correlation.core.audit import InvestigationAuditTrail  # noqa: E402
from ciis_correlation.core.config import InvestigationConfig  # noqa: E402
from ciis_correlation.correlation.service import CorrelationService  # noqa: E402
from ciis_correlation.core.data_access import CaseDataRepository  # noqa: E402
from ciis_correlation.evaluation.correlation_baselines import (  # noqa: E402
    exact_match_pairs,
    unweighted_shared_entity_pairs,
)
from ciis_correlation.evaluation.correlation_eval import (  # noqa: E402
    evaluate_correlation,
    predicted_related_pairs,
)
from ciis_correlation.evaluation.gold_labels import (  # noqa: E402
    load_correlation_gold,
)
from ciis_correlation.core.repository import InvestigationReportRepository  # noqa: E402


def _services():
    ecfg = EvidenceConfig.from_env()
    icfg = InvestigationConfig.from_env(ecfg)
    icfg.ensure_directories()
    data = CaseDataRepository(icfg)
    repo = InvestigationReportRepository(icfg)
    audit = InvestigationAuditTrail(icfg)
    return icfg, data, CorrelationService(icfg, data, repo, audit)


def _provenance_banner(gold) -> None:
    """Stamp demo-sourced numbers so they cannot be quoted as measurements."""
    if not getattr(gold, "illustrative", False):
        return
    line = "=" * 74
    print(line)
    print("  ILLUSTRATIVE GOLD - THESE NUMBERS ARE NOT A MEASUREMENT")
    print("  The gold file declares itself demo data. It exists so this")
    print("  harness runs end to end, not to evaluate the engine. Replace it")
    print("  with human-verified labels before quoting any figure below.")
    print(line)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Table 6.4 correlation evaluation.")
    parser.add_argument("--gold", required=True, help="correlation gold JSON")
    args = parser.parse_args()

    gold = load_correlation_gold(args.gold)
    if gold.is_template():
        print("Gold labels are empty (this is the template).")
        print("Fill related_pairs in", args.gold, "with human-judged related")
        print("evidence-id pairs, then re-run. No numbers are produced from a")
        print("template — that would be fabrication.")
        return

    _provenance_banner(gold)

    icfg, data, correlation = _services()
    header = f"{'Case':<16}{'Method':<22}{'Prec':>8}{'Rec':>8}{'F1':>8}{'TP':>5}{'FP':>5}{'FN':>5}"
    print("Table 6.4 — Correlation (live weighted engine vs. baselines)")
    print("\n[WITHIN-CASE]")
    print(header); print("-" * len(header))

    labelled = [c for c in gold.within_case if data.case_exists(c)]
    for case_id in gold.within_case:
        gold_pairs = gold.within_case[case_id]
        if not data.case_exists(case_id):
            print(f"{case_id:<16}(no evidence in storage — skipped)")
            continue
        evidence = data.load_case_evidence(case_id)
        analysis = correlation.analyze_case(case_id, evidence, persist=False)
        methods = {
            "live_weighted": predicted_related_pairs(analysis),
            "exact_match": exact_match_pairs(evidence),
            "unweighted_shared": unweighted_shared_entity_pairs(evidence, icfg),
        }
        for name, pred in methods.items():
            ev = evaluate_correlation(gold_pairs, pred).to_dict()
            print(f"{case_id:<16}{name:<22}{ev['precision']:>8}{ev['recall']:>8}"
                  f"{ev['f1']:>8}{ev['tp']:>5}{ev['fp']:>5}{ev['fn']:>5}")

    # ---- Cross-case: score linked evidence pairs ACROSS cases against gold ----
    if gold.cross_case:
        print("\n[CROSS-CASE]")
        # Index every labelled case first so the shared-entity index is current.
        for case_id in labelled:
            correlation.index_case_entities(case_id, data.load_case_evidence(case_id))
        predicted: set = set()
        for case_id in labelled:
            cc = correlation.correlate_cross_case(case_id, data.load_case_evidence(case_id))
            for link in cc.links:
                for match in link.matched_entities:
                    for a in match.this_evidence_ids:
                        for b in match.other_evidence_ids:
                            predicted.add((a, b))
        ev = evaluate_correlation(gold.cross_case, predicted).to_dict()
        print(header); print("-" * len(header))
        print(f"{'ALL CASES':<16}{'live_cross_case':<22}{ev['precision']:>8}"
              f"{ev['recall']:>8}{ev['f1']:>8}{ev['tp']:>5}{ev['fp']:>5}{ev['fn']:>5}")


if __name__ == "__main__":
    main()
