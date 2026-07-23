"""Case management: engine cases.csv is the source of truth for identity,
CaseMeta adds platform workflow (status, assignment, archive)."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import require

from .. import engine
from ..models import ActivityLog, CaseHistory, CaseMeta, CaseStatus
from ..pagination import DefaultPagination
from ..serializers import (
    CaseCreateSerializer,
    CaseHistorySerializer,
    CaseMetaSerializer,
)


def _merged_case(row: dict, meta: CaseMeta | None) -> dict:
    """Engine case row merged with platform workflow + Phase-2 priority."""
    case_id = row["case_id"]
    priority = engine.try_artifact(case_id, "priority")
    payload = (priority or {}).get("report", priority) if priority else None
    return {
        "case_id": case_id,
        "created_at": row.get("created_at", ""),
        "title": (meta.title if meta and meta.title else row.get("title", "")),
        "description": meta.description if meta else "",
        "investigator_notes": row.get("investigator_notes", ""),
        "evidence_count": int(row.get("evidence_count") or 0),
        "status": meta.status if meta else CaseStatus.OPEN,
        "assigned_to": meta.assigned_to.username if meta and meta.assigned_to else None,
        "tags": meta.tags if meta else [],
        "priority": payload,  # engine verdict verbatim (score, band, rationale)
        "priority_override": meta.priority_override if meta else "",
        "updated_at": meta.updated_at.isoformat() if meta else row.get("created_at", ""),
    }


class CaseListCreateView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request):
        metas = {m.case_id: m for m in CaseMeta.objects.select_related("assigned_to")}
        cases = [_merged_case(row, metas.get(row["case_id"])) for row in engine.list_cases()]

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
        meta = CaseMeta.objects.create(
            case_id=row["case_id"], title=data["title"],
            description=data["description"], tags=data["tags"],
            created_by=None, status=CaseStatus.OPEN,
        )
        CaseHistory.objects.create(
            case_id=row["case_id"], username=request.user.username,
            action="created", detail=f"Case created: {data['title']}",
        )
        ActivityLog.record(
            username=request.user.username, module="cases",
            action="create", case_id=row["case_id"], detail=data["title"],
        )
        return Response(_merged_case(row, meta), status=status.HTTP_201_CREATED)


def _band(priority_payload) -> str:
    if not priority_payload:
        return ""
    return str(
        priority_payload.get("priority_band")
        or priority_payload.get("band")
        or priority_payload.get("priority_level")
        or ""
    )


class CaseDetailView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request, case_id: str):
        row = engine.get_case(case_id)
        if row is None:
            return Response({"detail": "Case not found."}, status=404)
        meta = CaseMeta.objects.filter(case_id=case_id).select_related("assigned_to").first()
        data = _merged_case(row, meta)
        data["evidence"] = engine.list_evidence(case_id)
        return Response(data)

    def patch(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        meta, _ = CaseMeta.objects.get_or_create(case_id=case_id)
        serializer = CaseMetaSerializer(meta, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        changed = ", ".join(sorted(request.data.keys()))
        CaseHistory.objects.create(
            case_id=case_id, username=request.user.username,
            action="updated", detail=f"Fields changed: {changed}",
        )
        ActivityLog.record(
            username=request.user.username, module="cases",
            action="update", case_id=case_id, detail=changed,
        )
        return self.get(request, case_id)


class CaseArchiveView(APIView):
    permission_classes = (require("case.manage"),)

    def post(self, request, case_id: str):
        meta, _ = CaseMeta.objects.get_or_create(case_id=case_id)
        unarchive = request.data.get("unarchive", False)
        meta.status = CaseStatus.OPEN if unarchive else CaseStatus.ARCHIVED
        meta.save(update_fields=["status", "updated_at"])
        action = "unarchived" if unarchive else "archived"
        CaseHistory.objects.create(
            case_id=case_id, username=request.user.username, action=action
        )
        ActivityLog.record(
            username=request.user.username, module="cases",
            action=action, case_id=case_id,
        )
        return Response({"case_id": case_id, "status": meta.status})


class CaseHistoryView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request, case_id: str):
        qs = CaseHistory.objects.filter(case_id=case_id)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            CaseHistorySerializer(page, many=True).data
        )
