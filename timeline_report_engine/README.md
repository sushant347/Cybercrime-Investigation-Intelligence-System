# Timeline & Report Engine

The terminal stage of the CIIE pipeline. Takes the relationships found by the
correlation engine and produces what an investigator actually reads: an attack
timeline, a relationship graph, case statistics, a priority band, and a
forensic report.

Every sentence in a report is templated over a concrete stored value. There is
no free-text generation anywhere in this module, so a report cannot state
something the analysis did not compute — missing inputs render an explicit
"not available" instead.

## Where this sits

```
evidence_ocr_engine → evidence_correlation_engine → timeline_report_engine
                                                            (this)
```

It imports the correlation engine — models, `InvestigationConfig`, the
read-only storage gateway, the versioned repository and the audit trail — and
through it the OCR engine. Neither imports back. Importing
`ciis_timeline_report` bootstraps both upstream roots onto `sys.path`;
`CIIS_CORRELATION_ROOT` overrides where it looks.

## Layout

```
ciis_timeline_report/
├── timeline/
│   ├── engine.py       framework-independent reconstruction algorithm:
│   │                   timestamp resolution, ordering, de-duplication,
│   │                   attack stages, milestones, critical events
│   ├── service.py      adapter: model translation, persistence, audit
│   └── models.py       TimelineAnalysis / TimelineEvent contracts
├── graph/              typed graph + NetworkX centrality/community/backbone
├── analytics/          case, entity, threat and quality statistics
├── prioritization/     weighted case priority (6 dimensions)
├── legal/              source-backed statutory mapping and regulatory follow-up
├── reporting/          21-section JSON/Markdown + investigator-brief PDF
└── pipeline.py         orchestrator and composition root for the whole run
```

`timeline/engine.py` knows nothing about configuration, storage or audit — it
takes plain dicts and returns plain dicts, which is what makes it testable in
isolation and reusable outside the platform. `service.py` is the only thing
that adapts it to the platform.

## Installation

This module owns NetworkX, Pydantic, PDF rendering and test dependencies in
`requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

When copied separately, provide the upstream correlation and OCR engine roots
through `CIIS_CORRELATION_ROOT` and `CIIS_ENGINE_ROOT`.

## Why graph, analytics and priority live here

All three consume `TimelineAnalysis` — the graph most heavily, building
`timeline_event` nodes and temporal edges from it. Leaving them in the
correlation engine while the timeline moved here would have made the two
engines import each other. They belong to the output stage.

## Timeline and graph provenance

Timestamp resolution prefers explicit content date/time entities, complete
chat timestamps, and then EXIF/PDF/Office creation metadata. A partial chat
timestamp may borrow its year from acquisition time and is explicitly marked
`timestamp_inferred=true`; upload time is the final fallback and is labelled
`upload_time_fallback`. Only reconstructed content/metadata event times may
create evidence-to-evidence temporal edges, so uploading *n* files together no
longer produces *n(n-1)/2* false chronology links.

Acquisition fallbacks remain in the stored timeline as provenance, but they do
not set attack-stage dates, create incident milestones, or determine stage
order. The frontend therefore plots **Incident chronology** by default and
lists upload-only records below it. An explicit switch can add acquisition
timestamps to a combined diagnostic view, where they are labelled as intake
times rather than incident events.

Graph nodes cover cases, evidence, normalized entities, and timeline events.
Every edge carries its relationship type, confidence, source evidence IDs,
timestamp/provenance, inference flag, and explanation. NetworkX runs on a
simple analytical projection of the complete typed artifact and writes degree
centrality, betweenness, PageRank, combined importance, community membership,
bridge counts, and a maximum-spanning-forest `backbone` flag. No stored
relationship is removed by this analysis.

## Pipeline

`pipeline.py` is the composition root for the *entire* analysis, wiring the
correlation engine's services alongside this module's:

```python
from ciis_timeline_report.pipeline import build_default_pipeline

pipeline = build_default_pipeline()           # dependency-injection root
results  = pipeline.analyze_case("CASE_0042")
results["priority"].priority_level            # e.g. "HIGH"
```

Dependency order, each module failure-isolated:

```
correlation → cross-case → timeline → graph
                                    ↘ campaigns
                                    ↘ suspects
           → analytics → priority → report
```

## CLI

```bash
python investigation_cli.py analyze CASE_0042    # or --all
python investigation_cli.py priority CASE_0042
python investigation_cli.py report CASE_0042

python reindex_entities.py                       # after a normalization change
python scripts/run_table_6_5.py                  # timeline accuracy vs gold
python scripts/report_review.py                  # report-correctness harness
```

## Tests

```bash
python -m pytest -q
```

Fixtures come from `ciis_correlation.testing`, the same synthetic case the
correlation engine's suite uses, so tests move between the two without
rewriting.

## Output

Artifacts land in `storage/investigation/<CASE_ID>/`, versioned rather than
overwritten:

```
timeline_analysis.json   graph.json + graph_statistics.json + graph_summary.json
analytics.json           case_statistics.json   entity_statistics.json
case_priority.json       investigation_report.{json,md,pdf}
analysis_manifest.json   API-run inputs, versions, policy and warnings
```

PDF rendering needs `reportlab`. Without it the Markdown and JSON reports are
still produced and the run is logged, never failed.

The JSON and Markdown outputs preserve the complete 21-section machine-readable
contract. The PDF groups that material into eight investigator-facing parts:
Executive Brief; Evidence Register and Integrity; Reconstructed Incident
Chronology; Analytical Findings; Statutory and Regulatory Screening;
Investigator Action Plan; Methodology, Limitations and Conclusion; and
Report Control and Review Certification. The PDF uses a formal Times-family
serif face. Tables separate incident times from acquisition records, compact
paired summaries replace vertical metric dumps, and metadata is reduced to
coverage plus recorded exceptions. Legal matches are labelled as screening
candidates and operational actions use formal request language. The PDF has no
raw technical appendix: its evidence register records verification outcomes
and its report-control page carries the evidence-set digest, while the complete
item/source hash registers remain in the stored JSON companion.
The frontend adds a Timeline Flow projection without modifying the stored graph
artifact.

## Statutory and regulatory sources

The report's statutory basis is deterministic. Automatically engaged offence
provisions come from the Nepal Law Commission's Electronic Transactions Act,
while provisions whose essential elements cannot be established from current
signals are explicitly listed for manual review. ETA sections 4 and 6 add
electronic-record preservation guidance.

When payment evidence is present, selected controls from the official Nepal
Rastra Bank Cyber Resilience Guidelines 2023 add conditional follow-up for MFA,
authentication records, protected forensic logs and timestamp synchronisation.
These entries are not findings that a bank violated a rule. Applicability to the
affected institution must be confirmed by the investigator. Every generated
assessment carries source URLs, local corpus filenames and SHA-256 provenance.
