from rest_framework import serializers

from .models import ActivityLog, BackgroundJob, CaseHistory, CaseMeta, Notification


class CaseMetaSerializer(serializers.ModelSerializer):
    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True, default=None
    )

    class Meta:
        model = CaseMeta
        fields = (
            "case_id", "title", "description", "status", "priority_override",
            "assigned_to", "assigned_to_username", "tags",
            "created_at", "updated_at",
        )
        read_only_fields = ("case_id", "created_at", "updated_at")


class CaseHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseHistory
        fields = ("id", "case_id", "username", "action", "detail", "created_at")


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id", "type", "title", "message", "case_id",
            "evidence_id", "read", "created_at",
        )


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ("id", "username", "module", "action", "case_id", "detail", "created_at")


class BackgroundJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackgroundJob
        fields = (
            "id", "job_type", "status", "case_id", "evidence_id",
            "detail", "error", "created_by", "created_at", "finished_at",
        )


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
