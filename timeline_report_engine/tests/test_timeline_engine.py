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


if __name__ == "__main__":
    unittest.main()
