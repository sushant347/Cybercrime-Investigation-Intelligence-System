"""Table 6.7 (report-correctness row) — human-review harness.

Report correctness cannot be computed by code: it needs a human to grade
generated reports against the source evidence. This harness makes that review
*structured and reproducible* rather than ad hoc:

  --case <ID>   builds a review checklist from a real stored report (each
                checkable claim + the evidence to check it against), written as
                a JSON template with blank "verdict" fields.
  --score <f>   once a human has filled the verdicts, computes the
                report-correctness rate.

It never invents a score — an unfilled template scores nothing until a human
marks the verdicts. Run over 10-20 reports to get the table's number.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VERDICTS = {"correct", "incorrect", "partial", ""}


def build_review_template(report_doc: Dict, evidence_rows: List[Dict]) -> Dict:
    """Turn a stored investigation report into a blank human-review checklist."""
    sections = report_doc.get("report", {}).get("sections", {})
    items: List[Dict] = []

    def add(claim_id: str, claim: str):
        items.append({"id": claim_id, "claim": claim, "verdict": "", "note": ""})

    for i, line in enumerate(sections.get("executive_summary", []) or []):
        add(f"exec_{i}", line)
    for i, line in enumerate(sections.get("investigation_conclusion", []) or []):
        add(f"concl_{i}", line)
    for i, line in enumerate(sections.get("recommendations", []) or []):
        add(f"rec_{i}", line)

    return {
        "case_id": report_doc.get("case_id", ""),
        "report_version": report_doc.get("report_version"),
        "evidence_reviewed": [r.get("evidence_id") for r in evidence_rows],
        "instructions": ("Grade each claim against the source evidence: set "
                         "'verdict' to correct | incorrect | partial."),
        "items": items,
    }


def score_review(filled: Dict) -> Dict:
    """Compute report-correctness from a human-filled review template."""
    items = filled.get("items", [])
    graded = [it for it in items if it.get("verdict") in {"correct", "incorrect", "partial"}]
    if not graded:
        raise ValueError("no items graded yet — fill 'verdict' fields first")
    weights = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
    score = sum(weights[it["verdict"]] for it in graded)
    return {
        "case_id": filled.get("case_id", ""),
        "graded_items": len(graded),
        "ungraded_items": len(items) - len(graded),
        "correctness_rate": round(score / len(graded), 4),
        "breakdown": {v: sum(1 for it in graded if it["verdict"] == v)
                      for v in ("correct", "partial", "incorrect")},
    }


def _load_case(case_id: str):
    from backend.modules.evidence.config import EvidenceConfig
    from backend.modules.investigation.config import InvestigationConfig
    from backend.modules.investigation.repository import InvestigationReportRepository

    ecfg = EvidenceConfig.from_env()
    icfg = InvestigationConfig.from_env(ecfg)
    repo = InvestigationReportRepository(icfg)
    report = repo.load_latest(case_id, icfg.investigation_report_name)
    import csv
    rows = []
    if ecfg.evidence_csv.is_file():
        with open(ecfg.evidence_csv, encoding="utf-8") as h:
            rows = [r for r in csv.DictReader(h) if r.get("case_id") == case_id]
    return report, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-correctness review harness.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", help="build a review template from a stored report")
    group.add_argument("--score", help="score a filled review template JSON")
    parser.add_argument("--out", help="write the template here (with --case)")
    args = parser.parse_args()

    if args.score:
        filled = json.loads(Path(args.score).read_text(encoding="utf-8"))
        print(json.dumps(score_review(filled), indent=2))
        return

    report, rows = _load_case(args.case)
    if report is None:
        print(f"No investigation report stored for {args.case}. Run the analysis first.")
        return
    template = build_review_template(report, rows)
    text = json.dumps(template, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Wrote review template ({len(template['items'])} claims) -> {args.out}")
        print("Fill each 'verdict', then: report_review.py --score <file>")
    else:
        print(text)


if __name__ == "__main__":
    main()
