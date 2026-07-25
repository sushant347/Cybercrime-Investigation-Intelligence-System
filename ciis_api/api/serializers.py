"""Input validation + output shaping.

The platform no longer uses the Django ORM, so there are no ModelSerializers:
records come out of ``api.store`` as plain dicts. The ``*_payload`` helpers
below shape those dicts for the API so field names stay stable for the SPA.
"""
from rest_framework import serializers


# ------------------------------------------------------------------- input
class CaseCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=256)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    notes = serializers.CharField(allow_blank=True, required=False, default="")
    tags = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False, default=list
    )


class EvidenceUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    notes = serializers.CharField(allow_blank=True, required=False, default="")


class AdminLoginSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=256, trim_whitespace=False)


# ------------------------------------------------------------------ output
def _int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def job_payload(row: dict) -> dict:
    return {
        "id": _int(row.get("id")),
        "job_type": row.get("job_type", ""),
        "status": row.get("status", ""),
        "case_id": row.get("case_id", ""),
        "evidence_id": row.get("evidence_id", "") or "",
        "detail": row.get("detail", "") or "",
        "error": row.get("error", "") or "",
        "created_by": row.get("created_by", "") or "",
        "created_at": row.get("created_at", ""),
        "finished_at": row.get("finished_at") or None,
    }


def notification_payload(row: dict) -> dict:
    return {
        "id": _int(row.get("id")),
        "type": row.get("type", ""),
        "title": row.get("title", ""),
        "message": row.get("message", "") or "",
        "case_id": row.get("case_id", "") or "",
        "evidence_id": row.get("evidence_id", "") or "",
        "read": bool(row.get("read")),
        "created_at": row.get("created_at", ""),
    }


def activity_payload(row: dict) -> dict:
    return {
        "id": _int(row.get("id")),
        "username": row.get("username", "") or "",
        "module": row.get("module", ""),
        "action": row.get("action", ""),
        "case_id": row.get("case_id", "") or "",
        "detail": row.get("detail", "") or "",
        "created_at": row.get("created_at", ""),
    }


def case_history_payload(row: dict) -> dict:
    return {
        "id": _int(row.get("id")),
        "case_id": row.get("case_id", ""),
        "username": row.get("username", "") or "",
        "action": row.get("action", ""),
        "detail": row.get("detail", "") or "",
        "created_at": row.get("created_at", ""),
    }
