"""Report-correctness review harness (Table 6.7) — scoring math + template build."""

import importlib.util

import pytest

from ciis_correlation import CORRELATION_ENGINE_ROOT

#: The harness is a script rather than an importable module, so it is loaded
#: by path. Resolved from the engine root the package already knows about,
#: not by counting directories up from this file.
_SCRIPT = str(CORRELATION_ENGINE_ROOT / "scripts" / "report_review.py")
_spec = importlib.util.spec_from_file_location("report_review", _SCRIPT)
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)


def test_template_lists_gradeable_claims():
    report = {"case_id": "C1", "report_version": 2, "report": {"sections": {
        "executive_summary": ["A", "B"],
        "investigation_conclusion": ["C"],
        "recommendations": ["D"],
    }}}
    tmpl = rr.build_review_template(report, [{"evidence_id": "E1"}])
    assert tmpl["case_id"] == "C1"
    assert len(tmpl["items"]) == 4  # 2 exec + 1 concl + 1 rec
    assert all(it["verdict"] == "" for it in tmpl["items"])  # blank until graded


def test_score_weights_partial_as_half():
    filled = {"case_id": "C1", "items": [
        {"id": "a", "verdict": "correct"},
        {"id": "b", "verdict": "partial"},
        {"id": "c", "verdict": "incorrect"},
        {"id": "d", "verdict": ""},  # ungraded -> excluded
    ]}
    result = rr.score_review(filled)
    assert result["graded_items"] == 3
    assert result["ungraded_items"] == 1
    assert result["correctness_rate"] == pytest.approx((1 + 0.5 + 0) / 3)
    assert result["breakdown"] == {"correct": 1, "partial": 1, "incorrect": 1}


def test_score_refuses_when_nothing_graded():
    with pytest.raises(ValueError):
        rr.score_review({"items": [{"id": "a", "verdict": ""}]})
