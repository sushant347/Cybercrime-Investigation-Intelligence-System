"""DRF permission classes backed by the configurable RBAC matrix."""
from rest_framework.permissions import BasePermission


def require(permission: str) -> type[BasePermission]:
    """Build a permission class requiring one platform permission code."""

    class _HasPermission(BasePermission):
        message = f"Requires permission '{permission}'."

        def has_permission(self, request, view) -> bool:  # noqa: D102
            user = request.user
            return bool(
                user and user.is_authenticated and user.has_platform_permission(permission)
            )

    _HasPermission.__name__ = f"Requires_{permission.replace('.', '_')}"
    return _HasPermission
