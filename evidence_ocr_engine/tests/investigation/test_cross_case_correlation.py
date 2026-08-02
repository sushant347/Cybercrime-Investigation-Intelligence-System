"""Cross-case entity correlation (Module 1 persistent-index extension).

Covers the behaviours required of the feature:

* exact cross-case entity matches create links,
* normalized matches (different raw text, same normalized value) create links,
* unrelated cases produce no links,
* re-processing a case is idempotent (no duplicate entities, no duplicate
  correlations, no report-version spam),
* a new match updates *both* cases' correlation artifacts and reports
  (bidirectional propagation),
* the engine reset clears every case and entity.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.investigation.config import InvestigationConfig
from backend.modules.investigation.maintenance import reset_all
from backend.modules.investigation.pipeline import build_default_pipeline
from backend.modules.investigation.repository import InvestigationReportRepository

_EVIDENCE_FIELDS = [
    "evidence_id", "case_id", "original_file_name", "stored_file_name",
    "file_extension", "file_size_bytes", "sha256_before", "sha256_after",
    "hash_verified", "upload_time", "processing_time", "status",
    "investigator_notes",
]

#: One entity row: (evidence_id, entity_type, raw_value, normalized_value)
Entity = Tuple[str, str, str, str]


@pytest.fixture()
def ecfg(tmp_path: Path) -> EvidenceConfig:
    """A fully temp EvidenceConfig (every path under tmp, incl. the registry)."""
    storage = tmp_path / "storage"
    cfg = EvidenceConfig(
        base_dir=tmp_path,
        storage_dir=storage,
        json_dir=storage / "json",
        originals_dir=storage / "originals",
        log_dir=tmp_path / "logs",
        cases_csv=storage / "cases.csv",
        evidence_csv=storage / "evidence.csv",
        ocr_results_csv=storage / "ocr_results.csv",
        processing_log_csv=storage / "processing_log.csv",
        case_registry_csv=storage / "case_registry.csv",
    )
    cfg.ensure_directories()
    return cfg


@pytest.fixture()
def icfg(ecfg: EvidenceConfig) -> InvestigationConfig:
    cfg = InvestigationConfig.from_evidence_config(ecfg)
    cfg.ensure_directories()
    return cfg


def _seed_case(
    ecfg: EvidenceConfig,
    icfg: InvestigationConfig,
    case_id: str,
    evidence: Sequence[Tuple[str, str]],   # (evidence_id, upload_time)
    entities: Sequence[Entity],
) -> None:
    """Append one case's evidence + entities to the shared temp storage."""
    new = not ecfg.evidence_csv.exists()
    with open(ecfg.evidence_csv, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_EVIDENCE_FIELDS)
        if new:
            writer.writeheader()
        for evidence_id, upload in evidence:
            writer.writerow({
                "evidence_id": evidence_id, "case_id": case_id,
                "original_file_name": f"{evidence_id}.png",
                "stored_file_name": f"{evidence_id}__x__{evidence_id}.png",
                "file_extension": ".png", "file_size_bytes": "1000",
                "sha256_before": evidence_id * 8, "sha256_after": evidence_id * 8,
                "hash_verified": "True", "upload_time": upload,
                "processing_time": upload, "status": "processed",
                "investigator_notes": "",
            })

    new_entities = not icfg.entities_csv.exists()
    with open(icfg.entities_csv, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_entities:
            writer.writerow(["case_id", "evidence_id", "entity_type", "value",
                             "normalized", "extracted_at"])
        for evidence_id, entity_type, value, normalized in entities:
            writer.writerow([case_id, evidence_id, entity_type, value,
                             normalized, "2026-07-05T00:00:00.000Z"])

    case_doc = {
        "case_id": case_id,
        "evidence": [
            {"evidence_id": evidence_id, "case_id": case_id,
             "raw_text": "sample", "average_confidence": 0.9}
            for evidence_id, _ in evidence
        ],
    }
    (ecfg.json_dir / f"{case_id}.json").write_text(json.dumps(case_doc),
                                                   encoding="utf-8")


def _cross_case(repo: InvestigationReportRepository, case_id: str) -> Dict:
    doc = repo.load_latest(case_id, "cross_case_correlation")
    assert doc is not None, f"no cross_case artifact for {case_id}"
    return doc


def _report(repo: InvestigationReportRepository, case_id: str) -> Dict:
    doc = repo.load_latest(case_id, "investigation_report")
    assert doc is not None, f"no report for {case_id}"
    return doc


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_exact_match_links_two_cases(ecfg, icfg):
    """Identical phone in two cases -> a cross-case link on the second case."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "9812345678", "9812345678")])
    pipe = build_default_pipeline(ecfg, icfg)

    # Entities live in the single entities.csv, so a case is matchable as soon
    # as its entities are extracted - it does NOT have to be analysed first.
    # (Previously an unanalysed case was invisible to cross-case correlation.)
    first = pipe.analyze_case("CASE_1")
    assert first["cross_case"].related_case_ids == ["CASE_2"]

    second = pipe.analyze_case("CASE_2")
    cross = second["cross_case"]
    assert cross.link_count == 1
    link = cross.links[0]
    assert link.other_case_id == "CASE_1"
    assert link.match_confidence > 0
    assert link.matched_entities[0].entity_type == "phones"
    assert link.matched_entities[0].value == "9812345678"
    assert "EA" in link.other_evidence_ids and "EB" in link.this_evidence_ids


def test_normalized_match_links_two_cases(ecfg, icfg):
    """Different raw text but the same normalized value still links."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "98-1234-5678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "+977 9812345678", "9812345678")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    cross = pipe.analyze_case("CASE_2")["cross_case"]

    assert cross.related_case_ids == ["CASE_1"]
    assert cross.links[0].matched_entities[0].value == "9812345678"


