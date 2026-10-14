"""
NyumbaFind Django settings.

Secrets are loaded from a local ``.env`` file (python-dotenv) or environment
variables. Never commit real secrets to version control.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load .env from the project root when present (local development).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core settings
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-change-me-in-production",
)

DEBUG = os.getenv("DJANGO_DEBUG", "True").strip().lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

# Vercel sets VERCEL=1 at runtime. Allow all *.vercel.app
# hosts automatically so a missing DJANGO_ALLOWED_HOSTS
# never bricks a deployment. Custom domains still need to
# be listed via DJANGO_ALLOWED_HOSTS.
if os.getenv("VERCEL", "").strip() == "1" and ".vercel.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")

# Platforms like Vercel terminate TLS and forward the original
# protocol/host via X-Forwarded-* headers. Trust them (only when
# explicitly enabled — Vercel sets VERCEL=1 at runtime) so Django
# treats requests as HTTPS, builds correct absolute URLs, and the
# CSRF referer check accepts secure origins.
if os.getenv("VERCEL", "").strip() == "1" or os.getenv(
    "DJANGO_SECURE_PROXY", ""
).strip().lower() in ("1", "true", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    # Local apps
    "accounts",
    "properties",
    "reviews",
    "landlords",
    "ai",
    "payments",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nyumbafind.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nyumbafind.wsgi.application"
ASGI_APPLICATION = "nyumbafind.asgi.application"

# ---------------------------------------------------------------------------
# Database: SQLite by default, PostgreSQL via DATABASE_URL for production
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    _parsed = urlparse(DATABASE_URL)
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _parsed.path.lstrip("/"),
        "USER": _parsed.username or "",
        "PASSWORD": _parsed.password or "",
        "HOST": _parsed.hostname or "127.0.0.1",
        "PORT": _parsed.port or "5432",
    }

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "ai": os.getenv("AI_RATE_LIMIT", "10/min"),
    },
}

# ---------------------------------------------------------------------------
# CORS: restricted to explicitly configured origins
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = False

# Origins trusted by CSRF protection for cross-origin unsafe
# requests (POST etc.). Must include the scheme, e.g.
# "https://nyumbafind-eight.vercel.app". Same-origin requests
# are covered automatically; set this via DJANGO_CSRF_TRUSTED_ORIGINS.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# ---------------------------------------------------------------------------
# Static files & media uploads
# ---------------------------------------------------------------------------
# WhiteNoise serves /static/ from STATIC_ROOT in production.
# Run `python manage.py collectstatic --noinput` during the
# build step on Vercel (or any PaaS) so the files are collected.
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "frontend"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Maximum uploaded image size (5 MB)
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")

# ---------------------------------------------------------------------------
# AI assistant configuration
# ---------------------------------------------------------------------------
AI_PROVIDER = os.getenv("AI_PROVIDER", "rule_based").strip().lower() or "rule_based"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
AI_MAX_MESSAGE_LENGTH = 500

# ---------------------------------------------------------------------------
# M-Pesa Daraja configuration (credentials from environment only)
# ---------------------------------------------------------------------------
MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox").strip().lower() or "sandbox"
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "").strip()
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "").strip()
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "").strip()
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "").strip()
MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "").strip()
# Optional: registered Daraja initiator for TransactionStatusQuery
# (used only for manual reconciliation).
MPESA_INITIATOR = os.getenv("MPESA_INITIATOR", "").strip()
MPESA_SECURITY_CREDENTIAL = os.getenv("MPESA_SECURITY_CREDENTIAL", "").strip()

# ---------------------------------------------------------------------------
# Internationalisation & security defaults
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Speed up the test suite: use a fast (non-production) password hasher.
import sys  # noqa: E402

if "test" in sys.argv:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]

# Email (console backend for development; configure SMTP for production)
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# Production hardening flags (opt-in via environment)
if os.getenv("DJANGO_SECURE", "").strip().lower() in ("1", "true", "yes"):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
