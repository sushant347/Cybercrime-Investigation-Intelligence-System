"""Permission classes.

This runs as a **case-centric forensic engine**, not a multi-user case
management system: there are no logins and no role-based access control.
``require()`` is kept as a documented no-op so each view still records which
capability it represents - and so RBAC can be reinstated later by restoring
the check that used to live here (see git history).
"""
from rest_framework.permissions import AllowAny, BasePermission


def require(permission: str) -> type[BasePermission]:
    """Formerly enforced an RBAC code; now open access (no authentication)."""

    class _OpenAccess(AllowAny):
        """Open access - retains the permission code for documentation."""

        required_permission = permission

    _OpenAccess.__name__ = f"Open_{permission.replace('.', '_')}"
    return _OpenAccess
