from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import RolePermission, User, UserPreference


class TokenSerializer(TokenObtainPairSerializer):
    """JWT pair enriched with the user profile (single round-trip login)."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ("theme", "language", "notifications_enabled", "items_per_page")


class UserSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    preference = UserPreferenceSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "username", "first_name", "last_name", "email",
            "role", "badge_number", "department", "is_active",
            "permissions", "preference", "date_joined", "last_login",
        )
        read_only_fields = ("date_joined", "last_login")

    def get_permissions(self, obj: User) -> list[str]:
        return obj.permissions()


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = (
            "username", "password", "first_name", "last_name", "email",
            "role", "badge_number", "department",
        )

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        UserPreference.objects.get_or_create(user=user)
        return user


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = ("id", "role", "permission")
