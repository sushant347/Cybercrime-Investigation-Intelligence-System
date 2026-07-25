"""Administrator role — the only privileged surface in the engine.

Investigators work anonymously and reach a case only by knowing its reference.
An **administrator** proves knowledge of the shared admin password and can then:

* list **every** case in the system (normally nothing enumerates them), and
* **delete** a case — which purges it from every store and re-analyses every
  case that was cross-linked to it, so no surviving correlation, timeline,
  graph or report still references the deleted case.

Auth is a signed, expiring token (``api.admin_auth``) — no user table, no
session store, no database.
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine
from ..admin_auth import issue_token, password_is_correct
from ..constants import CaseStatus, NotificationType
from ..permissions import IsAdmin
from ..serializers import AdminLoginSerializer
from ..store import activity, case_meta, delete_case_everywhere, notifications


class AdminLoginView(APIView):
    """POST /api/admin/login/ — exchange the admin password for a token."""

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not password_is_correct(serializer.validated_data["password"]):
            activity.record(module="admin", action="login_failed")
            return Response({"detail": "Incorrect admin password."}, status=401)
        activity.record(module="admin", action="login")
        return Response({"token": issue_token(), "role": "admin"})


class AdminSessionView(APIView):
    """GET /api/admin/session/ — is the caller's admin token still valid?"""

    permission_classes = (IsAdmin,)

    def get(self, request):
        return Response({"role": "admin", "valid": True})


class AdminCaseListView(APIView):
    """GET /api/admin/cases/ — every case, with evidence + analysis status."""

    permission_classes = (IsAdmin,)

    def get(self, request):
        registry = {r["case_id"]: r for r in engine.case_registry().list_all()}
        metas = {m["case_id"]: m for m in case_meta.all_decoded()}
        evidence_by_case: dict[str, int] = {}
        for row in engine.list_evidence():
            cid = row.get("case_id", "")
            evidence_by_case[cid] = evidence_by_case.get(cid, 0) + 1

        cases = []
        for row in engine.list_cases():
            case_id = row["case_id"]
            reg = registry.get(case_id, {})
            meta = metas.get(case_id, {})
            cross = engine.try_artifact(case_id, "cross_case")
            linked = ((cross or {}).get("report") or {}).get("related_case_ids", [])
            priority = engine.try_artifact(case_id, "priority")
            payload = (priority or {}).get("report") if priority else None
            cases.append({
                "case_id": case_id,
                "case_reference": reg.get("case_reference", ""),
                "title": meta.get("title") or row.get("title", ""),
                "created_at": row.get("created_at", ""),
                "last_opened_at": reg.get("last_opened_at", ""),
                "evidence_count": evidence_by_case.get(case_id, 0),
                "status": meta.get("status") or CaseStatus.OPEN,
                "analysed": engine.artifact_exists(case_id, "report"),
                "linked_case_ids": linked,
                "priority_level": (payload or {}).get("priority_level", ""),
            })
        cases.sort(key=lambda c: c.get("created_at", ""), reverse=True)
        return Response({"count": len(cases), "cases": cases})


class AdminCaseDeleteView(APIView):
    """DELETE /api/admin/cases/<case_id>/ — purge a case and refresh its links."""

    permission_classes = (IsAdmin,)

    def delete(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)

        # Engine-side purge + re-analysis of every previously linked case.
        result = engine.delete_case_cascade(case_id)
        # Platform-side records for this case.
        result["platform_records_removed"] = delete_case_everywhere(case_id)

        activity.record(
            module="admin", action="delete_case", case_id=case_id,
            detail=(f"deleted; refreshed {len(result.get('refreshed_cases', []))} "
                    f"linked case(s)"),
        )
        notifications.broadcast(
            type=NotificationType.CASE_DELETED,
            title=f"Case {case_id} deleted",
            message=("Removed by an administrator. Linked cases refreshed: "
                     + (", ".join(result.get("refreshed_cases", [])) or "none")),
            case_id="",
        )
        return Response({"status": "deleted", **result})
