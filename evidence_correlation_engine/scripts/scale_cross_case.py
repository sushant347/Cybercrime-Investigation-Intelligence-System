#!/usr/bin/env python3
"""Measure how cross-case correlation scales, and find where it stops being usable.

Cross-case correlation is the one component with a genuinely super-linear shape:
for every entity of the case under analysis it looks up every occurrence of that
value in every other case. On the tracked corpus - 4 cases, 152 entities - it
runs in milliseconds, which tells you nothing about what happens at the size a
real unit reaches in a year.

This builds synthetic corpora at increasing sizes and times the real code path
against them, so the limit is a measured number rather than a guess.

    python scripts/scale_cross_case.py                # default sweep
    python scripts/scale_cross_case.py --max-cases 500

Nothing here touches the real storage tree: every run gets its own temp
directory and is deleted afterwards.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ciis_correlation  # noqa: E402,F401  (chains the OCR-engine bootstrap)

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from ciis_correlation.core.config import InvestigationConfig  # noqa: E402
from ciis_correlation.core.data_access import CaseDataRepository  # noqa: E402
from ciis_correlation.correlation.service import CorrelationService  # noqa: E402
from ciis_correlation.core.repository import (  # noqa: E402
    InvestigationReportRepository,
)
from ciis_correlation.core.audit import InvestigationAuditTrail  # noqa: E402

#: Entity types that participate in cross-case matching, with a value pattern.
#: Mixing shared and unique values matters: a corpus where nothing matches is
#: the easy case, and a corpus where everything matches is not realistic.
_TYPES = ("phones", "emails", "esewa_ids", "bank_accounts", "urls")


def build_corpus(root: Path, cases: int, evidence_per_case: int,
                 entities_per_item: int, shared_every: int) -> EvidenceConfig:
    """Write a synthetic storage tree and return its config.

    ``shared_every`` controls collision density: one entity in every N is drawn
    from a small shared pool, so cases genuinely link rather than being N
    isolated islands.
    """
    storage = root / "storage"
    cfg = EvidenceConfig(
        base_dir=root, storage_dir=storage, json_dir=storage / "json",
        originals_dir=storage / "originals", log_dir=root / "logs",
        cases_csv=storage / "cases.csv", evidence_csv=storage / "evidence.csv",
        ocr_results_csv=storage / "ocr_results.csv",
        processing_log_csv=storage / "processing_log.csv",
    )
    cfg.ensure_directories()

    evidence_fields = [
        "evidence_id", "case_id", "original_file_name", "stored_file_name",
        "file_extension", "file_size_bytes", "sha256_before", "sha256_after",
        "hash_verified", "upload_time", "processing_time", "status",
        "investigator_notes",
    ]
    entity_fields = ["case_id", "evidence_id", "entity_type", "value",
                     "normalized", "extracted_at"]

    shared_pool = [f"9800{n:06d}" for n in range(50)]
    counter = 0

    with open(cfg.evidence_csv, "w", newline="", encoding="utf-8") as ev, \
         open(storage / "entities.csv", "w", newline="", encoding="utf-8") as en:
        ew = csv.DictWriter(ev, fieldnames=evidence_fields); ew.writeheader()
        nw = csv.DictWriter(en, fieldnames=entity_fields); nw.writeheader()
        for c in range(cases):
            case_id = f"CASE_S{c:05d}"
            for e in range(evidence_per_case):
                evidence_id = f"EVID_{c:05d}_{e:03d}"
                ew.writerow({
                    "evidence_id": evidence_id, "case_id": case_id,
                    "original_file_name": f"{evidence_id}.png",
                    "stored_file_name": f"{evidence_id}.png",
                    "file_extension": ".png", "file_size_bytes": "1024",
                    "sha256_before": "a" * 64, "sha256_after": "a" * 64,
                    "hash_verified": "True",
                    "upload_time": f"2026-01-01T{e % 24:02d}:00:00.000Z",
                    "processing_time": "1.0", "status": "processed",
                    "investigator_notes": "",
                })
                for k in range(entities_per_item):
                    counter += 1
                    etype = _TYPES[k % len(_TYPES)]
                    if counter % shared_every == 0:
                        value = shared_pool[counter % len(shared_pool)]
                    else:
                        value = f"{etype}-{counter:09d}"
                    nw.writerow({
                        "case_id": case_id, "evidence_id": evidence_id,
                        "entity_type": etype, "value": value,
                        "normalized": value.lower(),
                        "extracted_at": "2026-01-01T00:00:00.000Z",
                    })
    return cfg


def measure(cases: int, evidence_per_case: int, entities_per_item: int,
            shared_every: int) -> dict:
    root = Path(tempfile.mkdtemp(prefix="ciis-scale-"))
    try:
        ecfg = build_corpus(root, cases, evidence_per_case,
                            entities_per_item, shared_every)
        icfg = InvestigationConfig.from_evidence_config(ecfg)
        icfg.ensure_directories()
        data = CaseDataRepository(icfg)
        service = CorrelationService(
            icfg, data, InvestigationReportRepository(icfg),
            InvestigationAuditTrail(icfg),
        )

        target = "CASE_S00000"
        items = data.load_case_evidence(target)

        started = time.perf_counter()
        service.index_case_entities(target, items)
        indexed = time.perf_counter() - started

        started = time.perf_counter()
        result = service.correlate_cross_case(target, items)
        elapsed = time.perf_counter() - started

        total_entities = cases * evidence_per_case * entities_per_item
        return {
            "cases": cases,
            "entities": total_entities,
            "index_s": round(indexed, 3),
            "correlate_s": round(elapsed, 3),
            "links": result.link_count,
            "us_per_entity": round(elapsed / max(total_entities, 1) * 1e6, 1),
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-cases", type=int, default=400)
    parser.add_argument("--evidence-per-case", type=int, default=8)
    parser.add_argument("--entities-per-item", type=int, default=20)
    parser.add_argument("--shared-every", type=int, default=25,
                        help="1 entity in N is drawn from a shared pool")
    args = parser.parse_args()

    sizes = [n for n in (5, 10, 25, 50, 100, 200, 400, 800, 1600)
             if n <= args.max_cases]
    print(f"{'cases':>7} {'entities':>10} {'index s':>9} {'correlate s':>12} "
          f"{'links':>7} {'us/entity':>10}")
    rows = []
    for n in sizes:
        row = measure(n, args.evidence_per_case, args.entities_per_item,
                      args.shared_every)
        rows.append(row)
        print(f"{row['cases']:>7} {row['entities']:>10} {row['index_s']:>9} "
              f"{row['correlate_s']:>12} {row['links']:>7} "
              f"{row['us_per_entity']:>10}")

    # Growth factor between the last two points: 1.0 is linear, 2.0 quadratic.
    if len(rows) >= 2:
        a, b = rows[-2], rows[-1]
        if a["correlate_s"] > 0 and a["entities"] > 0:
            size_ratio = b["entities"] / a["entities"]
            time_ratio = b["correlate_s"] / a["correlate_s"]
            import math
            exponent = math.log(time_ratio) / math.log(size_ratio)
            print(f"\nobserved growth: time ~ n^{exponent:.2f} "
                  f"over the last doubling (1.0 = linear, 2.0 = quadratic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
