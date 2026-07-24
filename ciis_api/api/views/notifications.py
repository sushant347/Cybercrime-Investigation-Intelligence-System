"""Engine-wide notifications (no accounts, so no per-user inbox)."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Notification
from ..pagination import DefaultPagination
from ..serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        qs = Notification.objects.all()
        if request.query_params.get("unread") == "1":
            qs = qs.filter(read=False)
        ntype = request.query_params.get("type")
        if ntype:
            qs = qs.filter(type=ntype)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response(
            NotificationSerializer(page, many=True).data
        )
        response.data["unread_count"] = Notification.objects.filter(read=False).count()
        return response


class NotificationMarkReadView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        ids = request.data.get("ids")
        qs = Notification.objects.filter(read=False)
        if ids is not None:
            qs = qs.filter(id__in=ids)
        updated = qs.update(read=True)
        return Response({"marked_read": updated})
