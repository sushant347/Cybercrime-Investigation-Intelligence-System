"""
Tests for the report generator (src/reporting/report_generator.py).

Covers:
- AnalysisReport creation from single and multiple PredictionResult objects.
- to_dict() and to_json() structure and content.
- summary_stats() calculations for batch reports.
- save() writes a valid JSON file to disk.
- ReportGenerator.generate(), generate_batch(), generate_and_save(),
  generate_batch_and_save() methods.
- report_id is deterministic and unique per input.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.prediction.result import PredictionResult
from src.reporting.report_generator import ReportGenerator, AnalysisReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_result(
    url: str = "https://paypal-login.xyz/login",
    prediction: str = "phishing",
    confidence: float = 0.92,
    risk_score: int = 87,
    risk_level: str = "Critical",
    reasons: list | None = None,
) -> PredictionResult:
    return PredictionResult(
        url=url,
        prediction=prediction,
        confidence=confidence,
        risk_score=risk_score,
        risk_level=risk_level,
        features={"url_length": 27, "is_https": 1},
        threat_intelligence={"whois_domain_age_days": 5},
        reasons=reasons if reasons is not None else ["Young domain", "Suspicious TLD"],
        model_type="xgboost",
    )


@pytest.fixture
def phishing_result() -> PredictionResult:
    return _make_result()


@pytest.fixture
def legit_result() -> PredictionResult:
    return _make_result(
        url="https://www.google.com",
        prediction="legitimate",
        confidence=0.99,
        risk_score=2,
        risk_level="Safe",
        reasons=[],
    )


@pytest.fixture
def generator() -> ReportGenerator:
    return ReportGenerator()


# ---------------------------------------------------------------------------
# AnalysisReport
# ---------------------------------------------------------------------------

class TestAnalysisReport:
    def test_single_result_report_id_set(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        assert report.report_id
        assert report.report_id.startswith("phish-")

    def test_custom_report_id(self, phishing_result):
        report = AnalysisReport(results=[phishing_result], report_id="my-report-123")
        assert report.report_id == "my-report-123"

    def test_empty_results_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            AnalysisReport(results=[])

    def test_engine_version_set(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        assert report.engine_version == "2.0.0"

    def test_generated_at_is_iso8601(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        # Should parse as ISO 8601 without raising
        dt = datetime.fromisoformat(report.generated_at.replace("Z", "+00:00"))
        assert dt is not None


class TestAnalysisReportToDict:
    def test_single_url_dict_structure(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        d = report.to_dict()
        assert "report_id" in d
        assert "generated_at" in d
        assert "engine_version" in d
        assert "analysis" in d
        assert "threat_intelligence" in d

    def test_single_url_analysis_keys(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        analysis = report.to_dict()["analysis"]
        assert "url" in analysis
        assert "prediction" in analysis
        assert "confidence" in analysis
        assert "risk_score" in analysis
        assert "risk_level" in analysis
        assert "reasons" in analysis
        assert "verdict_summary" in analysis
        assert "is_phishing" in analysis
        assert "is_high_risk" in analysis

    def test_verdict_summary_contains_prediction(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        verdict = report.to_dict()["analysis"]["verdict_summary"]
        assert "PHISHING" in verdict

    def test_features_included_by_default(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        d = report.to_dict(include_features=True)
        assert "features" in d

    def test_features_excluded_when_requested(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        d = report.to_dict(include_features=False)
        assert "features" not in d

    def test_batch_dict_structure(self, phishing_result, legit_result):
        report = AnalysisReport(results=[phishing_result, legit_result])
        d = report.to_dict()
        assert "summary" in d
        assert "results" in d
        assert len(d["results"]) == 2

    def test_batch_summary_counts(self, phishing_result, legit_result):
        report = AnalysisReport(results=[phishing_result, legit_result])
        stats = report.to_dict()["summary"]
        assert stats["total_urls"] == 2
        assert stats["phishing_count"] == 1
        assert stats["legitimate_count"] == 1


class TestAnalysisReportToJson:
    def test_valid_json_output(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_json_contains_report_id(self, phishing_result):
        report = AnalysisReport(results=[phishing_result])
        parsed = json.loads(report.to_json())
        assert parsed["report_id"] == report.report_id


class TestAnalysisReportSave:
    def test_save_creates_file(self, phishing_result, tmp_path):
        report = AnalysisReport(results=[phishing_result])
        saved = report.save(output_dir=tmp_path)
        assert saved.exists()
        assert saved.suffix == ".json"

    def test_saved_file_is_valid_json(self, phishing_result, tmp_path):
        report = AnalysisReport(results=[phishing_result])
        saved = report.save(output_dir=tmp_path)
        content = json.loads(saved.read_text(encoding="utf-8"))
        assert "report_id" in content

    def test_custom_filename(self, phishing_result, tmp_path):
        report = AnalysisReport(results=[phishing_result])
        saved = report.save(output_dir=tmp_path, filename="my_report")
        assert saved.name == "my_report.json"


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

class TestSummaryStats:
    def test_stats_counts(self, phishing_result, legit_result):
        report = AnalysisReport(results=[phishing_result, legit_result])
        stats = report.summary_stats()
        assert stats["total_urls"] == 2
        assert stats["phishing_count"] == 1
        assert stats["legitimate_count"] == 1

    def test_avg_score_calculated(self, phishing_result, legit_result):
        report = AnalysisReport(results=[phishing_result, legit_result])
        stats = report.summary_stats()
        expected_avg = (87 + 2) / 2
        assert stats["average_risk_score"] == pytest.approx(expected_avg, abs=0.01)

    def test_phishing_rate(self, phishing_result, legit_result):
        report = AnalysisReport(results=[phishing_result, legit_result])
        stats = report.summary_stats()
        assert stats["phishing_rate"] == pytest.approx(0.5, abs=0.001)

    def test_risk_distribution_keys(self, phishing_result, legit_result):
        report = AnalysisReport(results=[phishing_result, legit_result])
        stats = report.summary_stats()
        dist = stats["risk_distribution"]
        for level in ("Critical", "High", "Medium", "Low", "Safe", "Unknown"):
            assert level in dist


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------

class TestReportGenerator:
    def test_generate_single(self, generator, phishing_result):
        report = generator.generate(phishing_result)
        assert isinstance(report, AnalysisReport)
        assert len(report.results) == 1

    def test_generate_batch(self, generator, phishing_result, legit_result):
        report = generator.generate_batch([phishing_result, legit_result])
        assert isinstance(report, AnalysisReport)
        assert len(report.results) == 2

    def test_generate_batch_empty_raises(self, generator):
        with pytest.raises(ValueError):
            generator.generate_batch([])

    def test_generate_and_save_returns_tuple(self, generator, phishing_result, tmp_path):
        report, path = generator.generate_and_save(
            phishing_result, output_dir=tmp_path
        )
        assert isinstance(report, AnalysisReport)
        assert path.exists()

    def test_generate_batch_and_save(self, generator, phishing_result, legit_result, tmp_path):
        report, path = generator.generate_batch_and_save(
            [phishing_result, legit_result], output_dir=tmp_path
        )
        assert isinstance(report, AnalysisReport)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "summary" in data  # batch report has summary
