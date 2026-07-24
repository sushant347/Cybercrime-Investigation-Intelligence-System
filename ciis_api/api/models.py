"""Workflow state owned by the platform (never by the forensic engine).

The engine's CSV/JSON storage remains the single source of truth for
evidence and analysis artifacts. These models add investigation-platform
workflow: case status, assignments, notifications, and user activity audit.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class CaseStatus(models.TextChoices):
    OPEN = "open", "Open"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    ARCHIVED = "archived", "Archived"


class CaseMeta(models.Model):
    """Platform-side metadata for an engine case (keyed by engine case_id)."""

    case_id = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=CaseStatus.choices, default=CaseStatus.OPEN
    )
    priority_override = models.CharField(max_length=16, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_cases",
    )
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_cases",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)


class CaseHistory(models.Model):
    """Immutable trail of workflow changes on a case."""

    case_id = models.CharField(max_length=32, db_index=True)
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=64)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)


class NotificationType(models.TextChoices):
    PROCESSING_COMPLETE = "processing_complete", "Processing complete"
    HIGH_PRIORITY = "high_priority", "High priority case"
    FORGERY_WARNING = "forgery_warning", "Forgery warning"
    THREAT_DETECTED = "threat_detected", "Threat detected"
    REPORT_GENERATED = "report_generated", "Report generated"
    SYSTEM_ERROR = "system_error", "System error"


class Notification(models.Model):
    #: Nullable: the engine has no accounts, so notifications are engine-wide.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications", null=True, blank=True,
    )
    type = models.CharField(max_length=32, choices=NotificationType.choices)
    title = models.CharField(max_length=256)
    message = models.TextField(blank=True)
    case_id = models.CharField(max_length=32, blank=True)
    evidence_id = models.CharField(max_length=32, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    @classmethod
    def broadcast(cls, *, type: str, title: str, message: str = "",
                  case_id: str = "", evidence_id: str = "") -> None:
        """Record an engine-wide event (one notification, no recipients)."""
        cls.objects.create(
            user=None, type=type, title=title, message=message,
            case_id=case_id, evidence_id=evidence_id,
        )


class ActivityLog(models.Model):
    """Platform-side user activity audit (merged with engine audit logs)."""

    username = models.CharField(max_length=150, blank=True)
    module = models.CharField(max_length=64)
    action = models.CharField(max_length=64)
    case_id = models.CharField(max_length=32, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    @classmethod
    def record(cls, *, username: str, module: str, action: str,
               detail: str = "", case_id: str = "") -> None:
        cls.objects.create(
            username=username, module=module, action=action,
            detail=detail, case_id=case_id,
        )


class BackgroundJob(models.Model):
    """Tracks long-running engine work (uploads, Phase-2 analysis)."""

    JOB_TYPES = (("evidence_processing", "Evidence processing"),
                 ("case_analysis", "Case analysis"))
    STATUSES = (("queued", "Queued"), ("running", "Running"),
                ("completed", "Completed"), ("failed", "Failed"))

    job_type = models.CharField(max_length=32, choices=JOB_TYPES)
    status = models.CharField(max_length=16, choices=STATUSES, default="queued")
    case_id = models.CharField(max_length=32, blank=True, db_index=True)
    evidence_id = models.CharField(max_length=32, blank=True)
    detail = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
