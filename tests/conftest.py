import tomllib
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import translation

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@pytest.fixture(autouse=True)
def _reset_active_language():
    """Stop a request's language leaking into the next test.

    LocaleMiddleware activates the language a request asks for and does
    not deactivate it afterwards, so one test fetching a page with
    Accept-Language: sl leaves every later test in the process running
    in Slovenian. That makes assertions on English output fail depending
    on test order.
    """
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.activate(settings.LANGUAGE_CODE)


@pytest.fixture
def declared_version():
    """The version pyproject.toml declares, which a release bumps.

    Tests compare against this rather than a literal, so bumping the
    version does not mean editing them.
    """
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["project"]["version"]
