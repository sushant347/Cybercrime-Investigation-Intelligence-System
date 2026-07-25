#!/usr/bin/env python3
"""Master evaluation runner — one command for the whole Chapter-6 status.

Runs every table that can be computed from artifacts present in the repo,
prints their real outputs, and reports an honest status for the rest
(component-level / estimate-only / blocked-on-human-data). It never fabricates:
blocked tables show the exact command to run once the missing data exists.

    python run_all_evaluations.py

Uses the two project venvs (paddlepaddle vs. the ML stack pin incompatible
numpy majors), shelling out to each with the right interpreter.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLATFORM_PY = ROOT / ".venv-platform" / "bin" / "python"
THREAT_PY = ROOT / ".venv-threat" / "bin" / "python"
OCR = ROOT / "evidence_ocr_engine"
THREAT = ROOT / "threat_intelligence_system"
GT = OCR / "samples" / "ground_truth"


def _run(py: Path, script: Path, *args: str, cwd: Path) -> str:
    if not py.exists():
        return f"[skipped: {py.name} venv not found — run ./dev.sh setup]"
    proc = subprocess.run(
        [str(py), str(script), *args], cwd=str(cwd),
        capture_output=True, text=True,
    )
    return (proc.stdout + proc.stderr).strip()


def _first_analyzed_case() -> str | None:
    audit = OCR / "storage" / "investigation" / "investigation_audit_log.csv"
    if not audit.is_file():
        return None
    with open(audit, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row.get("case_id"):
            return row["case_id"]
    return None


def _gold_is_template(path: Path, key: str) -> bool:
    """True if a gold file is missing or still the empty template."""
    if not path.is_file():
        return True
    data = json.loads(path.read_text(encoding="utf-8"))
    if key == "correlation":
        within = data.get("within_case", {})
        cross = data.get("cross_case", {}).get("related_pairs", [])
        return not any(b.get("related_pairs") for b in within.values()) and not cross
    order = [v.get("order") for k, v in data.items() if not k.startswith("_")]
    return not any(order)


def banner(text: str) -> None:
    print("\n" + "=" * 74 + f"\n{text}\n" + "=" * 74)


def main() -> None:
    status: dict[str, str] = {}

    banner("TABLE 6.3 — URL / phishing classification  [IMPLEMENTED · real]")
    report = sorted((THREAT / "results").glob("full_retraining_report_*.json")) \
        if (THREAT / "results").is_dir() else []
    if report:
        print(_run(THREAT_PY, THREAT / "scripts" / "run_table_6_3.py", cwd=THREAT))
        status["6.3 URL classification"] = "IMPLEMENTED (real, verified test set)"
    else:
        print("Report artifact not present (gitignored). Place "
              "results/full_retraining_report_*.json to reproduce.")
        status["6.3 URL classification"] = "BLOCKED (artifact absent on this machine)"

    banner("TABLE 6.7 — End-to-end processing time  [IMPLEMENTED · real (1 case)]")
    case = _first_analyzed_case()
    if case:
        print(_run(PLATFORM_PY, OCR / "scripts" / "aggregate_processing_time.py",
                   "--case", case, cwd=OCR))
        status["6.7 End-to-end timing"] = f"IMPLEMENTED (real, case {case})"
    else:
        print("No analyzed case in storage. Upload evidence + run analysis first.")
        status["6.7 End-to-end timing"] = "BLOCKED (no analyzed case in storage)"
    status["6.7 Manual-workflow baseline"] = "ESTIMATE/HUMAN (no measurement in code)"
    status["6.7 Report correctness"] = "HARNESS ready (scripts/report_review.py; human grades)"

    banner("TABLE 6.8 — Security  [IMPLEMENTED · test-backed]")
    print("Row 1 unauthorized access : OPEN BY DESIGN — api/tests/test_security_posture.py")
    print("Row 2 file tampering      : DETECTED — tests/test_hash_service.py::test_verify_detects_tampering")
    print("Row 3 homoglyph phishing  : COMPONENT-LEVEL — tests/test_brand_intelligence.py (not e2e)")
    print("Row 4 oversized upload    : REJECTED — api/tests/test_evidence.py::test_upload_rejects_oversized")
    status["6.8 Security (4 rows)"] = "IMPLEMENTED (row 3 component-level, row 1 open-by-design)"

    banner("TABLES 6.4 / 6.5 — Correlation & Timeline  [live services vs. gold]")
    for label, tmpl, key, script in (
        ("6.4 Correlation", GT / "correlation_gold_template.json", "correlation", "run_table_6_4.py"),
        ("6.5 Timeline", GT / "timeline_gold_template.json", "timeline", "run_table_6_5.py"),
    ):
        real = tmpl.with_name(tmpl.name.replace("_template", ""))       # *_gold.json
        example = tmpl.with_name(tmpl.name.replace("_template", "_example"))
        if real.is_file() and not _gold_is_template(real, key):
            target, tag = real, "real gold"
            status[label] = "IMPLEMENTED (real gold provided)"
        elif example.is_file() and not _gold_is_template(example, key):
            target, tag = example, "ILLUSTRATIVE demo gold — real cases, not thesis-grade"
            status[label] = "DEMO runs (example gold; supply real gold for the table)"
        else:
            target = None
            status[label] = "BLOCKED (needs human gold labels)"
        if target is None:
            print(f"{label}: BLOCKED — fill {real.name} then: "
                  f"scripts/{script} --gold samples/ground_truth/{real.name}")
        else:
            print(f"[{tag}]  ({target.name})")
            print(_run(PLATFORM_PY, OCR / "scripts" / script, "--gold", str(target), cwd=OCR))

    banner("TABLES 6.1 / 6.2 — OCR & Entity extraction  [live pipeline vs. gold]")
    ents_gold, texts = GT / "entities_gold_example.json", GT / "texts_example.json"
    if ents_gold.is_file() and texts.is_file():
        print("[ILLUSTRATIVE demo gold — 2 hand-transcribed sample images, not thesis-grade]")
        print(_run(PLATFORM_PY, OCR / "scripts" / "run_table_6_2.py",
                   "--gold", str(ents_gold), "--texts", str(texts), cwd=OCR))
        status["6.2 Entity extraction"] = "DEMO runs (example gold; needs corpus for the table)"
    else:
        print("6.2 Entities: scripts/run_table_6_2.py --gold <gold>.json --texts <texts>.json")
        status["6.2 Entity extraction"] = "BLOCKED (needs annotated corpus + spaCy)"

    if (GT / "ocr_corpus_example.json").is_file():
        print("\n6.1 OCR (live OCR is slow — run separately to see real CER/WER):")
        print("  cd evidence_ocr_engine && ../.venv-platform/bin/python scripts/run_table_6_1.py \\")
        print("      --manifest samples/ground_truth/ocr_corpus_example.json --allow-example")
        status["6.1 OCR"] = "DEMO available (run separately; live OCR)"
    else:
        status["6.1 OCR"] = "BLOCKED (needs annotated corpus)"
    print("\nReal tables need a human-annotated 30-100 sample bilingual corpus "
          "(samples/ground_truth/README.md). spaCy is a new optional dependency.")

    banner("STATUS SUMMARY")
    width = max(len(k) for k in status)
    for k, v in status.items():
        print(f"  {k:<{width}}  {v}")
    print("\n(6.6 RAG: correctly Not Implemented — future work.)")


if __name__ == "__main__":
    main()
