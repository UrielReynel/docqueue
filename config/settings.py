"""Django settings for docqueue.

Everything that changes between environments comes from environment variables,
so the same code runs locally, in CI and in production.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "jobs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DOCQUEUE_DB_PATH", BASE_DIR / "db.sqlite3"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DOCQUEUE_TIME_ZONE", "America/Merida")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_ROOT = Path(os.environ.get("DOCQUEUE_MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["jobs.auth.APIKeyAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "UNAUTHENTICATED_USER": None,
}

# --- docqueue settings -------------------------------------------------------
# Largest file the API accepts, in megabytes.
DOCQUEUE_MAX_UPLOAD_MB = int(os.environ.get("DOCQUEUE_MAX_UPLOAD_MB", "10"))
# Hour (local time, 0-23) when "nightly" jobs become eligible to run.
DOCQUEUE_NIGHTLY_HOUR = int(os.environ.get("DOCQUEUE_NIGHTLY_HOUR", "2"))
# How many times a job is tried before it is marked as failed.
DOCQUEUE_MAX_ATTEMPTS = int(os.environ.get("DOCQUEUE_MAX_ATTEMPTS", "3"))
# Base delay for the exponential retry backoff, in seconds.
DOCQUEUE_RETRY_BASE_SECONDS = int(os.environ.get("DOCQUEUE_RETRY_BASE_SECONDS", "30"))
