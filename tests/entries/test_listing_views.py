"""The two ways to show a list of entries on your own entries page.

A list of wide rows with a small picture, or picture-led cards. The
choice belongs to the account: the last one picked is what the page
shows next time, on any device.
"""

import io
import re

import pytest
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from hrcek.accounts.models import User
from hrcek.core.listing import CARDS, LIST
from hrcek.entries.models import Entry, EntryImage

pytestmark = pytest.mark.django_db


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (1, 2, 3)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def nina():
    return User.objects.create_user(
        email="nina@example.com",
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def signed_in(client, nina):
    client.force_login(nina)
    return client


def _list_classes(body: str) -> list[str]:
    match = re.search(r'<ul class="([^"]*\bentries\b[^"]*)"', body)
    assert match, "no entries list on the page"
    return match.group(1).split()


def _choose(client, view, **extra):
    return client.post(reverse("entries:view"), {"view": view, **extra})


def test_a_new_account_starts_with_the_list(signed_in, nina):
    Entry.objects.create(owner=nina, url="https://example.com/a")
    assert nina.entry_view == LIST
    body = signed_in.get(reverse("entries:list")).text
    assert "view-list" in _list_classes(body)


def test_choosing_cards_is_remembered(signed_in, nina):
    Entry.objects.create(owner=nina, url="https://example.com/a")
    response = _choose(signed_in, CARDS)
    assert response.status_code == 302
    nina.refresh_from_db()
    assert nina.entry_view == CARDS
    body = signed_in.get(reverse("entries:list")).text
    assert "view-cards" in _list_classes(body)


def test_choosing_goes_back_to_the_page_it_came_from(signed_in, nina):
    back = reverse("entries:list") + "?page=2"
    response = _choose(signed_in, CARDS, next=back)
    assert response["Location"] == back


def test_a_return_address_elsewhere_is_ignored(signed_in):
    response = _choose(signed_in, CARDS, next="https://evil.example/")
    assert response["Location"] == reverse("entries:list")


def test_an_unknown_view_changes_nothing(signed_in, nina):
    _choose(signed_in, CARDS)
    _choose(signed_in, "carousel")
    nina.refresh_from_db()
    assert nina.entry_view == CARDS


def test_choosing_needs_a_session(client):
    response = _choose(client, CARDS)
    assert response.status_code == 302
    assert reverse("landing") in response["Location"]


def test_choosing_only_answers_post(signed_in):
    assert signed_in.get(reverse("entries:view")).status_code == 405


def test_the_switch_says_which_view_is_shown(signed_in, nina):
    Entry.objects.create(owner=nina, url="https://example.com/a")
    _choose(signed_in, CARDS)
    body = signed_in.get(reverse("entries:list")).text
    switch = body[body.index('class="view-switch"') :]
    switch = switch[: switch.index("</form>")]
    assert re.search(r'value="cards"[^>]*aria-pressed="true"', switch)
    assert re.search(r'value="list"[^>]*aria-pressed="false"', switch)


def test_the_switch_returns_to_the_page_and_label_shown(signed_in, nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/a")
    entry.tags.create(owner=nina, name="watches")
    body = signed_in.get(reverse("entries:list") + "?tag=watches").text
    switch = body[body.index('class="view-switch"') :]
    assert 'name="next" value="/entries/?tag=watches"' in switch


def test_the_switch_is_there_with_no_entries_yet(signed_in):
    body = signed_in.get(reverse("entries:list")).text
    assert 'class="view-switch"' in body


def test_cards_show_a_placeholder_for_an_entry_without_a_picture(signed_in, nina):
    Entry.objects.create(owner=nina, url="https://example.com/a")
    _choose(signed_in, CARDS)
    body = signed_in.get(reverse("entries:list")).text
    assert 'class="entry-thumb placeholder"' in body


def test_cards_show_the_picture_when_there_is_one(signed_in, nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/a")
    EntryImage.attach(entry, _png())
    _choose(signed_in, CARDS)
    body = signed_in.get(reverse("entries:list")).text
    assert reverse("entries:image", args=[entry.pk]) in body
    assert "placeholder" not in body


def test_the_list_shows_no_placeholder(signed_in, nina):
    Entry.objects.create(owner=nina, url="https://example.com/a")
    body = signed_in.get(reverse("entries:list")).text
    assert "placeholder" not in body
