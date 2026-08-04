"""CIIS API settings.

Thin presentation layer over the forensic engines. The engines are NEVER
modified - they are imported read-only from the roots below (see
``api/engine.py``, which is the only module that touches them).

Engine layout (a straight chain, each stage importing only the one before)::

    ENGINE_ROOT             evidence_ocr_engine          OCR / evidence
    CORRELATION_ROOT        evidence_correlation_engine  relationships
    TIMELINE_REPORT_ROOT    timeline_report_engine       timeline + output

The threat engine (``threat_intelligence_system``) plugs into the correlation
stage through a lazily-imported provider and needs no root here: it lives in
its own virtualenv and is reached by path only when ML scoring is enabled.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Root of the OCR / evidence-extraction engine (Phase 1).
ENGINE_ROOT = Path(
    os.environ.get("CIIS_ENGINE_ROOT", BASE_DIR.parent / "evidence_ocr_engine")
).resolve()

# Root of the correlation engine (Phase 2) - the analytical core.
CORRELATION_ROOT = Path(
    os.environ.get(
        "CIIS_CORRELATION_ROOT", BASE_DIR.parent / "evidence_correlation_engine"
    )
).resolve()

# Root of the timeline & report engine - the terminal stage, which owns the
# pipeline composition root the API drives.
TIMELINE_REPORT_ROOT = Path(
    os.environ.get(
        "CIIS_TIMELINE_REPORT_ROOT", BASE_DIR.parent / "timeline_report_engine"
    )
).resolve()

SECRET_KEY = os.environ.get(
    "CIIS_SECRET_KEY", "dev-only-insecure-key-change-in-production"
)
DEBUG = os.environ.get("CIIS_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get(
    "CIIS_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
).split(",")

# No database, no accounts: only the apps needed to serve the API. Django's
# ORM-backed contrib apps (admin/auth/contenttypes/sessions/messages) are all
# gone - platform state lives in CSV/JSON via ``api.store``.
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
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
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# ----------------------------------------------------------------- storage
# There is NO database. Platform workflow state (jobs, notifications, activity
# audit, case metadata/history) is stored as CSV/JSON under
# ``<engine storage>/platform/`` by ``api.store``; the forensic engine keeps its
# own CSV/JSON records. DATABASES is intentionally empty.
DATABASES = {}

# Admin role: a single shared password unlocks case administration (view all
# cases, delete a case). Override with CIIS_ADMIN_PASSWORD in any real
# deployment - the default exists so the feature works out of the box.
ADMIN_PASSWORD = os.environ.get("CIIS_ADMIN_PASSWORD", "hello123")
ADMIN_TOKEN_MAX_AGE = int(os.environ.get("CIIS_ADMIN_TOKEN_MAX_AGE", str(8 * 3600)))

REST_FRAMEWORK = {
    # No accounts and no authentication back-end: the engine is open access
    # (see api/permissions.py). Admin actions are gated by a separate shared
    # password, not by a user session.
    "DEFAULT_AUTHENTICATION_CLASSES": (),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    # django.contrib.auth is not installed, so there is no AnonymousUser to
    # fall back to; None keeps request.user harmless and import-free.
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "api.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "api.exceptions.api_exception_handler",
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

# ------------------------------------------------------------------ production
# Security headers/cookies are enabled automatically whenever DEBUG is off, so a
# production run (CIIS_DEBUG=0) is hardened without extra config. All are
# overridable by env for reverse-proxy setups that terminate TLS upstream.
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("CIIS_SSL_REDIRECT", "1") == "1"
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

# Phase-1 forensic analyses (integrity, EXIF/metadata, image quality, forgery
# indicators, logo/brand detection, evidence confidence) after OCR on upload.
# These write storage/forensics/<EVIDENCE_ID>/*.json, which is what the
# analytics quality panel, brand/device statistics, the forgery component of
# the priority score and the suspect scorer all read. With this off, every one
# of those reads zero - which is the state the platform shipped in, because the
# upload path never ran them at all. Set to "0" for fast tests or when an
# environment lacks the optional imaging dependencies.
ENGINE_RUN_FORENSICS = os.environ.get("CIIS_RUN_FORENSICS", "1") == "1"

# OCR engines for the multi-OCR fusion module. All off by default: each one
# performs a complete *second* OCR pass over an image the pipeline has already
# read, and EasyOCR/Tesseract are separate stacks (EasyOCR downloads model
# weights on first use). Nothing downstream consumes the fusion report today,
# so running it doubled upload latency for output no screen displays. Turn the
# engines on per deployment when fusion output is actually wanted.
FORENSICS_FUSION_PADDLE = os.environ.get("CIIS_FUSION_PADDLE", "0") == "1"
FORENSICS_FUSION_EASYOCR = os.environ.get("CIIS_FUSION_EASYOCR", "0") == "1"
FORENSICS_FUSION_TESSERACT = os.environ.get("CIIS_FUSION_TESSERACT", "0") == "1"

# ML threat intelligence: when enabled, Phase-2 analysis scores URL entities
# with the trained phishing classifier in ``threat_intelligence_system`` instead
# of (well, in addition to falling back to) the static indicator file. The ML
# stack is imported lazily and degrades gracefully if unavailable, so enabling
# this never breaks a deployment that lacks the ML dependencies/model artifact.
# Enabled by default: a URL submitted as evidence is useless in a report
# without a verdict, and the adapter already degrades to the static indicator
# file when the ML stack or model artifact is missing. Set to "0" to force the
# static provider (e.g. an air-gapped deployment).
ML_THREAT_INTEL_ENABLED = os.environ.get("CIIS_ML_THREAT_INTEL", "1") == "1"
ML_THREAT_INTEL_ROOT = Path(
    os.environ.get(
        "CIIS_THREAT_INTEL_ROOT", BASE_DIR.parent / "threat_intelligence_system"
    )
).resolve()
ML_THREAT_INTEL_MODEL = os.environ.get("CIIS_THREAT_INTEL_MODEL", "xgboost")

# Live enrichment (WHOIS / DNS / SSL / GeoIP) behind the URL verdict. This is
# what supplies domain age, registrar, SPF/DMARC and hosting - the facts an
# investigator actually cites - so it is on by default. It costs a few seconds
# per *distinct* URL (results are memoized) and each connector fails soft, so
# an offline host still gets the ML verdict, just without the network facts.
ML_THREAT_INTEL_LIVE = os.environ.get("CIIS_THREAT_INTEL_LIVE", "1") == "1"

# Build the OCR engine and the post-OCR text chain in a background thread at
# startup, instead of on the first upload. Constructing PaddleOCR loads its
# detection/recognition/orientation models, which is tens of seconds of work
# that used to land inside the first investigator's upload - while they watched
# a spinner - and made the whole product feel slow exactly once per restart,
# every restart. Warming it concurrently with the server coming up moves that
# cost to a moment when nobody is waiting. Set to "0" for fast test runs and
# short-lived management commands.
ENGINE_WARM_START = os.environ.get("CIIS_WARM_START", "1") == "1"
