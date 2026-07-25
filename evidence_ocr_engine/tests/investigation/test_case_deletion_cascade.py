"""Deleting a case must not leave other cases citing it.

The admin delete is two halves: purge the case, then rebuild every case that
referenced it. The second half is driven entirely by
:func:`linked_case_ids`, so if that under-reports, surviving cases keep showing
the deleted case in their cross-case correlation, graph and report — which is
exactly the failure these tests pin down.

The fixtures and seeding helpers are shared with the cross-case suite.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.investigation.config import InvestigationConfig
from backend.modules.investigation.maintenance import delete_case, linked_case_ids
from backend.modules.investigation.pipeline import build_default_pipeline
from backend.modules.investigation.repository import InvestigationReportRepository

from .test_cross_case_correlation import _seed_case, ecfg, icfg  # noqa: F401

_CASE_FIELDS = ["case_id", "case_reference", "title", "created_at", "status"]


def _register_cases(ecfg: EvidenceConfig, *case_ids: str) -> None:
    """Give each case a row in cases.csv so delete_case has something to purge."""
    with open(ecfg.cases_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CASE_FIELDS)
        writer.writeheader()
        for case_id in case_ids:
            writer.writerow({
                "case_id": case_id, "case_reference": f"REF-{case_id}",
                "title": case_id, "created_at": "2026-07-01T00:00:00Z",
                "status": "active",
            })


def _link_two_cases(ecfg: EvidenceConfig, icfg: InvestigationConfig):
    """Two cases sharing a phone number, both fully analysed."""
    _seed_case(ecfg, icfg, "CASE_KEEP", [("EA", "2026-07-01T10:00:00Z")],
               [("EA", "phones", "9812345678", "9812345678")])
    _seed_case(ecfg, icfg, "CASE_GONE", [("EB", "2026-07-02T10:00:00Z")],
               [("EB", "phones", "9812345678", "9812345678")])
    _register_cases(ecfg, "CASE_KEEP", "CASE_GONE")
    pipe = build_default_pipeline(ecfg, icfg)
    pipe.analyze_case("CASE_KEEP")
    pipe.analyze_case("CASE_GONE")
    return pipe


def test_the_survivor_is_identified_as_linked(ecfg, icfg):  # noqa: F811
    """The case to rebuild is found even though it is the *other* case's artifact
    that names the doomed one."""
    _link_two_cases(ecfg, icfg)

    assert linked_case_ids(icfg, "CASE_GONE") == ["CASE_KEEP"]


def test_linked_case_found_when_doomed_case_has_no_artifacts(ecfg, icfg):  # noqa: F811
    """The regression: an unanalysed case still has to be cleaned up after.

    The old implementation read only the doomed case's own cross-case report.
    With no artifact it returned an empty list, nothing was rebuilt, and
    CASE_KEEP kept citing a case that no longer existed.
    """
    _link_two_cases(ecfg, icfg)
    # Wipe the doomed case's own artifacts, leaving only CASE_KEEP's view.
    for path in icfg.case_dir("CASE_GONE").glob("cross_case_correlation*"):
        path.unlink()

    assert linked_case_ids(icfg, "CASE_GONE") == ["CASE_KEEP"], (
        "a case must be rebuilt because *it* references the deleted case, "
        "not because the deleted case happened to have recorded the link"
    )


def test_unrelated_cases_are_not_rebuilt(ecfg, icfg):  # noqa: F811
    """Only cases that actually reference the deleted one are touched."""
    _link_two_cases(ecfg, icfg)
    _seed_case(ecfg, icfg, "CASE_OTHER", [("EC", "2026-07-03T10:00:00Z")],
               [("EC", "phones", "9800000000", "9800000000")])
    _register_cases(ecfg, "CASE_KEEP", "CASE_GONE", "CASE_OTHER")
    build_default_pipeline(ecfg, icfg).analyze_case("CASE_OTHER")

    linked = linked_case_ids(icfg, "CASE_GONE")

    assert "CASE_OTHER" not in linked, "unrelated cases must not be rebuilt"
    assert linked == ["CASE_KEEP"]


def test_deleted_case_is_gone_from_the_single_entity_file(ecfg, icfg):  # noqa: F811
    """Cross-correlation reads entities.csv, so the purge alone must silence it."""
    _link_two_cases(ecfg, icfg)

    delete_case(ecfg, icfg, "CASE_GONE")

    rows = list(csv.DictReader(open(icfg.entities_csv, encoding="utf-8")))
    assert rows, "other cases' entities must survive"
    assert not [r for r in rows if r["case_id"] == "CASE_GONE"]
    # And a freshly computed correlation no longer sees it.
    fresh = build_default_pipeline(ecfg, icfg).analyze_case("CASE_KEEP")
    assert fresh["cross_case"].related_case_ids == []


def test_rebuilding_the_survivor_clears_the_stale_reference(ecfg, icfg):  # noqa: F811
    """End-to-end: after purge + rebuild, nothing the survivor stores cites the
    deleted case."""
    _link_two_cases(ecfg, icfg)
    repo = InvestigationReportRepository(icfg)
    before = repo.load_latest("CASE_KEEP", icfg.cross_case_report_name)
    assert "CASE_GONE" in json.dumps(before), "precondition: the link exists"

    linked = linked_case_ids(icfg, "CASE_GONE")
    delete_case(ecfg, icfg, "CASE_GONE")
    # This is what the API cascade does for each linked case.
    pipe = build_default_pipeline(ecfg, icfg)
    for other in linked:
        pipe.refresh_timeline_graph(other)

    for report_name in (icfg.cross_case_report_name, icfg.graph_report_name):
        latest = repo.load_latest("CASE_KEEP", report_name)
        assert latest is not None
        assert "CASE_GONE" not in json.dumps(latest), (
            f"{report_name} still references the deleted case"
        )


def test_orphaned_entity_rows_cannot_resurrect_a_deleted_case(ecfg, icfg):  # noqa: F811
    """The root cause the user hit: entities.csv outliving its case.

    An entity row whose case has no evidence left is orphaned data. Cross-case
    correlation reads entities.csv directly, so without a guard one leftover
    row keeps a deleted case appearing in every other case's correlation.
    """
    _link_two_cases(ecfg, icfg)
    delete_case(ecfg, icfg, "CASE_GONE")

    # Simulate a delete that did not finish: put the entity rows back, but
    # leave the evidence deleted (which is what "the case is gone" means).
    with open(icfg.entities_csv, "a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            ["CASE_GONE", "EB", "phones", "9812345678", "9812345678",
             "2026-07-05T00:00:00.000Z"]
        )

    cross = build_default_pipeline(ecfg, icfg).analyze_case("CASE_KEEP")["cross_case"]

    assert cross.related_case_ids == [], (
        "an entity row whose case has no evidence must not create a link"
    )


def test_deleting_a_case_sweeps_previously_orphaned_rows(ecfg, icfg):  # noqa: F811
    """Deletion also cleans up rows a previous failed delete left behind."""
    _link_two_cases(ecfg, icfg)
    with open(icfg.entities_csv, "a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            ["CASE_LONG_GONE", "EZ", "phones", "9899999999", "9899999999",
             "2026-07-05T00:00:00.000Z"]
        )

    delete_case(ecfg, icfg, "CASE_GONE")

    remaining = {r["case_id"]
                 for r in csv.DictReader(open(icfg.entities_csv, encoding="utf-8"))}
    assert remaining == {"CASE_KEEP"}, "orphans swept, live case untouched"


def test_purge_does_not_touch_the_surviving_case_files(ecfg, icfg):  # noqa: F811
    """Deleting one case must not remove another case's stored data."""
    _link_two_cases(ecfg, icfg)
    survivor_json = Path(ecfg.json_dir / "CASE_KEEP.json")
    survivor_dir = icfg.case_dir("CASE_KEEP")
    assert survivor_json.is_file() and survivor_dir.is_dir()

    delete_case(ecfg, icfg, "CASE_GONE")

    assert survivor_json.is_file(), "survivor's OCR JSON was deleted"
    assert survivor_dir.is_dir(), "survivor's artifacts were deleted"
    assert not (ecfg.json_dir / "CASE_GONE.json").exists()
    assert not icfg.case_dir("CASE_GONE").exists()
