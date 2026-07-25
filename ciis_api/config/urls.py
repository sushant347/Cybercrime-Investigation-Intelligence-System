"""Root URL config.

No Django admin and no accounts app: the project has no database and no user
model. Everything is served under ``/api/``.
"""
from django.urls import include, path

urlpatterns = [
    path("api/", include("api.urls")),
]
