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
