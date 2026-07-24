"""CIIS API settings.

Thin presentation layer over the Phase 1/2 forensic engines.
The engines are NEVER modified - they are imported read-only from
``ENGINE_ROOT`` (see ``api/engine.py``).
"""
from datetime import timedelta
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Root of the completed forensic engine (Phase 1 + Phase 2).
ENGINE_ROOT = Path(
    os.environ.get("CIIS_ENGINE_ROOT", BASE_DIR.parent / "evidence_ocr_engine")
).resolve()

SECRET_KEY = os.environ.get(
    "CIIS_SECRET_KEY", "dev-only-insecure-key-change-in-production"
)
DEBUG = os.environ.get("CIIS_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get(
    "CIIS_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "accounts",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# Workflow database (holds ONLY workflow state - jobs, notifications, audit
# rows; the forensic engine's CSV/JSON remain the source of truth). Defaults to
# SQLite for zero-config dev; set CIIS_DB_ENGINE=postgres + the CIIS_DB_* vars
# for a production Postgres deployment.
if os.environ.get("CIIS_DB_ENGINE", "sqlite").lower() in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("CIIS_DB_NAME", "ciis"),
            "USER": os.environ.get("CIIS_DB_USER", "ciis"),
            "PASSWORD": os.environ.get("CIIS_DB_PASSWORD", ""),
            "HOST": os.environ.get("CIIS_DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("CIIS_DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("CIIS_DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.environ.get("CIIS_DB_PATH", BASE_DIR / "ciis_platform.sqlite3")),
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # No accounts: the engine is open access (see accounts/permissions.py).
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_PAGINATION_CLASS": "api.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "EXCEPTION_HANDLER": "api.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CIIS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- static/media
STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("CIIS_STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("CIIS_MEDIA_ROOT", BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ production
# Security headers/cookies are enabled automatically whenever DEBUG is off, so a
# production run (CIIS_DEBUG=0) is hardened without extra config. All are
# overridable by env for reverse-proxy setups that terminate TLS upstream.
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("CIIS_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("CIIS_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"
    # Fail fast if someone ships the insecure dev key to production.
    if SECRET_KEY == "dev-only-insecure-key-change-in-production":
        raise RuntimeError(
            "CIIS_SECRET_KEY must be set to a strong secret when CIIS_DEBUG=0."
        )

# --------------------------------------------------------------------- logging
LOG_LEVEL = os.environ.get("CIIS_LOG_LEVEL", "DEBUG" if DEBUG else "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"}
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "ciis": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "ciis.engine": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# Max evidence upload size accepted by the API layer (engine enforces its own).
DATA_UPLOAD_MAX_MEMORY_SIZE = 55 * 1024 * 1024

# When true (default), the API upload worker runs the FULL Phase-1 chain
# (OCR -> cleaning -> enhancement -> semantic -> entity extraction) via
# ``EvidenceProcessingOrchestrator`` so web-uploaded evidence produces the
# entities that Phase-2 (correlation/graph/campaigns/suspects) depends on.
# Set to "0" to fall back to the legacy OCR-only behaviour (e.g. fast tests
# or environments without the heavier enhancement/semantic stages).
ENGINE_RUN_FULL_PIPELINE = os.environ.get("CIIS_RUN_FULL_PIPELINE", "1") == "1"

# ML threat intelligence: when enabled, Phase-2 analysis scores URL entities
# with the trained phishing classifier in ``threat_intelligence_system`` instead
# of (well, in addition to falling back to) the static indicator file. The ML
# stack is imported lazily and degrades gracefully if unavailable, so enabling
# this never breaks a deployment that lacks the ML dependencies/model artifact.
ML_THREAT_INTEL_ENABLED = os.environ.get("CIIS_ML_THREAT_INTEL", "0") == "1"
ML_THREAT_INTEL_ROOT = Path(
    os.environ.get(
        "CIIS_THREAT_INTEL_ROOT", BASE_DIR.parent / "threat_intelligence_system"
    )
).resolve()
ML_THREAT_INTEL_MODEL = os.environ.get("CIIS_THREAT_INTEL_MODEL", "xgboost")
