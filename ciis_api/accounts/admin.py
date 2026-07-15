from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import RolePermission, User, UserPreference


@admin.register(User)
class CiisUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("CIIS", {"fields": ("role", "badge_number", "department")}),
    )
    list_display = ("username", "email", "role", "is_active")


admin.site.register(RolePermission)
admin.site.register(UserPreference)
