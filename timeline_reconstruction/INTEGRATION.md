# Active timeline core

This directory is the canonical, framework-independent timeline reconstruction
engine. The production call path is:

```text
investigation pipeline
  -> integrated TimelineService adapter
  -> timeline_reconstruction.build_timeline
  -> timeline_analysis.json
  -> GraphService
```

The integrated service translates `EvidenceContext` and correlation results,
then handles persistence and audit logging. Timestamp resolution, inference
labels, chronological ordering, duplicate prevention, attack stages,
milestones, and critical events are owned here.

Evidence entities continue to be produced by the existing semantic entity
extraction pipeline before this engine runs. The timeline core consumes those
stored entities; it does not perform OCR or entity extraction itself.
