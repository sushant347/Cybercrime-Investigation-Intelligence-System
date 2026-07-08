"""Command-line interface for investigators (internal API usage example).

Examples::

    # Ingest evidence into a new case
    python cli.py ingest samples/phishing_screenshot.png --title "Bank phishing"

    # Attach more evidence to an existing case, with notes
    python cli.py ingest samples/scam_sms.jpg --case CASE_0001 --notes "victim's phone"

    # List cases / show a case's stored JSON
    python cli.py list-cases
    python cli.py show-case CASE_0001

    # Prompt 2: clean OCR output + extract forensic entities for a case
    python cli.py clean CASE_0001
    python cli.py clean CASE_0001 --evidence EVID_00002
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.modules.evidence import (  # noqa: E402
    EvidenceConfig,
    EvidenceError,
    EvidencePipeline,
    JSONCaseStorage,
    PaddleOCRService,
)
from backend.modules.evidence.csv_storage import CaseRepository  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidence-engine",
        description="Digital Evidence Acquisition and OCR Engine (CIIS Module 2)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="acquire and OCR one evidence file")
    ingest.add_argument("file", type=Path, help="evidence file (png/jpg/jpeg/pdf/txt/csv/docx)")
    ingest.add_argument("--case", default=None, help="existing case id (default: create new)")
    ingest.add_argument("--title", default="", help="case title when creating a new case")
    ingest.add_argument("--notes", default="", help="investigator notes")
    ingest.add_argument("--lang", default=None, help="OCR language (en, devanagari, ...)")

    sub.add_parser("list-cases", help="list all investigation cases")

    show = sub.add_parser("show-case", help="print the full JSON of a case")
    show.add_argument("case_id")

    clean = sub.add_parser(
        "clean", help="clean OCR text + extract entities (Module 2 / Prompt 2)"
    )
    clean.add_argument("case_id")
    clean.add_argument("--evidence", default=None,
                       help="clean only this evidence id")

    enhance = sub.add_parser(
        "enhance", help="confidence-based OCR correction (Module 2 / Prompt 2.5)"
    )
    enhance.add_argument("case_id")
    enhance.add_argument("--evidence", default=None,
                         help="enhance only this evidence id")

    semantic = sub.add_parser(
        "semantic", help="context-validate corrections with XLM-R (Semantic Engine)")
    semantic.add_argument("case_id")
    semantic.add_argument("--evidence", default=None,
                          help="process only this evidence id")
    semantic.add_argument("--no-xlmr", action="store_true",
                          help="use the offline heuristic validator instead of XLM-R")

    process = sub.add_parser(
        "process", help="run clean -> enhance -> semantic for a case (merged pipeline)")
    process.add_argument("case_id")
    process.add_argument("--no-xlmr", action="store_true",
                         help="use the offline heuristic validator instead of XLM-R")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = EvidenceConfig.from_env()

    if args.command == "list-cases":
        for row in CaseRepository(config).read_all():
            print(f"{row['case_id']}  {row['created_at']}  "
                  f"evidence={row['evidence_count']}  {row['title']}")
        return 0

    if args.command == "show-case":
        document = JSONCaseStorage(config).load_case(args.case_id)
        if document is None:
            print(f"Case '{args.case_id}' not found", file=sys.stderr)
            return 1
        print(json.dumps(document, ensure_ascii=False, indent=2))
        return 0

    if args.command == "clean":
        from backend.modules.evidence.cleaning import CleaningService

        service = CleaningService(config)
        try:
            if args.evidence:
                results = [service.clean_evidence(args.case_id, args.evidence)]
            else:
                results = service.clean_case(args.case_id)
        except EvidenceError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for res in results:
            print(f"{res.evidence_id}: language={res.language}, "
                  f"entities={res.statistics.entity_count}, "
                  f"keyword_hits={sum(res.keywords.values())}, "
                  f"{res.processing_time_ms:.1f} ms")
        return 0

    if args.command == "enhance":
        from backend.modules.evidence.enhancement import EnhancementService

        service = EnhancementService(config)
        try:
            if args.evidence:
                results = [service.enhance_evidence(args.case_id, args.evidence)]
            else:
                results = service.enhance_case(args.case_id)
        except EvidenceError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for res in results:
            stats = res.correction_statistics
            print(f"{res.evidence_id}: corrections={stats.total_corrections} "
                  f"(nepali={stats.nepali_corrections}, "
                  f"english={stats.english_corrections}, "
                  f"unicode={stats.unicode_corrections}), "
                  f"doc_confidence={stats.document_confidence:.2f}, "
                  f"{res.processing_time_ms:.1f} ms")
        return 0

    if args.command == "semantic":
        from backend.modules.evidence.semantic import (
            SemanticCorrectionPipeline, SemanticCorrectionService)

        pipeline = SemanticCorrectionPipeline(use_xlm_roberta=not args.no_xlmr)
        service = SemanticCorrectionService(config, pipeline=pipeline)
        try:
            if args.evidence:
                results = [service.correct_evidence(args.case_id, args.evidence)]
            else:
                results = service.correct_case(args.case_id)
        except EvidenceError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for res in results:
            s = res.statistics
            print(f"{res.evidence_id}: validator={s.validator}, "
                  f"suspects={s.suspicious_tokens}, "
                  f"accepted={s.accepted_corrections}, "
                  f"rejected={s.rejected_corrections}, "
                  f"confidence={res.confidence:.2f}, "
                  f"{res.processing_time_ms:.1f} ms")
        return 0

    if args.command == "process":
        from backend.modules.evidence.semantic import (
            EvidenceProcessingOrchestrator, SemanticCorrectionPipeline)

        pipeline = SemanticCorrectionPipeline(use_xlm_roberta=not args.no_xlmr)
        orchestrator = EvidenceProcessingOrchestrator(config, semantic_pipeline=pipeline)
        try:
            summary = orchestrator.process_case(args.case_id)
        except EvidenceError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        st = summary["stages"]
        print(f"{args.case_id}: cleaned={st['cleaning']} enhanced={st['enhancement']} "
              f"semantic={st['semantic']} in {summary['duration_ms']:.0f} ms")
        for res in summary["semantic_results"]:
            print(f"  {res.evidence_id}: accepted={res.statistics.accepted_corrections}, "
                  f"entities={sum(len(v) for v in res.entities.values())}")
        return 0

    # ingest
    try:
        pipeline = EvidencePipeline(config, PaddleOCRService(config, lang=args.lang))
        result = pipeline.process_file(
            args.file, case_id=args.case, notes=args.notes, case_title=args.title
        )
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
