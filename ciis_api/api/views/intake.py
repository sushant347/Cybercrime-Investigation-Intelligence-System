"""Case intake: the engine's front door.

There are no user accounts. An investigator types a *case reference*, which
is hashed into a stable case id (see the engine's ``case_registry`` module);
entering the same reference again reopens the same case with its evidence
and reports. The registry lives in CSV, never a database.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine
from ..store import activity


def _payload(record: dict, created: bool) -> dict:
    return {
        "case_id": record["case_id"],
        "case_reference": record.get("case_reference", ""),
        "title": record.get("title", ""),
        "created_at": record.get("created_at", ""),
        "last_opened_at": record.get("last_opened_at", ""),
        "created": created,
    }


class IntakeView(APIView):
    """``POST`` opens or creates a case from its reference.

    There is deliberately **no listing endpoint**: cases are private to
    whoever knows the reference, so the registry is never enumerated over
    the API.
    """

    def post(self, request):
        reference = str(request.data.get("reference", "")).strip()
        title = str(request.data.get("title", "")).strip()
        if not reference:
            return Response(
                {"detail": "A case reference is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record, created = engine.intake_case(reference, title)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        activity.record(module="intake",
                        action="created" if created else "opened",
                        case_id=record["case_id"],
                        detail=record.get("case_reference", ""))
        return Response(
            _payload(record, created),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class IntakeResolveView(APIView):
    """Look up a reference without creating anything (existence check)."""

    def get(self, request):
        reference = request.query_params.get("reference", "").strip()
        if not reference:
            return Response({"detail": "A case reference is required."}, status=400)
        registry = engine.case_registry()
        record = registry.get_by_reference(reference)
        return Response(
            {
                "case_id": registry.case_id_for(reference),
                "exists": record is not None,
                "case": _payload(record, created=False) if record else None,
            }
        )
