"""Testing maintenance: clear all cases and entities from the engine.

Destructive by design and intended for development/testing only. Resets the
forensic engine's storage (cases, evidence, entities, artifacts, the cross-case
index) and the platform's own CSV/JSON records (jobs, notifications, activity
audit, case metadata/history) so the next run starts from an empty system.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine, store


class ResetView(APIView):
    """POST /api/maintenance/reset/ - clear all cases and entities."""

    permission_classes = (AllowAny,)

    def post(self, request):
        summary = engine.reset_engine_storage()
        store.clear_all()
        store.activity.record(
            module="maintenance", action="reset",
            detail="Cleared all cases and entities.",
        )
        return Response({"status": "reset", "storage": summary})
