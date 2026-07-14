"""CIIS Phase 1 - Forensic Evidence Processing Enhancements.

This package is a pure *add-on* to the existing evidence engine. It never
modifies, replaces or removes any behaviour of the completed modules:

* Module 1 - OCR Quality Assessment Engine        -> :mod:`.quality`
* Module 2 - Advanced Image Preprocessing         -> :mod:`.advanced_preprocessing`
* Module 3 - Multi-OCR Fusion Engine              -> :mod:`.multi_ocr`
* Module 4 - Image Forgery Detection              -> :mod:`.forgery`
* Module 5 - Logo & Brand Detection               -> :mod:`.logos`
* Module 6 - Forensic Metadata Extraction         -> :mod:`.metadata`
* Module 7 - Advanced File Integrity Analysis     -> :mod:`.integrity`
* Module 8 - Evidence Confidence Scoring          -> :mod:`.confidence`

Shared infrastructure:

* :mod:`.config`      - configuration (no hardcoded values in services)
* :mod:`.repository`  - versioned JSON report storage (never overwrites)
* :mod:`.audit`       - forensic audit trail (storage/forensics/forensics_audit_log.csv)
* :mod:`.pipeline`    - Phase-1 orchestrator composing the existing pipeline

Design guarantees:

* Original evidence files are **never** written to.
* Existing CSV/JSON storage formats are untouched; all new outputs live in
  ``storage/forensics/``.
* Every analysis produces an audit log entry.
* Every service receives its collaborators through dependency injection and
  is independently testable.
"""

from .config import ForensicsConfig

__all__ = ["ForensicsConfig"]
