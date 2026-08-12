"""Dependency-free smoke check for a current case JSON and artifact directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from ciis_rag.adapters import load_case_bundle
from ciis_rag.core.config import RAGConfig
from ciis_rag.documents import build_chunks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-json", required=True)
    parser.add_argument("--artifact-dir", required=True)
    args = parser.parse_args()
    bundle = load_case_bundle(args.case_json, args.artifact_dir)
    chunks = build_chunks(bundle, RAGConfig.from_env())
    print(f"case={bundle.case_id}")
    print(f"evidence={len(bundle.evidence)}")
    print(f"timeline_events={len(bundle.timeline)}")
    print(f"relationships={len(bundle.relationships)}")
    print(f"chunks={len(chunks)}")
    for warning in bundle.warnings:
        print(f"warning={warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
