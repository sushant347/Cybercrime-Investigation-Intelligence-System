"""Case management: engine ``cases.csv`` is the source of truth for identity;
``store.case_meta`` (CSV) adds platform workflow (status, tags, archive)."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine
from ..constants import CaseStatus
from ..pagination import DefaultPagination
from ..permissions import require
from ..serializers import CaseCreateSerializer
from ..store import activity, case_meta


def _merged_case(row: dict, meta: dict | None) -> dict:
    """Engine case row merged with platform workflow + Phase-2 priority."""
    case_id = row["case_id"]
    priority = engine.try_artifact(case_id, "priority")
    payload = (priority or {}).get("report", priority) if priority else None
    meta = meta or {}
    return {
        "case_id": case_id,
        "created_at": row.get("created_at", ""),
        "title": meta.get("title") or row.get("title", ""),
        "description": meta.get("description", ""),
        "investigator_notes": row.get("investigator_notes", ""),
        "evidence_count": int(row.get("evidence_count") or 0),
        "status": meta.get("status") or CaseStatus.OPEN,
        "assigned_to": None,  # no user accounts
        "tags": meta.get("tags") or [],
        "priority": payload,  # engine verdict verbatim (score, band, rationale)
        "priority_override": meta.get("priority_override", ""),
        "updated_at": meta.get("updated_at") or row.get("created_at", ""),
    }


def _band(priority_payload) -> str:
    if not priority_payload:
        return ""
    return str(
        priority_payload.get("priority_band")
        or priority_payload.get("band")
        or priority_payload.get("priority_level")
        or ""
    )


class CaseListCreateView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request):
        metas = {m["case_id"]: m for m in case_meta.all_decoded()}
        cases = [_merged_case(row, metas.get(row["case_id"]))
                 for row in engine.list_cases()]

        q = request.query_params.get("search", "").lower()
        if q:
            cases = [
                c for c in cases
                if q in c["case_id"].lower() or q in c["title"].lower()
                or any(q in t.lower() for t in c["tags"])
            ]
        st = request.query_params.get("status")
        if st:
            cases = [c for c in cases if c["status"] == st]
        elif request.query_params.get("include_archived", "0") != "1":
            cases = [c for c in cases if c["status"] != CaseStatus.ARCHIVED]
        band = request.query_params.get("priority")
        if band:
            cases = [
                c for c in cases
                if (c["priority_override"] or _band(c["priority"])).lower() == band.lower()
            ]

        ordering = request.query_params.get("ordering", "-created_at")
        reverse = ordering.startswith("-")
        key = ordering.lstrip("-")
        if key in {"case_id", "created_at", "title", "evidence_count", "status", "updated_at"}:
            cases.sort(key=lambda c: (c[key] is None, c[key]), reverse=reverse)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(cases, request)
        return paginator.get_paginated_response(page)

    def post(self, request):
        serializer = CaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        row = engine.create_case(data["title"], data["notes"])
        meta = case_meta.upsert(
            row["case_id"], title=data["title"], description=data["description"],
            tags=data["tags"], status=CaseStatus.OPEN,
        )
        activity.record(module="cases", action="create",
                        case_id=row["case_id"], detail=data["title"])
        return Response(_merged_case(row, meta), status=status.HTTP_201_CREATED)


class CaseDetailView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request, case_id: str):
        row = engine.get_case(case_id)
        if row is None:
            return Response({"detail": "Case not found."}, status=404)
        data = _merged_case(row, case_meta.get(case_id))
        registry_row = engine.case_registry().get(case_id)
        data["case_reference"] = (registry_row or {}).get("case_reference", "")
        data["evidence"] = engine.list_evidence(case_id)
        return Response(data)

    def patch(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        allowed = {"title", "description", "status", "priority_override", "tags"}
        fields = {k: v for k, v in request.data.items() if k in allowed}
        if fields.get("status") and fields["status"] not in CaseStatus.ALL:
            return Response({"detail": f"Unknown status '{fields['status']}'."}, status=400)
        case_meta.upsert(case_id, **fields)
        changed = ", ".join(sorted(fields))
        activity.record(module="cases", action="update",
                        case_id=case_id, detail=changed)
        return self.get(request, case_id)


class CaseArchiveView(APIView):
    permission_classes = (require("case.manage"),)

    def post(self, request, case_id: str):
        unarchive = request.data.get("unarchive", False)
        new_status = CaseStatus.OPEN if unarchive else CaseStatus.ARCHIVED
        case_meta.upsert(case_id, status=new_status)
        action = "unarchived" if unarchive else "archived"
        activity.record(module="cases", action=action, case_id=case_id)
        return Response({"case_id": case_id, "status": new_status})

