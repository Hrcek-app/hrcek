from tests.support import run_manage

PROD_ENV = {
    "HRCEK_SECRET_KEY": "x" * 50,
    "HRCEK_ALLOWED_HOSTS": "hrcek.example.com",
    "HRCEK_SMTP_HOST": "localhost",
}


def _shell(tmp_path, code, *, settings_module="hrcek.settings.prod", **env):
    return run_manage(
        "shell",
        "--no-imports",
        "-c",
        code,
        data_dir=tmp_path,
        settings_module=settings_module,
        env={**PROD_ENV, **env},
    ).stdout.strip()


PROXY_HEADER = (
    "from django.conf import settings; print(settings.SECURE_PROXY_SSL_HEADER)"
)


def test_the_proxy_tls_header_is_ignored_without_a_proxy(tmp_path):
    assert _shell(tmp_path, PROXY_HEADER) == "None"


def test_the_proxy_tls_header_is_trusted_behind_a_proxy(tmp_path):
    assert _shell(tmp_path, PROXY_HEADER, HRCEK_PROXY_COUNT="1") == (
        "('HTTP_X_FORWARDED_PROTO', 'https')"
    )


def test_production_serves_static_files_itself(tmp_path):
    code = (
        "from django.conf import settings; m = settings.MIDDLEWARE; "
        "print(m.index('whitenoise.middleware.WhiteNoiseMiddleware') "
        "- m.index('django.middleware.security.SecurityMiddleware'))"
    )
    assert _shell(tmp_path, code) == "1"


def test_sentry_is_told_the_release(tmp_path):
    code = "import sentry_sdk; print(sentry_sdk.get_client().options['release'])"
    shown = _shell(
        tmp_path,
        code,
        settings_module="hrcek.settings.dev",
        HRCEK_RELEASE="v9.9.9",
        SENTRY_DSN="https://key@example.invalid/1",
    )
    assert shown == "hrcek@v9.9.9"
