"""Single-evidence deletion and the processing-state gate that guards it.

Deleting evidence is the one destructive action an ordinary user can take, so
what it removes - and, more importantly, what it refuses to remove - is pinned
here rather than left to the view layer.
"""

from __future__ import annotations

import csv
import json

from backend.modules.investigation.maintenance import (
    delete_evidence,
    evidence_processing_state,
)

from .conftest import CASE


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ------------------------------------------------------------ state detection


def test_processed_item_is_reported_as_processed(config, icfg):
    """EVID_A has OCR text, entities and forensic reports in the fixture."""
    state = evidence_processing_state(config, icfg, "EVID_A")
    assert state["exists"] is True
    assert state["processed"] is True
    assert state["has_ocr_text"] is True
    assert state["entity_count"] == 4
    assert state["has_forensics"] is True


def test_unknown_item_reports_not_existing(config, icfg):
    assert evidence_processing_state(config, icfg, "EVID_NOPE") == {"exists": False}


def test_item_with_no_findings_is_deletable(config, icfg):
    """An upload that produced nothing: no entities, no text, no reports."""
    with open(config.evidence_csv, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_rows(config.evidence_csv)[0].keys())
        writer.writerow({
            "evidence_id": "EVID_NEW", "case_id": CASE,
            "original_file_name": "broken.png",
            "stored_file_name": "EVID_NEW__x__broken.png",
            "file_extension": ".png", "file_size_bytes": "10",
            "sha256_before": "e" * 64, "sha256_after": "", "hash_verified": "",
            "upload_time": "2026-07-06T09:00:00.000Z", "processing_time": "",
            "status": "failed", "investigator_notes": "",
        })
    state = evidence_processing_state(config, icfg, "EVID_NEW")
    assert state["exists"] is True
    assert state["processed"] is False


# ------------------------------------------------------------------ deletion


def test_delete_removes_every_trace(config, icfg):
    stored = config.originals_dir / "EVID_A__x__chat_offer.png"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"binary evidence")

    summary = delete_evidence(config, icfg, "EVID_A")

    assert summary["deleted"] is True
    assert summary["case_id"] == CASE
    # register row gone, siblings untouched
    remaining = {r["evidence_id"] for r in _rows(config.evidence_csv)}
    assert remaining == {"EVID_B", "EVID_C", "EVID_D"}
    # entity rows gone
    assert all(r["evidence_id"] != "EVID_A" for r in _rows(icfg.entities_csv))
    # stored original and forensic reports gone
    assert not stored.exists()
    assert not (icfg.forensics_dir / "EVID_A").exists()
    # the case JSON no longer carries the item, and its count is corrected
    document = json.loads((config.json_dir / f"{CASE}.json").read_text(encoding="utf-8"))
    assert [i["evidence_id"] for i in document["evidence"]] == [
        "EVID_B", "EVID_C", "EVID_D",
    ]
    assert document["evidence_count"] == 3


def test_delete_is_a_no_op_for_an_unknown_id(config, icfg):
    before = _rows(config.evidence_csv)
    summary = delete_evidence(config, icfg, "EVID_NOPE")
    assert summary["deleted"] is False
    assert _rows(config.evidence_csv) == before


def test_delete_never_touches_another_case(config, icfg):
    """Other cases' entity rows survive: the filter is keyed on evidence id."""
    with open(icfg.entities_csv, "a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            ["CASE_OTHER", "EVID_X", "phones", "9800000000", "+9779800000000",
             "2026-07-05T00:00:00.000Z"]
        )
    delete_evidence(config, icfg, "EVID_A")
    assert any(r["case_id"] == "CASE_OTHER" for r in _rows(icfg.entities_csv))
