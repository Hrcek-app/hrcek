from urllib.parse import parse_qs, urlsplit

import pytest
from django.http import HttpResponseRedirect
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.core.middleware import HtmxSignInRedirectMiddleware
from hrcek.core.request_id import REQUEST_ID_HEADER, is_acceptable

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


@pytest.fixture
def nina():
    return User.objects.create_user(
        email="nina@example.com", password=PASSWORD, email_verified_at=timezone.now()
    )


def test_response_carries_a_request_id(client):
    response = client.get("/api/health")
    assert response.headers[REQUEST_ID_HEADER]


def test_a_valid_incoming_request_id_is_reused(client):
    response = client.get("/api/health", headers={"x-request-id": "abc-123_XYZ"})
    assert response.headers[REQUEST_ID_HEADER] == "abc-123_XYZ"


@pytest.mark.parametrize(
    "hostile",
    ["a" * 65, "has spaces", "semi;colon", ""],
)
def test_an_unacceptable_incoming_request_id_is_replaced(client, hostile):
    response = client.get("/api/health", headers={"x-request-id": hostile})
    assert response.headers[REQUEST_ID_HEADER] != hostile
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_the_request_id_is_tagged_on_sentry(client, monkeypatch):
    tags = {}
    monkeypatch.setattr("hrcek.core.middleware.set_tag", tags.__setitem__)
    response = client.get("/api/health")
    assert tags["request_id"] == response.headers[REQUEST_ID_HEADER]


@pytest.mark.parametrize(
    "value",
    ["abc", "a" * 64, "with.dots-and_underscores"],
)
def test_is_acceptable_accepts_sane_ids(value):
    assert is_acceptable(value) is True


@pytest.mark.parametrize(
    "value",
    ["", "a" * 65, "has spaces", "semi;colon", "inject\r\nX-Evil: 1", "a\nb"],
)
def test_is_acceptable_rejects_anything_header_unsafe(value):
    # Django's test client refuses CR/LF in headers outright, so these
    # cases can only be exercised against the predicate directly.
    assert is_acceptable(value) is False


def test_an_expired_session_on_a_plain_request_redirects_normally(client):
    response = client.get(reverse("entries:list"))
    assert response.status_code == 302
    assert "HX-Redirect" not in response


def test_an_expired_session_on_an_htmx_request_gets_a_full_redirect(client):
    response = client.get(reverse("entries:list"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response["HX-Redirect"].startswith("/?next=")


def test_a_csrf_failure_on_an_htmx_request_gets_a_full_redirect(nina):
    client = Client(enforce_csrf_checks=True)
    client.force_login(nina)
    response = client.post(
        "/entries/999999/delete/", {}, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert response["HX-Redirect"].startswith("/?next=")


def test_a_csrf_failure_on_a_plain_request_is_untouched(nina):
    client = Client(enforce_csrf_checks=True)
    client.force_login(nina)
    response = client.post("/entries/999999/delete/", {})
    assert response.status_code == 403
    assert "HX-Redirect" not in response


def test_a_redirect_elsewhere_on_an_htmx_request_is_left_alone(rf):
    """Only a redirect to the sign-in page is rewritten."""

    def get_response(request):
        return HttpResponseRedirect("/somewhere-else/")

    middleware = HtmxSignInRedirectMiddleware(get_response)
    request = rf.get("/", headers={"HX-Request": "true"})
    response = middleware(request)
    assert response.status_code == 302
    assert response["Location"] == "/somewhere-else/"


def _next_of(response):
    return parse_qs(urlsplit(response["HX-Redirect"]).query)["next"][0]


CURRENT = "http://testserver/entries/?tag=7&page=2"


def test_an_expired_session_returns_to_the_page_the_request_came_from(client):
    """Not to the URL htmx posted to: signing in and landing on a
    POST-only URL with a GET is a blank 405."""
    response = client.post(
        "/entries/1/delete/",
        headers={"HX-Request": "true", "HX-Current-URL": CURRENT},
    )
    assert _next_of(response) == "/entries/?tag=7&page=2"


def test_a_csrf_failure_returns_to_the_page_the_request_came_from(nina):
    client = Client(enforce_csrf_checks=True)
    client.force_login(nina)
    response = client.post(
        "/entries/999999/delete/",
        {},
        headers={"HX-Request": "true", "HX-Current-URL": CURRENT},
    )
    assert _next_of(response) == "/entries/?tag=7&page=2"


@pytest.mark.parametrize(
    "current",
    [None, "https://elsewhere.example/entries/", "javascript:alert(1)", ""],
)
def test_a_missing_or_foreign_current_url_falls_back_to_the_entries(client, current):
    headers = {"HX-Request": "true"}
    if current is not None:
        headers["HX-Current-URL"] = current
    response = client.post("/entries/1/delete/", headers=headers)
    assert _next_of(response) == reverse("entries:list")


@pytest.mark.parametrize(
    "current",
    [None, "https://elsewhere.example/entries/"],
)
def test_a_csrf_failure_with_no_usable_current_url_falls_back(nina, current):
    client = Client(enforce_csrf_checks=True)
    client.force_login(nina)
    headers = {"HX-Request": "true"}
    if current is not None:
        headers["HX-Current-URL"] = current
    response = client.post("/entries/999999/delete/", {}, headers=headers)
    assert _next_of(response) == reverse("entries:list")
