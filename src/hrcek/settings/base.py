"""Settings shared by every environment."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import Any

from django.utils.translation import gettext_lazy as _

from hrcek.core.telemetry import configure_sentry
from hrcek.settings.env import (
    env_bool,
    env_float,
    env_int,
    env_list,
    env_str,
    load_dotenv,
)

BASE_DIR = Path(__file__).resolve().parents[3]

load_dotenv(BASE_DIR / ".env")

HRCEK_VERSION = version("hrcek")

# Every environment module either overrides this (dev, test) or requires
# it from the environment (prod). It must NOT be required here: base.py
# runs to completion before the module importing it can override
# anything, so a required read would make dev and test unimportable.
SECRET_KEY = env_str("HRCEK_SECRET_KEY", "")
DEBUG = env_bool("HRCEK_DEBUG", default=False)
ALLOWED_HOSTS = env_list("HRCEK_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    # Not "django.contrib.admin": this subclass swaps in Hrcek's own
    # admin site while keeping autodiscovery.
    "hrcek.accounts.admin_site.HrcekAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    "hrcek.core",
    "hrcek.accounts",
    "hrcek.entries",
    "hrcek.collections",
    "hrcek.ops",
]

MIDDLEWARE = [
    "hrcek.core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Session must precede authentication and locale; CSRF must precede
    # authentication.
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

API_DOCS_ENABLED = env_bool("HRCEK_API_DOCS", default=True)

ENTRIES_PER_PAGE = env_int("HRCEK_ENTRIES_PER_PAGE", 25)
HRCEK_MAX_BATCH = env_int("HRCEK_MAX_BATCH", 200)

LOGIN_URL = "landing"
LOGIN_REDIRECT_URL = "entries:list"
LOGOUT_REDIRECT_URL = "landing"

ROOT_URLCONF = "hrcek.urls"
WSGI_APPLICATION = "hrcek.wsgi.application"
ASGI_APPLICATION = "hrcek.asgi.application"

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
        "NAME": env_str("HRCEK_DB_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {
            # WAL lets readers proceed while a write is in flight, and
            # IMMEDIATE takes the write lock up front instead of failing
            # partway through. The right shape for one small writer.
            "init_command": "PRAGMA journal_mode=WAL;",
            "transaction_mode": "IMMEDIATE",
        },
    },
}

# Release bookkeeping for deploys and rollbacks. The history file and
# snapshots sit beside the database so one directory holds all state.
# See docs/dev/deployment.md.
HRCEK_RELEASE = env_str("HRCEK_RELEASE", "dev")
_DATA_DIR = Path(DATABASES["default"]["NAME"]).parent
HRCEK_RELEASES_FILE = _DATA_DIR / "releases.json"
HRCEK_BACKUP_PATH = Path(env_str("HRCEK_BACKUP_PATH", str(_DATA_DIR / "backups")))
HRCEK_BACKUP_KEEP = env_int("HRCEK_BACKUP_KEEP", 10)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "hrcek.accounts.backends.EmailOrDisplayNameBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", _("English")),
    ("sl", _("Slovenian")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

HRCEK_BASE_URL = env_str("HRCEK_BASE_URL", "http://localhost:8000")
HRCEK_INVITATION_EXPIRY_DAYS = env_int("HRCEK_INVITATION_EXPIRY_DAYS", 7)
HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS = env_int(
    "HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS", 48
)
DEFAULT_FROM_EMAIL = env_str("HRCEK_FROM_EMAIL", "hrcek@localhost")

# Django 6.1's mailers API. The old EMAIL_* settings, and the
# fail_silently and connection arguments, all raise
# RemovedInDjango70Warning, which this project's test suite treats as an
# error. Leaving MAILERS undefined warns too.
MAILERS: dict[str, dict[str, Any]] = {
    "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
}

STATIC_URL = "static/"

# Where rendered image copies are cached. The database holds the real
# thing; everything under here can be deleted and will be written again
# on the next request. See docs/dev/images.md.
MEDIA_ROOT = Path(env_str("HRCEK_MEDIA_PATH", str(BASE_DIR / "media")))

# Rate limits for the unauthenticated routes that hand out
# credentials. Counters live in Django's cache, which here is the
# per-process default: with one process that is exactly right, and
# with several each would keep its own tally. See docs/dev/api.md.
NINJA_DEFAULT_THROTTLE_RATES = {
    "token_exchange": env_str("HRCEK_TOKEN_EXCHANGE_RATE", "10/h"),
    "token_exchange_account": env_str("HRCEK_TOKEN_EXCHANGE_ACCOUNT_RATE", "10/h"),
}

# How many reverse proxies sit in front. Zero means "believe the
# socket, not the headers", which is the only safe default: with this
# unset, django-ninja takes the caller's identity from
# X-Forwarded-For whenever the header is present, so anyone could send
# a different value on each request and get a fresh rate-limit
# allowance every time. Set it to 1 behind a single nginx or Caddy,
# and the last hop it appends is believed instead.
NINJA_NUM_PROXIES = env_int("HRCEK_PROXY_COUNT", default=0)

DEBUG_SQL = env_bool("HRCEK_DEBUG_SQL", default=False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "hrcek.core.logging.JSONFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Named explicitly, and deliberately not propagating. Django's
        # own DEFAULT_LOGGING runs before this one and gives "django" a
        # plain-text console handler and a mail_admins handler. Leaving
        # the logger unmentioned keeps both of those *and* lets every
        # record travel on to the root handler here, so one event was
        # printed twice — once as text, once as JSON. See issue #52.
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG_SQL else "INFO",
            "propagate": False,
        },
    },
}

SENTRY_DSN = env_str("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = env_str("SENTRY_ENVIRONMENT", "development")
# Family-scale traffic: sampling would discard signal and save nothing.
SENTRY_TRACES_SAMPLE_RATE = env_float("SENTRY_TRACES_SAMPLE_RATE", 1.0)

configure_sentry(
    SENTRY_DSN,
    environment=SENTRY_ENVIRONMENT,
    release=f"hrcek@{HRCEK_VERSION}",
    traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
)
