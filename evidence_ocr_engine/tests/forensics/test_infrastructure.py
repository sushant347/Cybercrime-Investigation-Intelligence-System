"""Shared infrastructure tests: repository versioning + audit trail."""

from __future__ import annotations

import csv


def test_repository_never_overwrites(repo):
    p1 = repo.save("EVID_00001", "CASE_0001", "quality_report", {"score": 1})
    p2 = repo.save("EVID_00001", "CASE_0001", "quality_report", {"score": 2})
    p3 = repo.save("EVID_00001", "CASE_0001", "quality_report", {"score": 3})
    assert p1.name == "quality_report.json"
    assert p2.name == "quality_report_v2.json"
    assert p3.name == "quality_report_v3.json"
    assert p1.exists() and p2.exists() and p3.exists()

    latest = repo.load_latest("EVID_00001", "quality_report")
    assert latest["report"]["score"] == 3
    assert latest["report_version"] == 3
    assert latest["evidence_id"] == "EVID_00001"


def test_repository_reports_are_isolated_per_evidence(repo):
    repo.save("EVID_00001", "CASE_0001", "forgery_report", {"x": 1})
    assert repo.load_latest("EVID_00002", "forgery_report") is None
    assert repo.list_versions("EVID_00001", "forgery_report")


def test_audit_trail_appends_rows(audit):
    audit.record("CASE_0001", "EVID_00001", "quality_assessment", "assessed",
                 "score=90", duration_ms=12.5)
    audit.record("CASE_0001", "EVID_00001", "forgery_detection", "analyzed",
                 level="WARNING")
    with open(audit.path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["module"] == "quality_assessment"
    assert rows[1]["level"] == "WARNING"
    assert rows[0]["timestamp"].endswith("Z")
