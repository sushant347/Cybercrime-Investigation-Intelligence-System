"""Shared vocabularies.

These were Django ``TextChoices`` on the old ORM models; with the database gone
they are plain string constants used by ``api.store`` records and the SPA.
"""


class CaseStatus:
    OPEN = "open"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    ALL = (OPEN, ACTIVE, COMPLETED, ARCHIVED)


class NotificationType:
    PROCESSING_COMPLETE = "processing_complete"
    HIGH_PRIORITY = "high_priority"
    FORGERY_WARNING = "forgery_warning"
    THREAT_DETECTED = "threat_detected"
    REPORT_GENERATED = "report_generated"
    CASE_DELETED = "case_deleted"
    SYSTEM_ERROR = "system_error"


class EvidenceStage:
    """The real steps an upload passes through, in the order they execute.

    The worker reports each transition onto the job record, so the upload
    dialog shows what the engine is actually doing rather than an indefinite
    spinner. Keys are stable API values; labels are what the investigator
    reads. Some steps are skipped by configuration (forensics can be disabled,
    the timeline rebuild is deferred to the last upload of a burst), so the UI
    must treat this as the *expected* order, not a guaranteed sequence.
    """

    ACQUIRE = "acquire"
    EXTRACT = "extract"
    VERIFY = "verify"
    STORE = "store"
    ENRICH = "enrich"
    FORENSICS = "forensics"
    CORRELATE = "correlate"

    #: (key, investigator-facing label) in execution order.
    ORDER = (
        (ACQUIRE, "Acquiring file, computing SHA-256"),
        (EXTRACT, "Extracting text"),
        (VERIFY, "Verifying hash integrity"),
        (STORE, "Storing OCR record"),
        (ENRICH, "Cleaning text, extracting entities"),
        (FORENSICS, "Forensic analysis"),
        (CORRELATE, "Correlation, timeline and graph"),
    )

    KEYS = tuple(key for key, _ in ORDER)
    LABELS = dict(ORDER)
