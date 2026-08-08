"""PDF report layout: the reader must get tables, and must lose nothing.

The PDF is the artifact that leaves the building — it is what a supervisor
prints and what a prosecutor reads — so these tests care about two things:

* **No information is dropped.** Every section now has a bespoke layout
  instead of a generic bullet dump, and a bespoke layout is exactly where a
  field quietly stops being rendered. The coverage test walks the section data
  and asserts each value reaches the page.
* **Nothing crashes on a shape it did not expect.** Report sections vary
  between artifact versions (some carry ``file_name``, some carry
  ``specificity``, some are empty). A renderer that raises would cost the
  whole report, so every renderer must degrade instead.
"""

from __future__ import annotations

import re

import pytest

from ciis_timeline_report.reporting import pdf_renderer

pytestmark = pytest.mark.skipif(
    not pdf_renderer.available(), reason="reportlab is not installed"
)

fitz = pytest.importorskip("fitz", reason="PyMuPDF needed to read the PDF back")


CASE = "CASE_PDF"


def sample_sections() -> dict:
    """A report exercising every specialised renderer at once."""
    return {
        "executive_summary": ["Nine exhibits were analysed.",
                              "Six indicators were flagged as malicious."],
        "case_overview": {"case_id": CASE, "evidence_count": 9},
        "evidence_summary": [
            {"evidence_id": "EVID_01", "file_name": "a.png",
             "upload_time": "2026-08-08T01:55:56", "ocr_confidence": 0.6,
             "hash_verified": True},
        ],
        "timeline_analysis": {
            "summary": "9 events spanning 1331 hours.",
            "stage_progression": ["initial_contact", "post_attack"],
            "progression_consistent": False,
            "milestones": [{"timestamp": "2026-06-14T00:00:00",
                            "description": "Investigation start"}],
            "critical_events": [{"timestamp": "2026-06-14T00:00:00",
                                 "evidence_id": "EVID_01",
                                 "reasons": ["contains money: NPR 25000"]}],
        },
        "correlation_analysis": {
            "pair_count": 36, "related_pair_count": 36,
            "strength_distribution": {"VERY_STRONG": 1, "WEAK": 26},
            "top_relationships": [
                {"pair": "EVID_01 <-> EVID_02", "strength": "VERY_STRONG",
                 "confidence": 0.9388, "explanation": "Both reference NPR 1500."},
            ],
        },
        "cross_case_correlation": {
            "related_case_count": 1, "related_case_ids": ["CASE_OTHER"],
            "links": [{"other_case_id": "CASE_OTHER",
                       "relationship_strength": "VERY_STRONG",
                       "match_confidence": 1.0,
                       "match_reason": "Shares 29 identifiers.",
                       "matched_entities": [
                           {"entity_type": "phones", "value": "+9779801122334",
                            "this_evidence_ids": ["EVID_01"],
                            "other_evidence_ids": ["EVID_99"]}]}],
        },
        "campaign_analysis": {
            "campaign_count": 1, "unclustered_evidence": ["EVID_07"],
            "campaigns": [{"campaign_id": "CAMP_01",
                           "members": ["EVID_01", "EVID_02"],
                           "confidence": 0.71,
                           "signature": ["domains:example.test"],
                           "summary": "Groups two exhibits."}],
        },
        "suspect_assessment": [
            {"suspect_id": "SUSPECT_01", "identity": "khalti_ids:+9779801122334",
             "confidence_score": 77.6, "confidence_level": "HIGH",
             "risk_level": "HIGH", "evidence_ids": ["EVID_01"],
             "explanation": "Anchor scores 77.6/100 across 1 evidence item."},
        ],
        "threat_intelligence_summary": {
            "intel_available": 1, "indicators_checked": 9,
            "malicious_indicators": 6, "suspicious_indicators": 2,
            "evidence_with_threats": 4, "threat_evidence_ratio": 0.44,
        },
        "model_predictions": {
            "indicators_classified": 1, "flagged_malicious": 1,
            "predictions": [{"indicator": "bad.test", "verdict": "malicious",
                             "risk_score": 100, "confidence": 1.0,
                             "source": "heuristics",
                             "reasons": ["impersonates a brand"]}],
        },
        "evidence_quality_summary": {
            "mean_image_quality": 70.0, "mean_evidence_confidence": 89.9,
            "mean_forgery_score": 12.0, "max_forgery_score": 25.2,
        },
        "metadata_summary": [
            {"evidence_id": "EVID_01", "has_exif": False, "device": "",
             "software": "", "consistency_notes": ["Image carries no EXIF"]},
        ],
        "investigation_statistics": {
            "entity_statistics": {"phones": 7}, "timeline_statistics": {"event_count": 9},
        },
        "confidence_analysis": [
            {"evidence_id": "EVID_01", "score": 83.6, "level": "VERY_HIGH",
             "explanation": "Confidence is 83.6/100 derived from 5 dimensions "
                            "and this string is deliberately long enough to be "
                            "treated as prose rather than a table column."},
        ],
        "investigation_conclusion": ["The case shows a coordinated operation."],
        "recommendations": ["Preserve the wallet records."],
        "appendix": {"chain_of_custody": [
            {"evidence_id": "EVID_01", "sha256": "a" * 64,
             "upload_time": "2026-08-08T01:55:56", "status": "processed"}]},
    }


