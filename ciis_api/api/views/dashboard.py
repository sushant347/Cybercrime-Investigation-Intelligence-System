"""Dashboard aggregates - counts come from engine storage + platform state."""
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import require

from .. import engine
from ..models import ActivityLog, BackgroundJob, CaseMeta, CaseStatus, Notification
from ..serializers import ActivityLogSerializer, BackgroundJobSerializer


class DashboardView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request):
        cases = engine.list_cases()
        evidence = engine.list_evidence()
        meta = {m.case_id: m for m in CaseMeta.objects.all()}

        def status_of(case_id: str) -> str:
            m = meta.get(case_id)
            return m.status if m else CaseStatus.OPEN

        statuses = [status_of(c["case_id"]) for c in cases]
        case_ids = [c["case_id"] for c in cases]

        # Priority + threat distributions straight from engine artifacts.
        priority_distribution: dict[str, int] = {}
        campaign_count = 0
        threat_distribution: dict[str, int] = {}
        high_priority_cases: list[dict] = []
        for cid, payload in engine.iter_case_artifact(case_ids, "priority"):
            band = str(
                payload.get("priority_band") or payload.get("band")
                or payload.get("priority_level") or "unknown"
            ).lower()
            priority_distribution[band] = priority_distribution.get(band, 0) + 1
            if band in {"high", "critical", "urgent"}:
                high_priority_cases.append(
                    {"case_id": cid, "band": band,
                     "score": payload.get("priority_score") or payload.get("score")}
                )
        for cid, payload in engine.iter_case_artifact(case_ids, "campaigns"):
            campaigns = (
                payload.get("campaigns")
                or payload.get("detected_campaigns")
                or []
            )
            campaign_count += len(campaigns) if isinstance(campaigns, list) else 0
        for cid, payload in engine.iter_case_artifact(case_ids, "analytics"):
            dist = payload.get("threat_distribution") or {}
            if isinstance(dist, dict):
                for k, v in dist.items():
                    if isinstance(v, (int, float)):
                        threat_distribution[k] = threat_distribution.get(k, 0) + int(v)

        recent_jobs = BackgroundJob.objects.all()[:8]
        recent_activity = ActivityLog.objects.all()[:10]

        return Response(
            {
                "totals": {
                    "cases": len(cases),
                    "active_cases": sum(
                        1 for s in statuses if s in (CaseStatus.OPEN, CaseStatus.ACTIVE)
                    ),
                    "completed_cases": statuses.count(CaseStatus.COMPLETED),
                    "archived_cases": statuses.count(CaseStatus.ARCHIVED),
                    "evidence": len(evidence),
                    "high_priority_cases": len(high_priority_cases),
                    "campaigns": campaign_count,
                    "unread_notifications": Notification.objects.filter(
                        read=False
                    ).count(),
                },
                "priority_distribution": priority_distribution,
                "threat_distribution": threat_distribution,
                "high_priority_cases": sorted(
                    high_priority_cases,
                    key=lambda c: (c["score"] is None, -(c["score"] or 0)),
                )[:5],
                "processing": BackgroundJobSerializer(recent_jobs, many=True).data,
                "recent_activity": ActivityLogSerializer(recent_activity, many=True).data,
                "engine_health": engine.engine_health(),
            }
        )
