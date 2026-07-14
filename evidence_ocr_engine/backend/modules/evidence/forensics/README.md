# CIIS Phase 1 — Forensic Evidence Processing Enhancements

Additive package strengthening the evidence pipeline before the investigation,
dashboard, and AI-assistant phases. **No existing module was modified.**

## Architecture

Clean Architecture, DI throughout, Repository Pattern, configuration-driven
(no hardcoded values — see `config.py`, overridable via `FORENSICS_*` env vars).

```
forensics/
├── config.py                  ForensicsConfig (all tunables, env overrides)
├── audit.py                   ForensicAuditTrail → forensics_audit_log.csv
├── repository.py              Versioned JSON reports (never overwrites: _v2, _v3…)
├── pipeline.py                ForensicPhase1Pipeline + build_default_pipeline()
├── quality/                   M1 OCR Quality Assessment Engine
├── advanced_preprocessing/    M2 planner + operations + service
├── multi_ocr/                 M3 Paddle/EasyOCR/Tesseract adapters + fusion
├── forgery/                   M4 ELA, compression, metadata, copy-move, noise
├── logos/                     M5 brand registry (data/logo_brands.json) + detector
├── metadata/                  M6 EXIF / PDF / OOXML extraction
├── integrity/                 M7 multi-hash fingerprint + duplicates
└── confidence/                M8 final evidence confidence score
```

Each module = `models.py` (Pydantic contracts, validation) + `service.py`
(business logic) sharing the repository, audit, and config layers.
Tests: `tests/forensics/` (fake OCR adapters, synthetic images, temp storage).

## Data flow

```
file ─→ EvidencePipeline (UNCHANGED: acquisition, SHA-256 custody, PaddleOCR)
     └→ ForensicPhase1Pipeline.analyze_evidence(evidence_id)
          ├─ M7 integrity  ──┐  (all file types, original opened read-only)
          ├─ M6 metadata   ──┤
          ├─ M1 quality    ──┤  (images: evidence never modified)
          ├─ M4 forgery    ──┤
          ├─ M2 preprocessing (working copy; driven by M1; each op logged)
          ├─ M3 multi-OCR fusion (on the enhanced working copy)
          ├─ M5 logo detection  (image + fused OCR lines)
          └─ M8 confidence  ←──┘  aggregates everything above
```

Every stage is failure-isolated (one broken analysis never stops the rest)
and writes an audit row. Re-analysis creates new report versions.

## Storage (all new, nothing legacy is touched)

```
storage/forensics/
├── forensics_audit_log.csv           audit trail, all modules
├── file_fingerprints.csv             M7 duplicate index
├── evidence_confidence.csv           M8 score index (evidence record companion)
├── logo_templates/<brand>/*.png      optional real logo assets (M5)
└── <EVIDENCE_ID>/
    ├── quality_report.json           M1   ├── logo_detections.json   M5
    ├── preprocessing_report.json     M2   ├── metadata_report.json   M6
    ├── ocr_fusion.json               M3   ├── file_fingerprint.json  M7
    ├── forgery_report.json           M4   ├── evidence_confidence.json M8
    └── derived/enhanced_*.png        M2 working copies (never originals)
```

`ocr_fusion.json` stores `raw_text`, `paddle_text`, `easyocr_text`,
`tesseract_text`, `merged_text`, `final_text`, per-engine confidences, and
which engine produced the final result.

## API / usage

```python
from backend.modules.evidence.forensics.pipeline import build_default_pipeline

pipeline = build_default_pipeline()                # composition root
outcome = pipeline.process_file("screenshot.png")  # legacy run + all analyses
results = pipeline.analyze_evidence("EVID_00042")  # enrich existing evidence
```

CLI (original `cli.py` untouched):

```
python forensics_cli.py process <file> [--case CASE_0001]
python forensics_cli.py analyze <EVIDENCE_ID>
python forensics_cli.py reports <EVIDENCE_ID>
```

## Dependencies

Core needs nothing beyond the existing requirements (opencv, pillow, numpy,
pydantic, pymupdf). Optional OCR engines: `requirements-forensics.txt`
(easyocr, pytesseract + tesseract binary). Missing engines are reported as
unavailable and skipped — PaddleOCR remains primary.

## Forensic guarantees

Originals are never opened for writing; reports are versioned, never
overwritten; chain of custody and every legacy storage format are preserved
bit-for-bit; forgery analysis produces findings only and never rejects
evidence; every action is audited.
