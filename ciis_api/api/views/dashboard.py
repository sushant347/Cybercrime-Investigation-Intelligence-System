"""Dashboard aggregates - counts come from engine storage + platform state."""
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import require

from .. import engine
from ..constants import CaseStatus
from ..serializers import activity_payload, job_payload
from ..store import activity, case_meta, jobs, notifications


class DashboardView(APIView):
    permission_classes = (require("case.view"),)

    def get(self, request):
        cases = engine.list_cases()
        evidence = engine.list_evidence()
        meta = {m["case_id"]: m for m in case_meta.all_decoded()}

        def status_of(case_id: str) -> str:
            m = meta.get(case_id)
            return (m.get("status") if m else None) or CaseStatus.OPEN

        statuses = [status_of(c["case_id"]) for c in cases]
        case_ids = [c["case_id"] for c in cases]

        # Priority + threat distributions straight from engine artifacts.
        priority_distribution: dict[str, int] = {}
        campaign_count = 0
        threat_distribution: dict[str, int] = {}
        high_priority_cases: list[dict] = []
        # One pass over the cases for all three artifacts (was three passes,
        # each re-listing every case directory).
        entity_total = 0
        analysed_cases = 0
        cases_with_threats = 0
        for cid, artifacts in engine.iter_case_artifacts(
            case_ids, ("priority", "campaigns", "analytics")
        ):
            payload = artifacts.get("priority")
            if payload:
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

            payload = artifacts.get("campaigns")
            if payload:
                campaigns = (
                    payload.get("campaigns")
                    or payload.get("detected_campaigns")
                    or []
                )
                campaign_count += len(campaigns) if isinstance(campaigns, list) else 0
            # Threat verdicts and entity totals.
            #
            # This used to read ``threat_distribution`` off the analytics
            # artifact - a key the engine has never written (the analytics
            # model calls it ``threat_statistics``), so the dashboard's threat
            # panel was empty on every deployment regardless of what the cases
            # contained.
            payload = artifacts.get("analytics")
            if payload:
                analysed_cases += 1
                stats = payload.get("threat_statistics") or {}
                if isinstance(stats, dict):
                    for verdict, key in (
                        ("malicious", "malicious_indicators"),
                        ("suspicious", "suspicious_indicators"),
                        ("benign", "benign_indicators"),
                    ):
                        value = stats.get(key)
                        if isinstance(value, (int, float)) and value:
                            threat_distribution[verdict] = (
                                threat_distribution.get(verdict, 0) + int(value)
                            )
                    if float(stats.get("evidence_with_threats") or 0) > 0:
                        cases_with_threats += 1
                entities = payload.get("entity_statistics") or {}
                if isinstance(entities, dict):
                    entity_total += sum(
                        int(v) for v in entities.values()
                        if isinstance(v, (int, float))
                    )

        recent_jobs = jobs.list(limit=8)
        recent_activity = activity.list(limit=10)

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
                    "unread_notifications": notifications.unread_count(),
                    # Coverage: how much of the workload has actually been
                    # analysed, so an empty chart can be explained rather than
                    # read as "nothing found".
                    "analysed_cases": analysed_cases,
                    "cases_with_threats": cases_with_threats,
                    "entities_extracted": entity_total,
                },
                "priority_distribution": priority_distribution,
                "threat_distribution": threat_distribution,
                "high_priority_cases": sorted(
                    high_priority_cases,
                    key=lambda c: (c["score"] is None, -(c["score"] or 0)),
                )[:5],
                "processing": [job_payload(j) for j in recent_jobs],
                "recent_activity": [activity_payload(a) for a in recent_activity],
                "engine_health": engine.engine_health(),
            }
        )
