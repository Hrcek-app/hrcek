"""Production settings. Every secret comes from the environment."""

from hrcek.settings.base import *  # noqa: F403
from hrcek.settings.env import env_bool, env_int, env_list, env_str

DEBUG = False
API_DOCS_ENABLED = False
SECRET_KEY = env_str("HRCEK_SECRET_KEY")
ALLOWED_HOSTS = env_list("HRCEK_ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"

# Behind a TLS-terminating proxy the request reaches us as plain HTTP,
# and SECURE_SSL_REDIRECT would redirect it forever. Believe the
# proxy's X-Forwarded-Proto only when a proxy is declared, exactly as
# the rate limiter treats X-Forwarded-For (see base.py).
if NINJA_NUM_PROXIES > 0:  # noqa: F405
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The container serves its own static files, so it works behind any
# proxy without a shared volume.
MIDDLEWARE = [*MIDDLEWARE]  # noqa: F405
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": env_str("HRCEK_SMTP_HOST"),
            "port": env_int("HRCEK_SMTP_PORT", 587),
            "username": env_str("HRCEK_SMTP_USER", ""),
            "password": env_str("HRCEK_SMTP_PASSWORD", ""),
            "use_tls": env_bool("HRCEK_SMTP_USE_TLS", default=True),
        },
    },
}
