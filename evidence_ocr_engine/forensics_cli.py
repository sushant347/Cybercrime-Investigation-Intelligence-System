#!/usr/bin/env python3
"""CIIE Phase-1 forensics CLI (additive - the original cli.py is untouched).

Usage:
    # Full run: legacy acquisition + OCR, then all Phase-1 analyses
    python forensics_cli.py process <file> [--case CASE_0001] [--title "..."]

    # Enrich evidence that was already acquired by the legacy pipeline
    python forensics_cli.py analyze <EVIDENCE_ID>

    # Show latest Phase-1 reports for an evidence item
    python forensics_cli.py reports <EVIDENCE_ID>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.forensics.config import ForensicsConfig
from backend.modules.evidence.forensics.pipeline import build_default_pipeline
from backend.modules.evidence.forensics.repository import ForensicReportRepository
from backend.modules.evidence.utils import EvidenceError


def _print(payload) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def cmd_process(args: argparse.Namespace) -> int:
    pipeline = build_default_pipeline()
    outcome = pipeline.process_file(
        Path(args.file), case_id=args.case, case_title=args.title or ""
    )
    legacy = outcome.pop("legacy_result")
    print(f"evidence_id : {legacy.evidence_id}")
    print(f"case_id     : {legacy.case_id}")
    print(f"hash_verified (chain of custody): {legacy.hash_verified}")
    confidence = outcome.get("confidence")
    if confidence is not None:
        print(f"evidence confidence: {confidence.confidence_score} "
              f"({confidence.confidence_level})")
    failures = outcome.get("failures") or []
    if failures:
        print(f"analysis failures: {failures}", file=sys.stderr)
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    pipeline = build_default_pipeline()
    results = pipeline.analyze_evidence(args.evidence_id)
    confidence = results.get("confidence")
    if confidence is not None:
        print(f"evidence confidence: {confidence.confidence_score} "
              f"({confidence.confidence_level})")
        print(confidence.explanation)
    failures = results.get("failures") or []
    if failures:
        print(f"analysis failures: {failures}", file=sys.stderr)
    return 0


def cmd_reports(args: argparse.Namespace) -> int:
    ecfg = EvidenceConfig.from_env()
    fcfg = ForensicsConfig.from_env(ecfg)
    repo = ForensicReportRepository(fcfg)
    names = (
        fcfg.quality_report_name, fcfg.preprocessing_report_name,
        fcfg.ocr_fusion_report_name, fcfg.forgery_report_name,
        fcfg.logo_report_name, fcfg.metadata_report_name,
        fcfg.fingerprint_report_name, fcfg.confidence_report_name,
    )
    found = False
    for name in names:
        document = repo.load_latest(args.evidence_id, name)
        if document is not None:
            found = True
            print(f"\n===== {name} (v{document.get('report_version')}) =====")
            _print(document.get("report"))
    if not found:
        print(f"No Phase-1 reports stored for '{args.evidence_id}'.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CIIE Phase-1 forensics")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("process", help="acquire + OCR + all Phase-1 analyses")
    p.add_argument("file")
    p.add_argument("--case", default=None)
    p.add_argument("--title", default="")
    p.set_defaults(func=cmd_process)

    p = sub.add_parser("analyze", help="run Phase-1 on existing evidence")
    p.add_argument("evidence_id")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("reports", help="print latest Phase-1 reports")
    p.add_argument("evidence_id")
    p.set_defaults(func=cmd_reports)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
