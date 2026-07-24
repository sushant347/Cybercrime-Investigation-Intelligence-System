"""Testing maintenance: clear all cases and entities from the engine.

Destructive by design and intended for development/testing only. It resets the
forensic engine's storage (cases, evidence, entities, artifacts, the cross-case
index) and the platform's workflow tables (jobs, notifications, audit, case
metadata) so the next run starts from an empty system.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine
from ..models import ActivityLog, BackgroundJob, CaseHistory, CaseMeta, Notification


class ResetView(APIView):
    """POST /api/maintenance/reset/ - clear all cases and entities."""

    permission_classes = (AllowAny,)

    def post(self, request):
        summary = engine.reset_engine_storage()

        # Workflow state references cases by id; clear it so nothing dangles.
        deleted = {
            "background_jobs": BackgroundJob.objects.all().delete()[0],
            "notifications": Notification.objects.all().delete()[0],
            "case_history": CaseHistory.objects.all().delete()[0],
            "case_meta": CaseMeta.objects.all().delete()[0],
        }
        ActivityLog.objects.all().delete()
        ActivityLog.record(
            username="", module="maintenance", action="reset",
            detail="Cleared all cases and entities.",
        )
        return Response({"status": "reset", "storage": summary, "workflow": deleted})
