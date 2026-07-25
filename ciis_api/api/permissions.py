"""Access control.

The engine is **open access**: investigators reach a case by knowing its
reference, and there are no user accounts (see AUDIT.md, 2026-07-23).
``require()`` is kept as a documented no-op so each view still records which
capability it represents.

The one privileged surface is the **admin role**, gated by a shared password
(``settings.ADMIN_PASSWORD``) rather than a user account. ``IsAdmin`` protects
those endpoints; see :mod:`api.admin_auth`.
"""
from rest_framework.permissions import AllowAny, BasePermission

from .admin_auth import token_is_valid


def require(permission: str) -> type[BasePermission]:
    """Formerly an RBAC check; now open access (no authentication)."""

    class _OpenAccess(AllowAny):
        """Open access - retains the permission code for documentation."""

        required_permission = permission

    _OpenAccess.__name__ = f"Open_{permission.replace('.', '_')}"
    return _OpenAccess


class IsAdmin(BasePermission):
    """Requires a valid admin token (obtained with the admin password)."""

    message = "Admin access required. Sign in with the admin password."

    def has_permission(self, request, view) -> bool:  # noqa: D102
        return token_is_valid(request.headers.get("X-Admin-Token", ""))
