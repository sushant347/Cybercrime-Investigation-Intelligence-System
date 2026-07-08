"""
Reporting package for the Phishing URL Detection Engine.

Generates structured JSON reports from ``PredictionResult`` objects.
"""

from src.reporting.report_generator import ReportGenerator, AnalysisReport

__all__ = ["ReportGenerator", "AnalysisReport"]
