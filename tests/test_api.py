import json

import pytest
from django.test import override_settings

from hrcek.core import errors

pytestmark = pytest.mark.django_db


def test_api_docs_are_served(client):
    assert client.get("/api/docs").status_code == 200


def test_health_endpoint_reports_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "hrcek"
    assert body["version"] == "0.2.0"
    assert body["message"]


@override_settings(ROOT_URLCONF="tests.urls_errors")
def test_known_error_renders_code_message_and_details(client):
    response = client.get("/api/known")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "HRC-CORE-0003",
            "message": "The requested resource does not exist.",
            "details": {"field": "url"},
        }
    }


@override_settings(ROOT_URLCONF="tests.urls_errors")
def test_django_404_is_rendered_as_a_registered_code(client):
    response = client.get("/api/django-404")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == errors.NOT_FOUND.code


@override_settings(ROOT_URLCONF="tests.urls_errors")
def test_validation_failure_is_rendered_as_a_registered_code(client):
    response = client.post(
        "/api/validated",
        data=json.dumps({"count": "not-a-number"}),
        content_type="application/json",
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == errors.VALIDATION_ERROR.code
    assert body["error"]["details"]["fields"]


@override_settings(ROOT_URLCONF="tests.urls_errors")
def test_unexpected_error_leaks_nothing(client, caplog):
    response = client.get("/api/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {
        "code": "HRC-CORE-0001",
        "message": "An unexpected error occurred.",
        "details": {},
    }
    # The secret is in the traceback, so it must be in the log and
    # nowhere near the response body.
    assert "hunter2" not in response.content.decode()
    assert "hunter2" in caplog.text


@override_settings(ROOT_URLCONF="tests.urls_errors")
def test_unexpected_error_is_reported_to_sentry(client, monkeypatch):
    captured = []
    monkeypatch.setattr("hrcek.api.capture_exception", captured.append)
    client.get("/api/boom")
    assert len(captured) == 1
    assert isinstance(captured[0], RuntimeError)
