from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command


# The checks reach the database: JSONField asks the backend whether it
# supports JSON before it will pass.
@pytest.mark.django_db
def test_django_system_checks_pass():
    stderr = StringIO()
    call_command("check", stderr=stderr)
    assert stderr.getvalue() == ""


def test_version_is_exposed():
    assert settings.HRCEK_VERSION == "0.2.0"


def test_timezone_support_is_on():
    assert settings.USE_TZ is True


def test_debug_is_off_under_test_settings():
    assert settings.DEBUG is False
