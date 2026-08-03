# Active timeline core

This directory is the canonical, framework-independent timeline reconstruction
engine. The production call path is:

```text
ciis_correlation.pipeline
  -> ciis_correlation.timeline.service.TimelineService   (adapter)
  -> timeline_reconstruction.build_timeline              (this module)
  -> timeline_analysis.json
  -> GraphService
```

The adapter lives in the correlation engine — mirroring
`ciis_correlation/threat/ml_provider.py`, which wraps the standalone threat
system the same way — and loads this file via `importlib` at runtime. It
translates `EvidenceContext` and correlation results, then handles
persistence and audit logging. Timestamp resolution, inference
labels, chronological ordering, duplicate prevention, attack stages,
milestones, and critical events are owned here.

Evidence entities continue to be produced by the existing semantic entity
extraction pipeline before this engine runs. The timeline core consumes those
stored entities; it does not perform OCR or entity extraction itself.
