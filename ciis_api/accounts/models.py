"""User accounts and configurable role-based access control."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMINISTRATOR = "administrator", "Administrator"
    INVESTIGATOR = "investigator", "Investigator"
    ANALYST = "analyst", "Analyst"
    VIEWER = "viewer", "Viewer"


class Permission(models.TextChoices):
    """Granular platform permissions (checked by ``HasPlatformPermission``)."""

    CASE_VIEW = "case.view", "View cases"
    CASE_MANAGE = "case.manage", "Create / update / archive cases"
    EVIDENCE_VIEW = "evidence.view", "View evidence and artifacts"
    EVIDENCE_UPLOAD = "evidence.upload", "Upload evidence"
    INVESTIGATION_VIEW = "investigation.view", "View investigation results"
    INVESTIGATION_RUN = "investigation.run", "Run Phase-2 analysis"
    REPORT_VIEW = "report.view", "View / download reports"
    AUDIT_VIEW = "audit.view", "View audit logs"
    SETTINGS_VIEW = "settings.view", "View system settings"
    USER_MANAGE = "user.manage", "Manage users and roles"


#: Default permission matrix - seeded into ``RolePermission`` and used as a
#: fallback when a role has no explicit database configuration.
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    Role.ADMINISTRATOR: [p.value for p in Permission],
    Role.INVESTIGATOR: [
        Permission.CASE_VIEW, Permission.CASE_MANAGE,
        Permission.EVIDENCE_VIEW, Permission.EVIDENCE_UPLOAD,
        Permission.INVESTIGATION_VIEW, Permission.INVESTIGATION_RUN,
        Permission.REPORT_VIEW, Permission.AUDIT_VIEW, Permission.SETTINGS_VIEW,
    ],
    Role.ANALYST: [
        Permission.CASE_VIEW, Permission.EVIDENCE_VIEW,
        Permission.INVESTIGATION_VIEW, Permission.INVESTIGATION_RUN,
        Permission.REPORT_VIEW, Permission.SETTINGS_VIEW,
    ],
    Role.VIEWER: [
        Permission.CASE_VIEW, Permission.EVIDENCE_VIEW,
        Permission.INVESTIGATION_VIEW, Permission.REPORT_VIEW,
    ],
}


class User(AbstractUser):
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.VIEWER)
    badge_number = models.CharField(max_length=64, blank=True)
    department = models.CharField(max_length=128, blank=True)

    def permissions(self) -> list[str]:
        configured = RolePermission.objects.filter(role=self.role).values_list(
            "permission", flat=True
        )
        if configured:
            return list(configured)
        return [str(p) for p in DEFAULT_ROLE_PERMISSIONS.get(self.role, [])]

    def has_platform_permission(self, permission: str) -> bool:
        return self.is_superuser or permission in self.permissions()


class RolePermission(models.Model):
    """Configurable role -> permission mapping (editable by administrators)."""

    role = models.CharField(max_length=32, choices=Role.choices)
    permission = models.CharField(max_length=64, choices=Permission.choices)

    class Meta:
        unique_together = ("role", "permission")

    def __str__(self) -> str:
        return f"{self.role}:{self.permission}"


class UserPreference(models.Model):
    """Per-user UI preferences (theme, language, notification opts)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preference")
    theme = models.CharField(max_length=16, default="dark")
    language = models.CharField(max_length=16, default="en")
    notifications_enabled = models.BooleanField(default=True)
    items_per_page = models.PositiveSmallIntegerField(default=25)