def test_no_match_no_link(ecfg, icfg):
    """Cases with no shared entities produce no cross-case links."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "9811111111", "9811111111")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "9822222222", "9822222222")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    cross = pipe.analyze_case("CASE_2")["cross_case"]

    assert cross.link_count == 0
    assert cross.related_case_ids == []


def test_temporal_entities_do_not_link(ecfg, icfg):
    """Shared dates/times are coincidental and must not link cases."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "dates", "2026-01-04", "2026-01-04"),
                ("EA", "times", "09:12", "09:12")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "dates", "2026-01-04", "2026-01-04"),
                ("EB", "times", "09:12", "09:12")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    cross = pipe.analyze_case("CASE_2")["cross_case"]

    assert cross.link_count == 0


def test_wallet_identifier_links_cross_case(ecfg, icfg):
    """A shared eSewa wallet id links two cases (extractor emits 'esewa_ids')."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "esewa_ids", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "esewa_ids", "9812345678", "9812345678")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    cross = pipe.analyze_case("CASE_2")["cross_case"]

    assert cross.related_case_ids == ["CASE_1"]
    assert cross.links[0].matched_entities[0].entity_type == "esewa_ids"
    assert cross.links[0].relationship_strength in {"MEDIUM", "STRONG", "VERY_STRONG"}


def test_shared_round_amount_does_not_link_cases(ecfg, icfg):
    """A common round amount is not evidence that two cases are connected.

    "Rs 2000" is one of a handful of amounts that appear in most scam cases,
    so a shared occurrence says essentially nothing. It used to be enough to
    declare a cross-case link, which named unrelated cases in each other's
    reports and pulled them into each other's re-analysis.
    """
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "money", "Rs 2000", "Rs 2000")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "money", "Rs 2000", "Rs 2000")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    cross = pipe.analyze_case("CASE_2")["cross_case"]

    assert cross.link_count == 0


def test_shared_distinctive_amount_still_links(ecfg, icfg):
    """An unusual amount is a real signal and must survive the discount.

    The fix must not amount to "ignore money": an oddly specific figure two
    cases both record is exactly the kind of detail that ties a victim's
    transfer to a scammer's receipt.
    """
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "money", "Rs 17432.55", "Rs 17432.55")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "money", "Rs 17432.55", "Rs 17432.55")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    cross = pipe.analyze_case("CASE_2")["cross_case"]

    assert cross.link_count == 1
    match = cross.links[0].matched_entities[0]
    assert match.specificity > 0.6, match.specificity_reason


def test_shared_identifier_outweighs_shared_amount(ecfg, icfg):
    """A shared phone must dominate a shared round amount, not tie with it."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_3", [("EC", "2026-07-03T10:00:00Z")],
               [("EC", "money", "Rs 2000", "Rs 2000")])
    _seed_case(ecfg, icfg, "CASE_4", [("ED", "2026-07-04T10:00:00Z")],
               [("ED", "money", "Rs 2000", "Rs 2000")])
    pipe = build_default_pipeline(ecfg, icfg)
    for case_id in ("CASE_1", "CASE_3", "CASE_4"):
        pipe.analyze_case(case_id)
    phone_link = pipe.analyze_case("CASE_2")["cross_case"]
    amount_link = pipe.analyze_case("CASE_4")["cross_case"]

    assert phone_link.link_count == 1
    assert phone_link.links[0].relationship_strength in ("MEDIUM", "STRONG", "VERY_STRONG")
    assert amount_link.link_count == 0


