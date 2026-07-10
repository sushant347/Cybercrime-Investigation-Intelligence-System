# Module 6 - Report Generator

Cybercrime Investigation Intelligence System (CIIS)

Generates a human-readable Markdown investigation report from Module 5's
`timeline.json`. Every line in the report is template-generated from a
specific field in the timeline data (no free-form/LLM generation), so it
stays traceable for evidentiary use.

## What it does

Takes `timeline.json` (produced by Module 5 - Timeline Reconstruction) and
produces a report (PDF by default, Markdown optional) containing:

1. **Report Metadata** - a report ID, generation timestamp, investigator
   name, and a SHA-256 hash of the source `timeline.json`, so a given
   report can always be tied back to the exact evidence-timeline snapshot
   it was built from
2. **Overview** - total evidence items, resolved/unresolved counts, case
   breakdown, timestamp confidence breakdown
3. **Risk Signal Highlights** - evidence items with active risk signals,
   pulled to the front so they aren't buried in the full timeline
4. **Correlation Highlights** - evidence items linked to others (from
   Module 4's correlation graph, as carried through by Module 5)
5. **Chronological Narrative** - the full timeline, grouped by case if more
   than one case is present, with text previews, correlation notes, and
   risk flags inline
6. **Confidence & Caveats** - explains what high/medium/low/none confidence
   actually means, and flags how many items have low or unresolved
   timestamps

PDF output also includes page numbers ("Page X of Y") and the report ID
in the footer of every page.

## Requirements

- Python 3.8+
- `reportlab` (only needed for PDF output — the default format)
  ```bash
  pip install reportlab
  ```
- Markdown output (`--format md`) needs no third-party packages.

## Usage

```bash
python report_generator.py <path-to-timeline.json> [--case CASE_ID] [--format pdf|md] [--output OUTPUT_PATH]
```

**Arguments:**

| Argument         | Required | Description                                                        |
|------------------|----------|----------------------------------------------------------------------|
| `timeline`       | yes      | Path to `timeline.json` from Module 5                              |
| `--case`         | no       | Restrict the report to a single `case_id`                          |
| `--format`       | no       | `pdf` (default) or `md`                                            |
| `--output`       | no       | Output path (default: `output/report.pdf` or `output/report.md`)   |
| `--investigator` | no       | Name/ID recorded on the report (default: "Unspecified")            |
| `--report-id`    | no       | Custom report ID (default: auto-generated, e.g. `RPT-XXXXXXXXXX`)  |

### Examples

Generate a PDF report from Module 5's default output location:

```bash
python report_generator.py ../timeline_reconstruction/output/timeline.json
```

Restrict to one case, with a custom output path and investigator name:

```bash
python report_generator.py output/timeline.json --case CASE-A \
    --output output/case_a_report.pdf --investigator "J. Rai"
```

Generate the Markdown version instead:

```bash
python report_generator.py output/timeline.json --format md --output output/report.md
```

## Checking the output

Run the script, then open the generated PDF:

```bash
# Run it (PDF is the default format)
python report_generator.py output/timeline.json

# Confirm it was created
ls -la output/report.pdf

# Open it (Linux)
xdg-open output/report.pdf

# Open it (macOS)
open output/report.pdf

# Or extract its text to sanity-check contents from the terminal
pdftotext -layout output/report.pdf - | less
```

If you passed `--output`, check that path instead of `output/report.pdf`.
For the Markdown format, just `cat output/report.md` or open it in any
Markdown viewer.

A successful run prints three lines to stdout:

```
Generated report -> output/report.pdf
Report ID: RPT-D6CE43E14A
Source SHA-256: 7d27adb78bac475aba6efba8e2a3e21b0a67b06ba24e4dce48c9e17b9d26f434
```

The Report ID and source hash are also embedded in the report itself
(metadata block on page 1, and the report ID appears in the PDF footer of
every page), so a printed or forwarded copy can still be traced back to
the exact `timeline.json` it came from.

## Quick self-test (no real data required)

You can sanity-check the script against a small hand-built `timeline.json`
that matches Module 5's schema:

```bash
cat > test_timeline.json << 'EOF'
{
  "total_events": 1,
  "resolved_count": 1,
  "unresolved_count": 0,
  "timeline": [
    {
      "evidence_id": "EVID-001",
      "case_id": "CASE-A",
      "file_name": "example.png",
      "resolved_time": "2025-12-04T22:02:00",
      "time_source": "content_chat_timestamp",
      "confidence": "medium",
      "text_preview": "example text",
      "risk_signals": {"financial_terms": true},
      "correlated_with": []
    }
  ]
}
EOF

python report_generator.py test_timeline.json --output test_report.pdf
xdg-open test_report.pdf   # or: open test_report.pdf on macOS
```

If the PDF opens without errors and shows the expected sections above,
the module is working correctly.

## Known limitations

- Report content is entirely template-driven from `timeline.json` fields;
  it does not re-derive or verify anything from the original evidence
  files.
- If Module 5 was run without `--correlation`, the "Correlation Highlights"
  section will simply report that no correlations were found.
- PDF and Markdown are the only supported formats. Convert externally
  (e.g. pandoc) if another format is needed.

## Where this fits in the pipeline

```
Module 2 (OCR/Evidence)  --->  Module 4 (Correlation)  --->  Module 5 (Timeline)  --->  Module 6 (Report)  --->  Module 8 (Dashboard, planned)
```
