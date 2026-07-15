from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from api.models import ActivityLog

from .models import Permission, RolePermission, User, UserPreference
from .permissions import require
from .serializers import (
    RolePermissionSerializer,
    TokenSerializer,
    UserCreateSerializer,
    UserPreferenceSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = TokenSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            ActivityLog.record(
                username=request.data.get("username", ""),
                module="auth", action="login", detail="Successful login",
            )
        return response


class LogoutView(APIView):
    """Blacklist-free logout: client discards tokens; we audit the event."""

    def post(self, request):
        try:
            refresh = request.data.get("refresh")
            if refresh:
                RefreshToken(refresh)  # validate shape; ignore result
        except Exception:  # noqa: BLE001 - logout must never fail
            pass
        ActivityLog.record(
            username=request.user.username, module="auth",
            action="logout", detail="User logged out",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        UserPreference.objects.get_or_create(user=self.request.user)
        return self.request.user


class MyPreferenceView(generics.RetrieveUpdateAPIView):
    serializer_class = UserPreferenceSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
        return pref


class UserViewSet(viewsets.ModelViewSet):
    """Administrator user management."""

    queryset = User.objects.all().order_by("username")
    permission_classes = (require("user.manage"),)
    search_fields = ("username", "first_name", "last_name", "email", "badge_number")
    filterset_fields = ("role", "is_active")

    def get_serializer_class(self):
        return UserCreateSerializer if self.action == "create" else UserSerializer


class RolePermissionView(APIView):
    """Read / replace the configurable role -> permission matrix."""

    permission_classes = (require("user.manage"),)

    def get(self, request):
        matrix: dict[str, list[str]] = {}
        for role in ("administrator", "investigator", "analyst", "viewer"):
            probe = User(role=role)
            matrix[role] = probe.permissions()
        return Response(
            {
                "matrix": matrix,
                "available_permissions": [
                    {"code": p.value, "label": p.label} for p in Permission
                ],
            }
        )

    def put(self, request):
        serializer = RolePermissionSerializer(data=request.data.get("entries", []), many=True)
        serializer.is_valid(raise_exception=True)
        role = request.data.get("role")
        if not role:
            return Response({"detail": "role is required"}, status=400)
        RolePermission.objects.filter(role=role).delete()
        RolePermission.objects.bulk_create(
            RolePermission(role=role, permission=e["permission"])
            for e in serializer.validated_data
            if e["role"] == role
        )
        ActivityLog.record(
            username=request.user.username, module="auth",
            action="rbac_update", detail=f"Permissions updated for role '{role}'",
        )
        return self.get(request)
