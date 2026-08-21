#!/usr/bin/env python3
"""Fail the build on any pyflakes finding that is not deliberate.

Four unused imports in this repository are intentional and must stay:

* the bootstrap import that chains the engine roots together, and
* three ``try: import X`` availability probes that answer "is this optional
  dependency installed?" and are unused by construction.

pyflakes has no ``# noqa`` support, so they have to be excluded here. This is a
script rather than a grep chain in the workflow because the chain silently
stopped matching the moment pyflakes emitted a Windows path separator - it
"passed" locally by filtering nothing and would have behaved differently on CI.

Exit code 0 = clean, 1 = findings (printed), 2 = pyflakes itself failed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TARGETS = [
    "ciis_api/api",
    "ciis_api/config",
    "evidence_correlation_engine/ciis_correlation",
    "timeline_report_engine/ciis_timeline_report",
    "evidence_ocr_engine/backend",
    "rag_assistant_engine/ciis_rag",
]

#: (file basename, exact message) pairs that are deliberate. Matching on the
#: basename keeps this independent of the path separator, which is what broke
#: the previous approach.
ALLOWED: set[tuple[str, str]] = {
    ("__init__.py", "'ciis_correlation' imported but unused"),
    ("engines.py", "'paddleocr' imported but unused"),
    ("engines.py", "'easyocr' imported but unused"),
    ("semantic_pipeline.py", "'transformers' imported but unused"),
}


def parse(line: str) -> tuple[str, str] | None:
    """``path:line:col: message`` -> ``(basename, message)``."""
    parts = line.split(":", 3)
    if len(parts) < 4:
        return None
    # A Windows drive letter ("C:\...") shifts the split; re-join if so.
    if len(parts[0]) == 1 and parts[0].isalpha():
        parts = line.split(":", 4)[1:]
        if len(parts) < 4:
            return None
    path, message = parts[0], parts[-1].strip()
    return Path(path.replace("\\", "/")).name, message


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", *TARGETS],
        capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        sys.stderr.write(result.stderr)
        return 2

    findings = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parsed = parse(line)
        if parsed is None or parsed not in ALLOWED:
            findings.append(line)

    if findings:
        print(f"pyflakes: {len(findings)} finding(s) that are not deliberate\n")
        print("\n".join(f"  {f}" for f in findings))
        return 1

    print(f"pyflakes: clean ({len(ALLOWED)} deliberate probes excluded by name)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
