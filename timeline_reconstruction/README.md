# Timeline Reconstruction

**Module 5** of the Cybercrime Investigation Intelligence System (CIIS).

This module resolves the best available timestamp for every piece of
evidence and orders it into a chronological narrative, cross-referenced
with the correlation links found by Module 4.

```text
Stored OCR/entity evidence + correlation analysis
        ↓
Timeline Reconstruction (this module)
        ↓
timeline_analysis.json + graph.json
        ↓
Frontend timeline and graph views
```

## The Core Problem It Solves

A file's `upload_time` (when it was processed by the system) is often
*not* when the underlying event actually happened. A screenshot of a chat
message sent last week might get uploaded to the investigation system
today. If you sort evidence by upload time alone, the timeline reflects
investigator workflow, not the actual sequence of events — which is what
actually matters for a case.

This module tries harder than that. For every evidence item, it looks for
a timestamp in three places, in order of trust:

1. **Structured date + time entities** already extracted by Module 2
   (`cleaning.entities.dates` / `.times`) — highest confidence, since
   these come from explicit content in the evidence.
2. **A time entity with no date** — combined with the evidence's upload
   date as a best guess (medium confidence; the day is assumed, not
   confirmed).
3. **Inline chat-app timestamps** embedded in the raw OCR text that
   Module 2's entity extractor didn't catch — e.g. `"12-05, 11:23:np"`
   style timestamps common in messaging app screenshots. Caught via a
   dedicated regex fallback (medium confidence).
4. **`upload_time` fallback** — used only when nothing above is available
   (low confidence, explicitly labeled as such so investigators know this
   is a system timestamp, not a content timestamp).

If literally nothing is available, the event is marked `unresolved` and
sorted to the end of the timeline rather than being guessed into a
misleading position.

### Year handling for partial timestamps

Chat-style timestamps like `12-05, 11:23` have no year. The module assumes
the same year as the evidence's upload time, then rolls back one year if
that would place the event *after* the upload — since a message has to be
sent before a screenshot of it can be taken and uploaded.

## Usage

```bash
python timeline_reconstruction.py case1.json
python timeline_reconstruction.py case1.json case2.json --correlation output/correlation_graph.json
```

Passing `--correlation` is optional but recommended — without it, the
timeline is just a sorted list; with it, each entry also shows what other
evidence it's linked to and why (from Module 4), turning the timeline into
an actual investigative narrative.

Or import directly:

```python
from timeline_reconstruction import build_timeline, generate_narrative, load_case, load_correlation_graph

cases = [load_case("case1.json")]
graph = load_correlation_graph("output/correlation_graph.json")
timeline = build_timeline(cases, graph)
narrative = generate_narrative(timeline)
```

In the running application, the investigation pipeline calls the integrated
`TimelineService`, which is a thin adapter to this engine. After a new evidence
upload completes OCR and semantic entity extraction, the API automatically
refreshes the timeline and graph artifacts for the case.

## Output

### `timeline.json`

```json
{
  "total_events": 3,
  "resolved_count": 3,
  "unresolved_count": 0,
  "timeline": [
    {
      "evidence_id": "EVID_00031",
      "case_id": "CASE_0021",
      "file_name": "messenger_chat_screenshot.jpg",
      "resolved_time": "2026-07-08T18:12:00+00:00",
      "time_source": "upload_time_fallback",
      "confidence": "low",
      "text_preview": "Rajesh Thapa\nनमस्ते dai, esewa ma paisa pathaideu na...",
      "risk_signals": {"urgency": 1, "financial": 1, "credential": 0, "threat": 0},
      "correlated_with": [
        {
          "linked_to": "EVID_00032",
          "type": "shared_entity",
          "shared_entities": [{"value": "9841122334", "type": "phones"}],
          "weight": 2.0
        }
      ]
    }
  ]
}
```

### `timeline_narrative.txt`

A flat, human-readable rendering of the same data, one line per event:

```text
[2026-07-08T18:12:00+00:00] messenger_chat_screenshot.jpg (evidence EVID_00031) (confidence: low) -- correlated with: EVID_00032 -- risk signals: urgency, financial
[2026-07-08T19:45:00+00:00] esewa_payment_request.jpg (evidence EVID_00032) (confidence: low) -- correlated with: EVID_00031 -- risk signals: financial
```

This narrative form is meant to be consumed directly by Module 6 as the
backbone of the investigation report.

## Design Notes

- **Confidence is always surfaced, never hidden.** Every timeline entry
  says exactly how its timestamp was derived (`content_date_time`,
  `content_time_only`, `content_chat_timestamp`, or
  `upload_time_fallback`). This matters for forensic credibility — an
  investigator should never mistake a system-generated timestamp for
  content evidence of when something happened.
- **Unresolved events are never dropped.** They're kept in the timeline,
  sorted to the end, rather than silently excluded — missing evidence
  should be visible, not hidden.
- **Correlation context is pulled in, not recomputed.** This module trusts
  Module 4's correlation graph rather than re-deriving relationships, to
  keep the two modules cleanly separated.

## Tested Against

- All four timestamp resolution paths verified independently: structured
  date+time entities, time-only entities combined with upload date, inline
  chat-style timestamp regex extraction, and the year-rollback logic for
  partial dates.
- Full chain tested end-to-end against Module 4's real output
  (`case_0021_test.json` → `correlation_engine.py` →
  `timeline_reconstruction.py`), confirming correlated evidence is
  correctly cross-referenced in the resulting timeline and unrelated
  evidence is placed independently by its own timestamp.

## Known Limitation

The current chat-timestamp regex handles the `MM-DD, HH:MM[:label]`
pattern seen in the messaging-app screenshots tested so far. Other apps
use different formats (e.g. `"Yesterday 3:45 PM"`, `"Jul 8 at 6:12 PM"`).
Extending the regex/parser coverage as new evidence formats show up is the
main way this module should grow before Module 6 depends on it heavily.

## Next Steps

**Module 6 (Report Generator)** consumes `timeline_narrative.txt` and
`timeline.json` directly, alongside Module 4's `entity_index` and Module
3's threat scores, to produce the final investigator-facing report.
