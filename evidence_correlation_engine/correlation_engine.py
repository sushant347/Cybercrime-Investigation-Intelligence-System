"""
Module 4 - Evidence Correlation Engine
========================================
Cybercrime Investigation Intelligence System (CIIS)

Scaffold: loads case JSON files produced by the OCR/evidence engine
(Module 2). Correlation logic to be added next.
"""

import json
import os
import sys
from collections import defaultdict

OUTPUT_DIR = "output"


def load_case(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: python correlation_engine.py <case1.json> [case2.json] ...")
        sys.exit(1)

    cases = [load_case(p) for p in sys.argv[1:]]
    print(f"Loaded {len(cases)} case(s)")


if __name__ == "__main__":
    main()
