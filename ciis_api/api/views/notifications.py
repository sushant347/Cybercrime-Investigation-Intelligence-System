"""Engine-wide notifications (no accounts, so no per-user inbox)."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..pagination import DefaultPagination
from ..serializers import notification_payload
from ..store import notifications


class NotificationListView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        rows = notifications.list(
            unread=request.query_params.get("unread") == "1",
            type=request.query_params.get("type", ""),
        )
        payload = [notification_payload(r) for r in rows]
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(payload, request)
        response = paginator.get_paginated_response(page)
        response.data["unread_count"] = notifications.unread_count()
        return response


class NotificationMarkReadView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        ids = request.data.get("ids")
        updated = notifications.mark_read(ids)
        return Response({"marked_read": updated})
