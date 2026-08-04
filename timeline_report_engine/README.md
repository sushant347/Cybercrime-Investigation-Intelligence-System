# Timeline & Report Engine

The terminal stage of the CIIS pipeline. Takes the relationships found by the
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
├── graph/              typed relationship graph (12 node / 5+1 edge types)
├── analytics/          case, entity, threat and quality statistics
├── prioritization/     weighted case priority (6 dimensions)
├── reporting/          report as Markdown + JSON + PDF (19 sections)
└── pipeline.py         orchestrator and composition root for the whole run
```

`timeline/engine.py` knows nothing about configuration, storage or audit — it
takes plain dicts and returns plain dicts, which is what makes it testable in
isolation and reusable outside the platform. `service.py` is the only thing
that adapts it to the platform.

## Why graph, analytics and priority live here

All three consume `TimelineAnalysis` — the graph most heavily, building
`timeline_event` nodes and temporal edges from it. Leaving them in the
correlation engine while the timeline moved here would have made the two
engines import each other. They belong to the output stage.

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
python -m pytest -q      # 52 tests
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
```

PDF rendering needs `reportlab`. Without it the Markdown and JSON reports are
still produced and the run is logged, never failed.
