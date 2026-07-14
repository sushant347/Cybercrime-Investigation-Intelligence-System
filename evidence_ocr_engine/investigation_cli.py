#!/usr/bin/env python3
"""CIIS Phase-2 investigation CLI (additive - existing CLIs untouched).

Usage:
    python investigation_cli.py analyze <CASE_ID>     # run all 8 modules
    python investigation_cli.py analyze --all         # every known case
    python investigation_cli.py priority <CASE_ID>    # show case priority
    python investigation_cli.py report <CASE_ID>      # print latest MD report
"""

from __future__ import annotations

import argparse
import sys

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.utils import EvidenceError
from backend.modules.investigation.config import InvestigationConfig
from backend.modules.investigation.pipeline import build_default_pipeline
from backend.modules.investigation.repository import InvestigationReportRepository


def cmd_analyze(args: argparse.Namespace) -> int:
    pipeline = build_default_pipeline()
    case_ids = None
    if args.all:
        results = pipeline.analyze_all_cases()
    elif args.case_id:
        results = {args.case_id: pipeline.analyze_case(args.case_id)}
    else:
        print("error: provide a CASE_ID or --all", file=sys.stderr)
        return 2
    for case_id, outcome in results.items():
        priority = outcome.get("priority")
        line = f"{case_id}: "
        if priority is not None:
            line += (f"priority {priority.priority_score}/100 "
                     f"({priority.priority_level})")
        failures = outcome.get("failures") or []
        if failures:
            line += f"  [failures: {', '.join(failures)}]"
        print(line)
    return 0


def cmd_priority(args: argparse.Namespace) -> int:
    icfg = InvestigationConfig.from_env(EvidenceConfig.from_env())
    repo = InvestigationReportRepository(icfg)
    document = repo.load_latest(args.case_id, icfg.priority_report_name)
    if document is None:
        print(f"No priority stored for '{args.case_id}'. Run analyze first.")
        return 1
    report = document["report"]
    print(f"{args.case_id}: {report['priority_score']}/100 "
          f"({report['priority_level']})")
    print(report["explanation"])
    for indicator in report.get("high_risk_indicators", []):
        print(f"  ! {indicator}")
    print(report.get("investigation_recommendation", ""))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    icfg = InvestigationConfig.from_env(EvidenceConfig.from_env())
    repo = InvestigationReportRepository(icfg)
    versions = repo.list_versions(args.case_id, icfg.investigation_report_name, ".md")
    if not versions:
        print(f"No investigation report stored for '{args.case_id}'.")
        return 1
    print(versions[-1].read_text(encoding="utf-8"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CIIS Phase-2 investigation")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="run all Phase-2 modules for a case")
    p.add_argument("case_id", nargs="?", default=None)
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("priority", help="show stored case priority")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_priority)

    p = sub.add_parser("report", help="print latest investigation report")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
