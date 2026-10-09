import re

import pytest
from django.core import mail
from django.urls import reverse

from hrcek.accounts.models import AllowedDomain, User
from hrcek.accounts.tokens import make_confirmation_token

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


@pytest.fixture
def open_domain():
    return AllowedDomain.objects.create(domain="example.com")


def _signup(client, email="nina@example.com", display_name=""):
    return client.post(
        reverse("accounts:signup"),
        {
            "email": email,
            "display_name": display_name,
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )


def test_an_allowed_address_creates_an_unconfirmed_user(client, open_domain):
    response = _signup(client)
    assert response.status_code == 200
    user = User.objects.get(email="nina@example.com")
    assert user.is_email_confirmed is False
    assert len(mail.outbox) == 1


def test_a_disallowed_address_is_refused_with_its_code(client):
    response = _signup(client, email="nina@elsewhere.com")
    # A policy refusal, so it carries the same status the API would use.
    assert response.status_code == 403
    assert "HRC-ACCT-0001" in response.content.decode()
    assert not User.objects.filter(email="nina@elsewhere.com").exists()
    assert mail.outbox == []


def _scrubbed(response) -> bytes:
    """The page minus its CSRF masks.

    Django salts the rendered CSRF token differently on every response,
    so the footer's language form, and the token handed to htmx on
    <body>, make byte-identical pages impossible. The mask differs
    between any two requests, regardless of whether an account exists,
    so it is noise to this comparison, not a signal.
    """
    content = re.sub(
        rb'name="csrfmiddlewaretoken" value="[^"]*"',
        b'name="csrfmiddlewaretoken" value="scrubbed"',
        response.content,
    )
    return re.sub(rb'"X-CSRFToken": "[^"]*"', b'"X-CSRFToken": "scrubbed"', content)


def test_an_existing_address_is_indistinguishable(client, open_domain):
    # Otherwise the signup form tells any stranger who has an account.
    fresh = _signup(client, email="new@example.com")
    User.objects.create_user(email="taken@example.com", password=PASSWORD)
    mail.outbox.clear()
    existing = _signup(client, email="taken@example.com")

    assert existing.status_code == fresh.status_code
    assert _scrubbed(existing) == _scrubbed(fresh)


def test_an_existing_address_gets_a_warning_email(client, open_domain):
    User.objects.create_user(email="taken@example.com", password=PASSWORD)
    mail.outbox.clear()
    _signup(client, email="taken@example.com")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["taken@example.com"]
    assert "already" in str(mail.outbox[0].body).lower()


def test_signing_up_twice_does_not_create_a_second_user(client, open_domain):
    _signup(client)
    _signup(client)
    assert User.objects.filter(email="nina@example.com").count() == 1


def test_a_weak_password_is_refused(client, open_domain):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "nina@example.com",
            "display_name": "",
            "password1": "abc",
            "password2": "abc",
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(email="nina@example.com").exists()


def test_a_taken_display_name_is_refused(client, open_domain):
    User.objects.create_user(
        email="other@example.com", password=PASSWORD, display_name="Nina"
    )
    _signup(client, display_name="nina")
    assert not User.objects.filter(email="nina@example.com").exists()


def test_a_valid_confirmation_link_confirms_the_address(client, open_domain):
    _signup(client)
    user = User.objects.get(email="nina@example.com")
    response = client.get(
        reverse("accounts:confirm", args=[make_confirmation_token(user)])
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.is_email_confirmed is True


def test_a_tampered_confirmation_link_is_refused(client, open_domain):
    _signup(client)
    user = User.objects.get(email="nina@example.com")
    token = make_confirmation_token(user)
    response = client.get(reverse("accounts:confirm", args=[token[:-1] + "x"]))
    assert response.status_code == 400
    assert "HRC-ACCT-0003" in response.content.decode()
    user.refresh_from_db()
    assert user.is_email_confirmed is False


def test_an_expired_confirmation_link_is_refused(client, open_domain, settings):
    _signup(client)
    user = User.objects.get(email="nina@example.com")
    token = make_confirmation_token(user)
    settings.HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS = 0
    response = client.get(reverse("accounts:confirm", args=[token]))
    assert response.status_code == 400
    assert "HRC-ACCT-0003" in response.content.decode()


def test_the_confirmation_email_carries_a_working_link(client, open_domain):
    _signup(client)
    body = str(mail.outbox[0].body)
    token = body.split("/accounts/confirm/")[1].split("/", maxsplit=1)[0]
    assert client.get(reverse("accounts:confirm", args=[token])).status_code == 302
