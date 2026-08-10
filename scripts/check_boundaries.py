#!/usr/bin/env python3
"""Fail the build if the engine dependency chain has inverted.

The architecture claims one thing above all: the analysis engines form a
straight line, while the RAG engine remains a standalone read-only consumer.

    evidence_ocr_engine -> evidence_correlation_engine -> timeline_report_engine

That claim is load-bearing. It is why each engine can be tested alone, why the
OCR engine can be deployed without the analysis stack, and why the whole thing
is comprehensible. It is also the kind of claim that decays silently: one
convenient import inside a function, added months later, inverts the chain
without breaking a single test - because in a normal test run every engine is
already on ``sys.path``, so the bad import resolves and nothing complains.

This checks the property directly. Each engine is imported in a subprocess with
*only its own* root available, and the run fails if a downstream package
appears in ``sys.modules``.

Exit code 0 = boundaries hold, 1 = a violation (named), 2 = the check itself
could not run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (label, engine root, module to import, packages that must NOT get pulled in)
CHECKS = [
    (
        "OCR engine",
        "evidence_ocr_engine",
        "backend.modules.evidence.pipeline",
        ("ciis_correlation", "ciis_timeline_report"),
    ),
    (
        # It bootstraps the OCR engine itself, so importing it with only its
        # own root on the path is the realistic case. What must not appear is
        # the engine downstream of it.
        "Correlation engine",
        "evidence_correlation_engine",
        "ciis_correlation.correlation.service",
        ("ciis_timeline_report",),
    ),
    (
        "RAG assistant engine",
        "rag_assistant_engine",
        "ciis_rag.assistant.service",
        ("django", "backend", "ciis_correlation", "ciis_timeline_report"),
    ),
]

PROBE = """
import sys
sys.path.insert(0, {root!r})
import importlib
importlib.import_module({module!r})
banned = [name for name in {banned!r} if name in sys.modules]
if banned:
    print("VIOLATION:" + ",".join(banned))
    raise SystemExit(1)
print("OK")
"""


def main() -> int:
    failures = []
    for label, root, module, banned in CHECKS:
        engine_root = REPO / root
        if not engine_root.is_dir():
            print(f"  ?  {label}: {root} not found")
            return 2
        result = subprocess.run(
            [sys.executable, "-c",
             PROBE.format(root=str(engine_root), module=module, banned=list(banned))],
            capture_output=True, text=True, cwd=str(engine_root),
        )
        out = (result.stdout + result.stderr).strip()
        if result.returncode == 0 and "OK" in out:
            print(f"  ok {label}: imports with no downstream engine loaded")
        else:
            print(f"  !! {label}: {out.splitlines()[-1] if out else 'failed'}")
            failures.append(label)

    if failures:
        print(f"\n{len(failures)} boundary violation(s). The analysis chain "
              "must stay OCR -> correlation -> timeline+report, with RAG standalone.")
        return 1
    print("\nmodule boundaries hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
