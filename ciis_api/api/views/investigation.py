"""Phase-2 artifacts, served verbatim. Explanations, scores and summaries
come exclusively from the engine's stored JSON - never recomputed here."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import require

from .. import engine
from ..serializers import job_payload
from ..store import activity, jobs


class ArtifactView(APIView):
    """GET /cases/<id>/artifacts/<key>/ - any Phase-2 artifact by key."""

    permission_classes = (require("investigation.view"),)

    def get(self, request, case_id: str, key: str):
        return Response(engine.load_artifact(case_id, key))


class ArtifactIndexView(APIView):
    """Availability map: which artifacts exist for a case."""

    permission_classes = (require("investigation.view"),)

    def get(self, request, case_id: str):
        # Existence check only - never deserialise the artifacts here.
        availability = {
            key: engine.artifact_exists(case_id, key) for key in engine.ARTIFACTS
        }
        return Response({"case_id": case_id, "artifacts": availability})


class RunAnalysisView(APIView):
    """Trigger the engine's Phase-2 pipeline (all eight modules)."""

    permission_classes = (require("investigation.run"),)

    def post(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        # A case exists in the registry before any evidence is attached to it,
        # but the pipeline resolves a case *through* its evidence — so running
        # analysis on an empty case failed deep inside with "Unknown case
        # '<id>'", which reads as data loss rather than "nothing to analyse
        # yet". Refuse it here, where the reason is still known.
        if not engine.list_evidence(case_id):
            return Response(
                {"detail": "Upload evidence before running the analysis - "
                           "this case has no items yet."},
                status=400,
            )
        running = jobs.active("case_analysis", case_id)
        if running:
            return Response(job_payload(running), status=200)
        job = jobs.start("case_analysis", case_id=case_id)
        engine.submit_analysis_job(job["id"], case_id, "")
        activity.record(module="investigation", action="run_analysis",
                        case_id=case_id)
        return Response(job_payload(job), status=202)
