"""The pages a visitor sees when an address is wrong or Hrček fails."""

import pytest
from django.test import Client
from django.utils import timezone

from hrcek.accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email, **extra):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now(), **extra
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


@pytest.fixture
def admin():
    return _person("admin@example.com", is_staff=True, is_superuser=True)


# --- 404 -------------------------------------------------------------------


def test_a_missing_page_is_the_404_page(client):
    response = client.get("/no-such-address/")
    assert response.status_code == 404
    body = response.content.decode()
    assert "Page not found" in body
    assert "hrcek-404.png" in body
    assert 'alt=""' in body


def test_the_404_page_keeps_the_site_around_it(client, nina):
    client.force_login(nina)
    body = client.get("/no-such-address/").content.decode()
    # The header's navigation, and a way back to the entries.
    assert "/collections/" in body
    assert 'href="/entries/"' in body


def test_the_404_page_sends_a_stranger_to_the_start(client):
    body = client.get("/no-such-address/").content.decode()
    assert 'href="/"' in body
    assert 'href="/entries/"' not in body


def test_the_404_page_is_translated(client):
    body = client.get(
        "/no-such-address/", headers={"accept-language": "sl"}
    ).content.decode()
    assert "Page not found" not in body
    assert 'lang="sl"' in body


# --- 500 -------------------------------------------------------------------


@pytest.fixture
def failing():
    return Client(raise_request_exception=False)


@pytest.mark.urls("tests.core.error_urls")
def test_a_fault_is_the_500_page(failing):
    response = failing.get("/boom/")
    assert response.status_code == 500
    body = response.content.decode()
    assert "Something went wrong" in body
    assert "hrcek-500.png" in body
    assert 'href="/"' in body


@pytest.mark.urls("tests.core.error_urls")
def test_the_500_page_asks_nothing_of_the_failed_request(failing, nina):
    """Signed in or not, the page is the same: it is rendered without
    the request, so it cannot show navigation or a form that needs one."""
    failing.force_login(nina)
    body = failing.get("/boom/").content.decode()
    assert "csrfmiddlewaretoken" not in body
    assert "Sign out" not in body


@pytest.mark.urls("tests.core.error_urls")
def test_the_500_page_is_translated(failing):
    body = failing.get("/boom/", headers={"accept-language": "sl"}).content.decode()
    assert "Something went wrong" not in body
    assert 'lang="sl"' in body


@pytest.mark.urls("tests.core.error_urls")
def test_the_500_page_is_styled_and_themed(failing):
    body = failing.get("/boom/").content.decode()
    assert "css/hrcek.css" in body
    assert "hrcek-theme" in body


# --- previews --------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "heading"), [(404, "Page not found"), (500, "Something went wrong")]
)
def test_a_superuser_can_preview_each_error_page(client, admin, code, heading):
    client.force_login(admin)
    response = client.get(f"/errors/{code}/")
    assert response.status_code == code
    assert heading in response.content.decode()


@pytest.mark.parametrize("code", [404, 500])
def test_nobody_else_can_preview(client, nina, code):
    assert client.get(f"/errors/{code}/").status_code == 404
    client.force_login(nina)
    response = client.get(f"/errors/{code}/")
    assert response.status_code == 404
    assert "Page not found" in response.content.decode()


def test_staff_who_are_not_superusers_cannot_preview(client):
    client.force_login(_person("staff@example.com", is_staff=True))
    assert client.get("/errors/500/").status_code == 404
