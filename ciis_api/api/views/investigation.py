"""Phase-2 artifacts, served verbatim. Explanations, scores and summaries
come exclusively from the engine's stored JSON - never recomputed here."""
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import require

from .. import engine
from ..models import ActivityLog, BackgroundJob
from ..serializers import BackgroundJobSerializer


class ArtifactView(APIView):
    """GET /cases/<id>/artifacts/<key>/ - any Phase-2 artifact by key."""

    permission_classes = (require("investigation.view"),)

    def get(self, request, case_id: str, key: str):
        return Response(engine.load_artifact(case_id, key))


class ArtifactIndexView(APIView):
    """Availability map: which artifacts exist for a case."""

    permission_classes = (require("investigation.view"),)

    def get(self, request, case_id: str):
        availability = {
            key: engine.try_artifact(case_id, key) is not None
            for key in engine.ARTIFACTS
        }
        return Response({"case_id": case_id, "artifacts": availability})


class RunAnalysisView(APIView):
    """Trigger the engine's Phase-2 pipeline (all eight modules)."""

    permission_classes = (require("investigation.run"),)

    def post(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        running = BackgroundJob.objects.filter(
            job_type="case_analysis", case_id=case_id,
            status__in=("queued", "running"),
        ).first()
        if running:
            return Response(BackgroundJobSerializer(running).data, status=200)
        job = BackgroundJob.objects.create(
            job_type="case_analysis", case_id=case_id,
            created_by=request.user.username,
        )
        engine.submit_analysis_job(job.pk, case_id, request.user.username)
        ActivityLog.record(
            username=request.user.username, module="investigation",
            action="run_analysis", case_id=case_id,
        )
        return Response(BackgroundJobSerializer(job).data, status=202)
