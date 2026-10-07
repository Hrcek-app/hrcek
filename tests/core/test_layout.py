"""Centred pages and Django's flash messages, rendered by base.html."""

from html.parser import HTMLParser

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import AllowedDomain, Invitation, User
from hrcek.collections.models import Collection, GotIt
from hrcek.entries.models import Tag
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email, **extra):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now(), **extra
    )


@pytest.fixture
def person():
    return _person("layout@example.com")


class _MainClass(HTMLParser):
    """Record the class of the first <main> the page renders."""

    def __init__(self) -> None:
        super().__init__()
        self.classes: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "main" and self.classes is None:
            raw = dict(attrs).get("class") or ""
            self.classes = [str(name) for name in raw.split()]


def main_classes(html: str) -> list[str]:
    parser = _MainClass()
    parser.feed(html)
    assert parser.classes is not None, "main carries no class"
    return parser.classes


# --- width ------------------------------------------------------------

CENTRED = [
    "/",
    "/accounts/signup/",
    "/accounts/password/reset/",
    "/accounts/password/reset/sent/",
    "/accounts/password/reset/done/",
    "/accounts/password/reset/Mg/bad-token/",
]


@pytest.mark.parametrize("path", CENTRED)
def test_sign_in_pages_are_centred(client, path):
    assert "mx-auto" in main_classes(client.get(path).content.decode())


def test_the_404_page_is_centred(client):
    assert "mx-auto" in main_classes(client.get("/no-such-page/").content.decode())


def test_working_pages_are_not_centred(client, person):
    client.force_login(person)
    assert "mx-auto" not in main_classes(client.get("/accounts/me/").content.decode())


def test_signup_done_is_centred(client):
    AllowedDomain.objects.create(domain="example.com")
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "new@example.com",
            "display_name": "",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert "mx-auto" in main_classes(response.content.decode())


def test_invitation_accept_is_centred(client):
    admin = _person("admin@example.com", is_staff=True, is_superuser=True)
    _invitation, raw = Invitation.issue("nina@example.com", admin)
    response = client.get(reverse("accounts:invitation_accept", args=[raw]))
    assert "mx-auto" in main_classes(response.content.decode())


def test_an_invalid_invitation_shows_a_centred_message_page(client):
    response = client.get(reverse("accounts:invitation_accept", args=["rubbish"]))
    assert "mx-auto" in main_classes(response.content.decode())


def test_a_refused_signup_shows_a_centred_message_page(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "nina@elsewhere.com",
            "display_name": "",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert "mx-auto" in main_classes(response.content.decode())


def test_error_preview_500_is_centred(client):
    admin = _person("admin2@example.com", is_staff=True, is_superuser=True)
    client.force_login(admin)
    response = client.get("/errors/500/")
    assert "mx-auto" in main_classes(response.content.decode())


# --- messages -----------------------------------------------------------


def test_a_message_renders_once_with_its_level(client, person):
    client.force_login(person)
    response = client.post(
        "/entries/new/", {"url": "https://example.com/"}, follow=True
    )
    body = response.content.decode()
    assert body.count('class="messages"') == 1
    assert 'role="status"' in body
    assert 'class="success"' in body


def _label_wish_list(owner, tag_name="want"):
    tag, _created = Tag.objects.get_or_create(owner=owner, name=tag_name)
    return Collection.objects.create(
        owner=owner,
        name="Wants",
        kind=Collection.BY_LABEL,
        label=tag,
        visibility=Collection.UNLISTED,
        is_wish_list=True,
    )


def test_a_message_with_a_link_keeps_the_link(client, person):
    """The "came back" message in entries/views.py is built with
    format_html. Rendering it through base.html's single {{ message }}
    must not escape the link it carries."""
    entry, _created = save_entry(
        person, url="https://example.com/watch", tag_names=["want"]
    )
    wishes = _label_wish_list(person)
    GotIt.objects.create(
        collection=wishes, entry=entry, got_by=_person("ana@example.com")
    )
    # Keep the tag alive elsewhere, then take it off this entry so
    # putting it back is news, not a no-op.
    save_entry(person, url="https://example.com/keep", tag_names=["want"])
    entry.tags.clear()

    client.force_login(person)
    response = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": "want"},
        follow=True,
    )
    body = response.content.decode()
    link = f'<a href="/collections/{wishes.pk}/?back={entry.pk}">'
    assert body.count(link) == 1
    assert "Put it back on the list?" in body
