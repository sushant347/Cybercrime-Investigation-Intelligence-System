"""Module 7 tests + full Phase-2 pipeline integration tests."""

from __future__ import annotations

import pytest

from backend.modules.evidence.utils import EvidenceError
from ciis_timeline_report.analytics.service import AnalyticsService
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.campaigns.service import CampaignService
from ciis_correlation.correlation.service import CorrelationService
from ciis_correlation.core.data_access import CaseDataRepository
from ciis_timeline_report.graph.service import GraphService
from ciis_timeline_report.pipeline import InvestigationPipeline
from ciis_timeline_report.prioritization.service import PrioritizationService
from ciis_timeline_report.reporting.service import InvestigationReportService
from ciis_correlation.core.repository import InvestigationReportRepository
from ciis_correlation.suspects.service import SuspectService
from ciis_timeline_report.timeline.service import TimelineService

from .conftest import CASE


@pytest.fixture()
def pipeline(icfg, data, repo, audit):
    return InvestigationPipeline(
        icfg,
        data=data,
        correlation=CorrelationService(icfg, data, repo, audit),
        graph=GraphService(icfg, data, repo, audit),
        campaigns=CampaignService(icfg, data, repo, audit),
        suspects=SuspectService(icfg, data, repo, audit),
        timeline=TimelineService(icfg, data, repo, audit),
        analytics=AnalyticsService(icfg, data, repo, audit),
        reporting=InvestigationReportService(icfg, data, repo, audit),
        prioritization=PrioritizationService(icfg, repo, audit),
        audit=audit,
    )


def test_full_pipeline_produces_all_artifacts(pipeline, icfg, repo):
    results = pipeline.analyze_case(CASE)
    assert results["failures"] == []
    for name in (icfg.correlation_report_name, icfg.graph_report_name,
                 icfg.graph_statistics_name, icfg.graph_summary_name,
                 icfg.campaign_report_name, icfg.suspect_report_name,
                 icfg.timeline_report_name, icfg.analytics_report_name,
                 icfg.case_statistics_name, icfg.entity_statistics_name,
                 icfg.investigation_report_name, icfg.priority_report_name):
        assert repo.load_latest(CASE, name) is not None, name
    md_versions = repo.list_versions(CASE, icfg.investigation_report_name, ".md")
    assert md_versions, "markdown report missing"


def test_report_references_findings_not_hallucinations(pipeline, icfg, repo):
    results = pipeline.analyze_case(CASE)
    markdown = results["report"]["markdown"]
    # every substantive claim is grounded in computed artefacts
    assert CASE in markdown
    assert "EVID_A" in markdown and "EVID_B" in markdown
    assert "+9779812345678" in markdown          # suspect anchor from data
    assert "campaign_analysis.json" in markdown     # findings referenced
    assert "scam-bank.top" in markdown
    # The report keeps the complete 21-section contract in one stable order.
    for title in ("Executive Summary", "Case Overview", "Evidence Summary",
                  "Correlation Analysis", "Campaign Analysis",
                  "Timeline Analysis", "Suspect Assessment",
                  "Threat Intelligence Summary", "Evidence Quality Summary",
                  "Metadata Summary", "Investigation Statistics",
                  "Confidence Analysis", "Investigation Conclusion",
                  "Recommendations", "Appendix"):
        assert f"## {title}" in markdown, title


def test_report_marks_missing_inputs_explicitly(icfg, data, repo, audit):
    service = InvestigationReportService(icfg, data, repo, audit)
    result = service.generate(CASE, persist=False)
    markdown = result["markdown"]
    assert "not available" in markdown  # no invented correlation/campaign data


def test_report_exposes_timestamp_provenance_and_avoids_attribution(pipeline):
    pipeline_result = pipeline.analyze_case(CASE)
    result = pipeline_result["report"]
    sections = result["sections"]
    timeline = sections["timeline_analysis"]

    assert len(timeline["chronological_events"]) == 4
    assert all(
        {"timestamp", "evidence_id", "timestamp_source",
         "timestamp_confidence", "timestamp_inferred"} <= set(event)
        for event in timeline["chronological_events"]
    )
    assert "reliability_note" in timeline["timestamp_quality"]
    assert sections["limitations"]

    report_text = " ".join(
        sections["executive_summary"] + sections["investigation_conclusion"]
    ).lower()
    assert "identity lead" in report_text
    assert "not identity attribution" in report_text
    assert "coordinated operation." not in report_text
    assert "automated analytical draft" in result["markdown"].lower()
    assert "| timestamp (utc) | evidence |" in result["markdown"].lower()
    assert "| identity lead | score |" in result["markdown"].lower()
    assert "suspect_id" not in result["markdown"]
    assert "| # | Finding |" in result["markdown"]
    assert "| Stage | Method and stored output |" in result["markdown"]
    assert "| Evidence | File | Acquired | OCR confidence | Entities | Integrity |" in result["markdown"]
    assert sections["investigation_statistics"]["timeline_statistics"] == (
        pipeline_result["timeline"].statistics
    )


def test_report_separates_offences_from_source_backed_follow_up(pipeline):
    result = pipeline.analyze_case(CASE)["report"]
    legal = result["sections"]["legal_basis"]

    assert legal["sources"]
    assert {item["section"] for item in legal["manual_review_provisions"]} == {
        "44", "48", "57"
    }
    assert legal["investigative_guidance"]
    assert all(
        item["status"] in {
            "evidence_handling_requirement", "investigative_follow_up"
        }
        for item in legal["investigative_guidance"]
    )
    assert "Evidentiary and regulatory follow-up" in result["markdown"]
    assert "not findings that an institution violated a rule" in result["markdown"]
    assert "Primary sources" in result["markdown"]
    assert "| Field | Recorded value |" in result["markdown"]
    assert "Evidence-based match" in result["markdown"]


def test_one_failing_module_does_not_abort(pipeline, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("campaign module exploded")

    monkeypatch.setattr(pipeline._campaigns, "cluster", boom)
    results = pipeline.analyze_case(CASE)
    assert any("campaigns" in f for f in results["failures"])
    assert results["report"] is not None
    assert results["priority"] is not None


def test_unknown_case_raises(pipeline):
    with pytest.raises(EvidenceError):
        pipeline.analyze_case("CASE_0000")


def test_reanalysis_replaces_rather_than_accumulates(pipeline, icfg, repo):
    """Two analyses leave one artifact per report, not one per run."""
    pipeline.analyze_case(CASE)
    pipeline.analyze_case(CASE)

    versions = repo.list_versions(CASE, icfg.correlation_report_name)
    assert len(versions) == 1
    assert versions[0].name == "correlation_analysis.json"
    # The run counter lives inside the document, not in the file name.
    assert repo.load_latest(CASE, icfg.correlation_report_name)["report_version"] == 2

    # The same holds for the report's Markdown and PDF twins.
    for suffix in (".md", ".pdf"):
        stored = repo.list_versions(CASE, icfg.investigation_report_name, suffix)
        assert len(stored) <= 1, f"{suffix} artifacts accumulated: {stored}"
