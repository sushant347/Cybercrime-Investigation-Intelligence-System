from __future__ import annotations

import unittest

from ciis_timeline_report.timeline.engine import build_timeline


class TimelineReconstructionTests(unittest.TestCase):
    def test_order_inference_missing_relationships_and_duplicates(self):
        cases = [{
            "case_id": "CASE_A",
            "evidence": [
                {
                    "evidence_id": "EVID_LATE",
                    "file_name": "late.png",
                    "upload_time": "2026-07-10T18:00:00Z",
                    "raw_text": "send money now",
                    "cleaning": {"entities": {
                        "dates": [{"normalized": "2026-07-03"}],
                        "times": [{"normalized": "14:30"}],
                        "phones": [{"normalized": "9812345678"}],
                    }},
                },
                {
                    "evidence_id": "EVID_INFERRED",
                    "file_name": "inferred.png",
                    "upload_time": "2026-07-02T10:00:00Z",
                    "raw_text": "hello",
                    "cleaning": {"entities": {}},
                },
                {
                    "evidence_id": "EVID_MISSING",
                    "file_name": "missing.png",
                    "raw_text": "timestamp absent",
                    "cleaning": {"entities": {}},
                },
                {
                    "evidence_id": "EVID_INFERRED",
                    "file_name": "duplicate.png",
                    "upload_time": "2026-07-20T10:00:00Z",
                    "raw_text": "duplicate",
                    "cleaning": {"entities": {}},
                },
            ],
        }]
        correlation = {"edges": [{
            "source": "evidence:EVID_INFERRED",
            "target": "evidence:EVID_LATE",
            "type": "shared_entity",
            "confidence": 0.9,
        }]}

        result = build_timeline(
            cases,
            correlation,
            stage_keywords={"financial_transaction": ("send money",)},
            stage_order=("financial_transaction",),
            critical_entity_types=("phones",),
        )

        self.assertEqual(
            [event["evidence_id"] for event in result["events"]],
            ["EVID_INFERRED", "EVID_LATE", "EVID_MISSING"],
        )
        actual = result["events"][1]
        self.assertEqual(actual["time_source"], "content_date_time")
        self.assertFalse(actual["timestamp_inferred"])
        inferred = result["events"][0]
        self.assertEqual(inferred["time_source"], "upload_time_fallback")
        self.assertTrue(inferred["timestamp_inferred"])
        missing = result["events"][2]
        self.assertEqual(missing["timestamp"], "")
        self.assertEqual(missing["time_source"], "unresolved")
        self.assertEqual(inferred["correlated_with"][0]["linked_to"], "EVID_LATE")
        self.assertEqual(inferred["correlated_with"][0]["confidence"], 0.9)
        self.assertEqual(result["statistics"]["event_count"], 3.0)

    def test_full_chat_timestamp_is_actual_without_upload_time(self):
        result = build_timeline([{
            "case_id": "CASE_CHAT",
            "evidence": [{
                "evidence_id": "EVID_CHAT",
                "file_name": "chat.txt",
                "raw_text": "[11/06/2026, 9:41 PM] Suspect: send OTP",
                "cleaning": {"entities": {}},
            }],
        }])

        event = result["events"][0]
        self.assertEqual(event["timestamp"], "2026-06-11T21:41:00+00:00")
        self.assertEqual(event["time_source"], "content_chat_timestamp")
        self.assertFalse(event["timestamp_inferred"])
        self.assertEqual(event["confidence"], "high")

    def test_named_content_date_and_time_are_parsed(self):
        result = build_timeline([{
            "case_id": "CASE_DATE",
            "evidence": [{
                "evidence_id": "EVID_DATE",
                "raw_text": "Payment completed",
                "cleaning": {"entities": {
                    "dates": [{"normalized": "11 June 2026"}],
                    "times": [{"normalized": "14:30"}],
                }},
            }],
        }])

        event = result["events"][0]
        self.assertEqual(event["timestamp"], "2026-06-11T14:30:00+00:00")
        self.assertFalse(event["timestamp_inferred"])

    def test_exif_creation_time_beats_upload_fallback(self):
        result = build_timeline([{
            "case_id": "CASE_META",
            "evidence": [{
                "evidence_id": "EVID_META",
                "upload_time": "2026-08-01T10:00:00Z",
                "raw_text": "No visible timestamp",
                "cleaning": {"entities": {}},
                "metadata": {
                    "image": {"date_created": "2026:06:11 08:15:30"}
                },
            }],
        }])

        event = result["events"][0]
        self.assertEqual(event["timestamp"], "2026-06-11T08:15:30+00:00")
        self.assertEqual(event["time_source"], "metadata_exif_created")
        self.assertFalse(event["timestamp_inferred"])

    def test_compact_ocr_iso_datetime_does_not_backtrack_into_bad_year(self):
        result = build_timeline([{
            "case_id": "CASE_COMPACT",
            "evidence": [{
                "evidence_id": "EVID_COMPACT",
                "upload_time": "2026-08-01T10:00:00Z",
                "raw_text": "Date & Time\n2026-06-1110:42AM\nStatus: complete",
                "cleaning": {"entities": {}},
            }],
        }])

        event = result["events"][0]
        self.assertEqual(event["timestamp"], "2026-06-11T10:42:00+00:00")
        self.assertEqual(event["time_source"], "content_labeled_date_time")
        self.assertFalse(event["timestamp_inferred"])
        self.assertEqual(event["confidence"], "high")

    def test_labelled_document_date_beats_earlier_narrative_entity(self):
        result = build_timeline([{
            "case_id": "CASE_LABEL",
            "evidence": [{
                "evidence_id": "EVID_LABEL",
                "upload_time": "2026-08-01T10:00:00Z",
                "raw_text": (
                    "The incident began on 10 June 2026.\n"
                    "Date of Report: 15 June 2026"
                ),
                "cleaning": {"entities": {
                    "dates": [
                        {"normalized": "10 June 2026"},
                        {"normalized": "15 June 2026"},
                    ],
                }},
            }],
        }])

        event = result["events"][0]
        self.assertEqual(event["timestamp"], "2026-06-15T00:00:00+00:00")
        self.assertEqual(event["time_source"], "content_labeled_date_only")
        self.assertTrue(event["timestamp_inferred"])
        self.assertEqual(event["confidence"], "medium")

    def test_implausible_chat_year_is_rejected(self):
        result = build_timeline([{
            "case_id": "CASE_BAD_YEAR",
            "evidence": [{
                "evidence_id": "EVID_BAD_YEAR",
                "upload_time": "2026-08-01T10:00:00Z",
                "raw_text": "26-06-1110:42AM",
                "cleaning": {"entities": {}},
            }],
        }])

        event = result["events"][0]
        self.assertEqual(event["timestamp"], "2026-08-01T10:00:00+00:00")
        self.assertEqual(event["time_source"], "upload_time_fallback")
        self.assertTrue(event["timestamp_inferred"])


if __name__ == "__main__":
    unittest.main()
