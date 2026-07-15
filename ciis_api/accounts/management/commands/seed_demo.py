"""Seed demo users (one per role). Usage: python manage.py seed_demo"""
from django.core.management.base import BaseCommand

from accounts.models import Role, User, UserPreference

DEMO_USERS = [
    ("admin", Role.ADMINISTRATOR, "Ava", "Sharma"),
    ("investigator", Role.INVESTIGATOR, "Ishan", "Thapa"),
    ("analyst", Role.ANALYST, "Anita", "Rai"),
    ("viewer", Role.VIEWER, "Vik", "Gurung"),
]


class Command(BaseCommand):
    help = "Create demo users for each role (password: Ciis@Demo2026)"

    def handle(self, *args, **options):
        for username, role, first, last in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role, "first_name": first, "last_name": last,
                    "email": f"{username}@ciis.local",
                    "is_staff": role == Role.ADMINISTRATOR,
                    "is_superuser": role == Role.ADMINISTRATOR,
                },
            )
            if created:
                user.set_password("Ciis@Demo2026")
                user.save()
                UserPreference.objects.get_or_create(user=user)
                self.stdout.write(self.style.SUCCESS(f"Created {username} ({role})"))
            else:
                self.stdout.write(f"{username} already exists")
