"""Uniform error envelope: {"detail": str, "code": str}."""
import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

log = logging.getLogger("ciis.api")


class EngineUnavailable(Exception):
    """Raised when a Phase 1/2 artifact or engine capability is missing."""


def api_exception_handler(exc, context):
    if isinstance(exc, EngineUnavailable):
        return Response({"detail": str(exc), "code": "engine_unavailable"}, status=503)
    response = exception_handler(exc, context)
    if response is None:
        log.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"detail": "Internal server error.", "code": "server_error"}, status=500
        )
    if isinstance(response.data, dict) and "code" not in response.data:
        response.data["code"] = getattr(exc, "default_code", "error")
    return response
