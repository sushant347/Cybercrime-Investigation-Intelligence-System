"""Case-scoped investigator assistant backed by the standalone RAG engine."""

from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine
from ..permissions import require
from ..serializers import RAGQuestionSerializer
from ..store import activity


class RAGStatusView(APIView):
    permission_classes = (require("assistant.view"),)

    def get(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        return Response(engine.rag_status(case_id))


class RAGAskView(APIView):
    permission_classes = (require("assistant.ask"),)

    def post(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        serializer = RAGQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = engine.ask_rag(case_id, serializer.validated_data["question"])
        activity.record(
            module="rag_assistant",
            action="ask",
            case_id=case_id,
            detail=(
                f"insufficient={bool(result.get('insufficient_evidence'))}; "
                f"citations={len(result.get('cited_sources') or [])}"
            ),
        )
        return Response(result)
