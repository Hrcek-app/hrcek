"""Settings for the test suite: fast, deterministic, offline."""

from pathlib import Path

from hrcek.settings.base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-insecure-not-a-real-secret"  # noqa: S105
ALLOWED_HOSTS = ["testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

# The suite must never reach Sentry.
SENTRY_DSN = ""

MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
}

# The in-memory database has no folder to sit beside, and a test must
# never touch the repository's own files. Tests that need these point
# them at tmp_path (tests/ops/conftest.py); anything else fails loudly.
HRCEK_RELEASES_FILE = Path("/nonexistent/hrcek-tests/releases.json")
HRCEK_BACKUP_PATH = Path("/nonexistent/hrcek-tests/backups")
