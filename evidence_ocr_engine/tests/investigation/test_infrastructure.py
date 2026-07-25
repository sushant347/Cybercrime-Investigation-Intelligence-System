"""Phase-2 infrastructure tests: data gateway, repository, audit, threat intel."""

from __future__ import annotations

import csv

from .conftest import CASE


def test_data_gateway_loads_full_context(data):
    items = data.load_case_evidence(CASE)
    assert [c.evidence_id for c in items] == ["EVID_A", "EVID_B", "EVID_C", "EVID_D"]
    a = items[0]
    assert a.file_name == "chat_offer.png"
    assert a.hash_verified is True
    assert "prize" in a.raw_text.lower()
    assert a.ocr_confidence == 0.9
    assert set(a.entity_values("phones")) == {"9812345678"}
    assert a.forensics["evidence_confidence"]["confidence_score"] == 85.0
    assert data.case_exists(CASE)
    assert not data.case_exists("CASE_0000")
    assert data.list_case_ids() == [CASE]


def test_threat_intel_provider(data):
    intel = data.threat_intel
    assert intel.available
    assert intel.is_malicious("scam-bank.top")
    assert intel.is_malicious("http://scam-bank.top/login")  # via domain match
    assert not intel.is_malicious("https://example.com")


def test_repository_keeps_one_file_per_report(repo):
    """Re-analysis replaces the stored report instead of piling up _v2, _v3…"""
    p1 = repo.save(CASE, "correlation_analysis", {"n": 1})
    p2 = repo.save(CASE, "correlation_analysis", {"n": 2})

    assert p1 == p2 == repo._cfg.case_dir(CASE) / "correlation_analysis.json"
    assert repo.list_versions(CASE, "correlation_analysis", ".json") == [p2]
    assert repo.load_latest(CASE, "correlation_analysis")["report"]["n"] == 2


def test_report_version_still_counts_the_analysis_runs(repo):
    """Only one file is kept, but it must still say which run produced it."""
    repo.save(CASE, "correlation_analysis", {"n": 1})
    repo.save(CASE, "correlation_analysis", {"n": 2})
    repo.save(CASE, "correlation_analysis", {"n": 3})

    assert repo.load_latest(CASE, "correlation_analysis")["report_version"] == 3


def test_legacy_versioned_files_are_swept_on_next_save(repo):
    """Artifacts written before single-file storage must not linger."""
    directory = repo._cfg.case_dir(CASE)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "correlation_analysis_v2.json").write_text(
        '{"report_version": 2, "report": {}}', encoding="utf-8")
    (directory / "correlation_analysis_v3.json").write_text(
        '{"report_version": 3, "report": {}}', encoding="utf-8")

    saved = repo.save(CASE, "correlation_analysis", {"n": 9})

    assert sorted(p.name for p in directory.glob("correlation_analysis*.json")) == [
        "correlation_analysis.json"
    ]
    # The counter carries over from the legacy files rather than resetting.
    assert repo.load_latest(CASE, "correlation_analysis")["report_version"] == 4
    assert saved.name == "correlation_analysis.json"


def test_repository_text_and_pdf_keep_one_file(repo):
    p1 = repo.save_text(CASE, "investigation_report", "# one", ".md")
    p2 = repo.save_text(CASE, "investigation_report", "# two", ".md")
    assert p1 == p2 and p2.name == "investigation_report.md"
    assert p2.read_text(encoding="utf-8") == "# two"

    b1 = repo.save_binary(CASE, "investigation_report", b"%PDF-1", ".pdf")
    b2 = repo.save_binary(CASE, "investigation_report", b"%PDF-2", ".pdf")
    assert b1 == b2 and b2.name == "investigation_report.pdf"
    assert b2.read_bytes() == b"%PDF-2"


def test_audit_appends(audit):
    audit.record(CASE, "correlation", "analyzed", "ok", duration_ms=5.0)
    with open(audit.path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[-1]["module"] == "correlation"
    assert rows[-1]["case_id"] == CASE