def render(sections: dict) -> str:
    payload = pdf_renderer.render_pdf(
        CASE, sections, report_id="RPT-TEST", generated_at="2026-08-08T00:00:00Z")
    assert payload, "renderer produced no bytes"
    document = fitz.open(stream=payload, filetype="pdf")
    return re.sub(r"\s+", " ", "".join(page.get_text() for page in document))


def test_every_section_value_reaches_the_page():
    """No specialised layout may silently drop a field.

    This is the guard that matters: a bespoke renderer reads named keys, so a
    field the engine adds later — or one this layout forgot — simply stops
    being printed, and nothing else in the system notices.
    """
    sections = sample_sections()
    text = render(sections).lower()

    missing = []

    def check(value, path):
        if value is None or value == "":
            return
        if isinstance(value, dict):
            for k, v in value.items():
                check(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                check(v, f"{path}[{i}]")
        elif isinstance(value, bool):
            return  # rendered as yes/no or VERIFIED, checked elsewhere
        elif isinstance(value, (int, float)):
            f = float(value)
            forms = {str(int(f)) if abs(f - round(f)) < 1e-9 else f"{f:.2f}",
                     f"{f:.1f}", f"{f:.0f}", f"{f * 100:.0f}%"}
            if not any(form.lower() in text for form in forms):
                missing.append((path, value))
        else:
            # The layout reformats strings for the page, so a value counts as
            # present in any of the forms it is legitimately printed as:
            #   VERY_STRONG                -> "VERY STRONG"  (underscores)
            #   2026-06-14T00:00:00        -> "2026-06-14 00:00" (to minutes)
            #   khalti_ids:+97798011223    -> a Type and a Value column
            # Anything outside this set is a genuine drop.
            raw = str(value)
            forms = {raw, raw.replace("_", " "), raw[:16].replace("T", " ")}
            if ":" in raw:
                kind, _, ident = raw.partition(":")
                if ident:
                    forms.update({ident, kind.replace("_", " ")})
            if not any(f.lower() in text for f in forms if f):
                missing.append((path, value))

    for key, value in sections.items():
        check(value, key)

    assert not missing, f"values absent from the rendered PDF: {missing}"


def test_dense_sections_render_as_tables_not_bullet_runs():
    """Correlation and suspects must arrive as tables.

    Before this layout each pair emitted four sibling bullets, so a case with
    thirty-six pairs produced a column of a hundred and forty. The column
    headers are the cheapest reliable evidence that a table was drawn.
    """
    text = render(sample_sections())
    for header in ("Evidence pair", "Strength", "Confidence",
                   "Identifier", "Related case", "Indicator"):
        assert header in text, f"expected a table column named {header!r}"


def test_a_stage_with_no_event_count_prints_no_count():
    """Never print a figure the engine did not compute.

    The stage ribbon takes an optional count. The report data carries no
    per-stage counts, and printing "0 events" beside every stage would be a
    fabricated number in an evidentiary document.
    """
    text = render(sample_sections())
    assert "0 events" not in text


def test_renderers_degrade_instead_of_raising_on_unexpected_shapes():
    """A malformed section costs its layout, never the whole report."""
    broken = {
        "executive_summary": "a bare string, not the expected list",
        "correlation_analysis": {"top_relationships": "not a list"},
        "suspect_assessment": [{"identity": None, "confidence_score": None}],
        "cross_case_correlation": {"links": []},
        "campaign_analysis": {"campaigns": []},
        "timeline_analysis": {},
        "metadata_summary": [],
        "appendix": {"chain_of_custody": []},
    }
    text = render(broken)
    assert "Investigation Report" in text
    # The generic fallback still carried the unexpected value through.
    assert "a bare string" in text


def test_empty_sections_still_produce_a_complete_document():
    """An unanalysed case must still yield cover, contents and limitations."""
    text = render({})
    assert "Forensic Investigation Report" in text
    assert "Statement of Limitations" in text
    assert "End of report" in text
