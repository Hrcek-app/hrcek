import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import translation

from hrcek.core import errors

pytestmark = pytest.mark.django_db


def test_configured_languages_are_english_and_slovenian():
    assert [code for code, _name in settings.LANGUAGES] == ["en", "sl"]


def test_error_message_is_translated_into_slovenian():
    with translation.override("en"):
        english = str(errors.NOT_FOUND.message)
    with translation.override("sl"):
        slovenian = str(errors.NOT_FOUND.message)
    assert english == "The requested resource does not exist."
    assert slovenian != english
    assert slovenian.strip() != ""


def test_health_endpoint_answers_in_the_requested_language(client):
    english = client.get("/api/health", headers={"accept-language": "en"})
    slovenian = client.get("/api/health", headers={"accept-language": "sl"})
    assert english.json()["message"] == "Service is running."
    assert slovenian.json()["message"] != english.json()["message"]


@override_settings(ROOT_URLCONF="tests.urls_errors")
def test_error_response_is_translated(client):
    response = client.get("/api/known", headers={"accept-language": "sl"})
    body = response.json()
    # The code is stable across languages; only the message moves.
    assert body["error"]["code"] == "HRC-CORE-0003"
    assert body["error"]["message"] != "The requested resource does not exist."
