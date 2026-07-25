"""Unified audit trail: Phase-1 processing log + Phase-2 investigation audit
+ platform activity log, merged and filterable."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import require

from .. import engine
from ..store import activity
from ..pagination import DefaultPagination


def _normalise(rows: list[dict], source: str) -> list[dict]:
    out = []
    for r in rows:
        out.append(
            {
                "source": source,
                "timestamp": r.get("timestamp") or r.get("time") or r.get("created_at", ""),
                "case_id": r.get("case_id", ""),
                "evidence_id": r.get("evidence_id", ""),
                "module": r.get("module") or r.get("stage", ""),
                "action": r.get("action") or r.get("stage") or r.get("event", ""),
                "level": r.get("level", "INFO"),
                "detail": r.get("detail") or r.get("message", ""),
                "username": r.get("username", "system"),
            }
        )
    return out


class AuditLogView(APIView):
    permission_classes = (require("audit.view"),)

    def get(self, request):
        case_id = request.query_params.get("case_id") or None
        entries = (
            _normalise(engine.processing_log(case_id), "evidence_pipeline")
            + _normalise(engine.investigation_audit(case_id), "investigation")
            + _normalise(activity.list(case_id=case_id or "", limit=2000), "platform")
        )
        module = request.query_params.get("module")
        if module:
            entries = [e for e in entries if module.lower() in e["module"].lower()]
        user = request.query_params.get("user")
        if user:
            entries = [e for e in entries if user.lower() in e["username"].lower()]
        q = request.query_params.get("search", "").lower()
        if q:
            entries = [
                e for e in entries
                if q in e["detail"].lower() or q in e["action"].lower()
                or q in e["case_id"].lower()
            ]
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            entries = [e for e in entries if str(e["timestamp"])[:10] >= date_from]
        if date_to:
            entries = [e for e in entries if str(e["timestamp"])[:10] <= date_to]

        entries.sort(key=lambda e: str(e["timestamp"]), reverse=True)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(entries, request)
        return paginator.get_paginated_response(page)
