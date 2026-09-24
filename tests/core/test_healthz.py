from unittest import mock

import pytest
from django.db import OperationalError

pytestmark = pytest.mark.django_db


def test_healthz_reports_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


def test_healthz_answers_a_host_that_is_not_allowed(client):
    # Docker's probe comes from inside the container as 127.0.0.1.
    response = client.get("/healthz", HTTP_HOST="127.0.0.1:8000")
    assert response.status_code == 200


def test_healthz_is_not_redirected_to_https(client, settings):
    settings.SECURE_SSL_REDIRECT = True
    assert client.get("/healthz").status_code == 200


def test_healthz_reports_a_broken_database(client):
    broken = mock.MagicMock()
    broken.cursor.side_effect = OperationalError("disk I/O error")
    with mock.patch("hrcek.core.middleware.connection", broken):
        response = client.get("/healthz")
    assert response.status_code == 503
