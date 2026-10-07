import pytest
from django.conf import settings
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import AllowedDomain, AllowedEmail, User

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


@pytest.fixture
def person():
    return User.objects.create_user(
        email="nina@example.com",
        password=PASSWORD,
        email_verified_at=timezone.now(),
    )


def test_the_landing_page_is_at_the_root(client):
    # Both halves of the claim: the name resolves to "/", and "/" really
    # renders the landing page rather than merely answering 200.
    assert reverse("landing") == "/"
    response = client.get("/")
    assert response.status_code == 200
    assert "accounts/landing.html" in [t.name for t in response.templates]


def test_it_offers_a_login_form_and_a_reset_link(client):
    body = client.get("/").content.decode()
    assert 'name="username"' in body
    assert 'name="password"' in body
    assert reverse("accounts:password_reset") in body


def test_it_does_not_advertise_signup_while_nobody_may_sign_up(client):
    # The form would reject everyone who found it there.
    assert reverse("accounts:signup") not in client.get("/").content.decode()


def test_it_offers_signup_once_a_domain_is_allowed(client):
    AllowedDomain.objects.create(domain="example.com")
    assert reverse("accounts:signup") in client.get("/").content.decode()


def test_it_offers_signup_once_an_address_is_allowed(client):
    AllowedEmail.objects.create(email="ana@example.org")
    assert reverse("accounts:signup") in client.get("/").content.decode()


def test_a_signed_in_visitor_is_redirected_away(client, person):
    client.force_login(person)
    response = client.get("/")
    assert response.status_code == 302
    # Where it lands matters: against LOGIN_REDIRECT_URL so the
    # assertion survives the destination moving, and explicitly not back
    # to "/", which would be a redirect loop.
    assert response["Location"] == resolve_url(settings.LOGIN_REDIRECT_URL)
    assert response["Location"] != "/"


def test_a_confirmed_user_can_log_in(client, person):
    response = client.post("/", {"username": "nina@example.com", "password": PASSWORD})
    assert response.status_code == 302
    assert response.wsgi_request.user.is_authenticated


def test_an_unconfirmed_user_cannot_log_in(client):
    """The API already refuses these; the web form used to let them in."""
    User.objects.create_user(email="new@example.com", password=PASSWORD)
    response = client.post("/", {"username": "new@example.com", "password": PASSWORD})
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated
    assert "Confirm your email address" in response.content.decode()


def test_a_wrong_password_says_nothing_about_the_account(client, person):
    known = client.post("/", {"username": "nina@example.com", "password": "no"})
    unknown = client.post("/", {"username": "nobody@example.com", "password": "no"})
    assert known.status_code == unknown.status_code == 200
    # Comparing whole bodies would only compare CSRF tokens; the thing
    # that must not differ is the validation outcome.
    assert known.context["form"].errors == unknown.context["form"].errors