def test_duplicate_processing_is_idempotent(ecfg, icfg):
    """Re-analysing a case adds no duplicate entities or correlations."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "9812345678", "9812345678")])
    pipe = build_default_pipeline(ecfg, icfg)
    repo = InvestigationReportRepository(icfg)

    pipe.analyze_case("CASE_1")
    pipe.analyze_case("CASE_2")
    # Baseline after the first full round. CASE_1's report is already at v2:
    # v1 from its own analysis, v2 from propagation when CASE_2 linked to it.
    entities_after_first = pipe._correlation.index.entity_count()
    case1_cross_versions = len(repo.list_versions("CASE_1", "cross_case_correlation"))
    case1_report_versions = len(repo.list_versions("CASE_1", "investigation_report"))

    # Re-analyse CASE_2 with no data change.
    pipe.analyze_case("CASE_2")

    # Index did not grow (dedup) ...
    assert pipe._correlation.index.entity_count() == entities_after_first
    # ... the unchanged link did not spawn a new CASE_1 cross-case version ...
    assert len(repo.list_versions("CASE_1", "cross_case_correlation")) == case1_cross_versions
    # ... and CASE_1's report was NOT regenerated (its cross-case is unchanged).
    assert len(repo.list_versions("CASE_1", "investigation_report")) == case1_report_versions


def test_bidirectional_report_update(ecfg, icfg):
    """Analysing the 2nd case updates the 1st case's artifact *and* report."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "wallets", "esewa:9812345678", "esewa:9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "wallets", "esewa:9812345678", "esewa:9812345678")])
    pipe = build_default_pipeline(ecfg, icfg)
    repo = InvestigationReportRepository(icfg)

    pipe.analyze_case("CASE_1")
    # Both cases' entities are already in the single entities.csv, so CASE_1
    # sees CASE_2 on its first analysis.
    assert _cross_case(repo, "CASE_1")["report"]["related_case_ids"] == ["CASE_2"]
    assert len(repo.list_versions("CASE_1", "investigation_report")) == 1

    pipe.analyze_case("CASE_2")

    # CASE_1's stored cross-case artifact reflects the link to CASE_2. It was
    # already correct at v1 (both cases' entities share one file), so
    # save-if-changed rightly does NOT write a duplicate version - what matters
    # is the content, which both sides agree on.
    case1_cross = _cross_case(repo, "CASE_1")["report"]
    assert case1_cross["related_case_ids"] == ["CASE_2"]
    case2_cross = _cross_case(repo, "CASE_2")["report"]
    assert case2_cross["related_case_ids"] == ["CASE_1"]  # bidirectional
    # ... and CASE_1's report carries the cross-case section.
    case1_report = _report(repo, "CASE_1")["report"]
    section = case1_report["sections"]["cross_case_correlation"]
    assert isinstance(section, dict)
    assert section["related_case_ids"] == ["CASE_2"]
    assert any("linked to" in line
               for line in case1_report["sections"]["executive_summary"])


def test_reset_clears_cases_and_entities(ecfg, icfg):
    """The engine reset wipes cases, entities, artifacts and the index."""
    _seed_case(ecfg, icfg, "CASE_1", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_2", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "9812345678", "9812345678")])
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_1")
    pipe.analyze_case("CASE_2")

    assert pipe._correlation.index.entity_count() > 0
    # There is no separate cross-case index file any more: entities.csv is the
    # single store that cross-case correlation reads.
    assert not icfg.cross_case_index_path.exists()
    assert (icfg.case_dir("CASE_1")).is_dir()

    summary = reset_all(ecfg, icfg)

    # Entities and per-case artifacts are gone.
    assert not icfg.cross_case_index_path.exists()
    assert not icfg.case_dir("CASE_1").is_dir()
    assert not icfg.case_dir("CASE_2").is_dir()
    assert summary["investigation_case_dirs_removed"] >= 2
    # CSVs are truncated to just their header (0 data rows).
    with open(ecfg.evidence_csv, encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == []
    with open(icfg.entities_csv, encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == []
    # A brand-new index reads empty.
    fresh = build_default_pipeline(ecfg, icfg)
    assert fresh._correlation.index.entity_count() == 0
