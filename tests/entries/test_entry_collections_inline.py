"""Adding an entry to a collection, and taking it out, from the list."""

import re

import pytest
from django.conf import settings
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, GotIt
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"
HTMX = {"HX-Request": "true"}


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def person(client):
    person = _person("nina@example.com")
    client.force_login(person)
    return person


@pytest.fixture
def entry(person):
    return Entry.objects.create(owner=person, url="https://example.com/a", title="A")


@pytest.fixture
def mine(person):
    return Collection.objects.create(owner=person, name="Mine", kind=Collection.MANUAL)


def _add(entry):
    return reverse("entries:collection_add", args=[entry.pk])


def _remove(entry):
    return reverse("entries:collection_remove", args=[entry.pk])


def _held(entry, collection):
    return CollectionEntry.objects.filter(collection=collection, entry=entry).exists()


def _messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


# Without htmx: a round trip, as any other form.


def test_adding_puts_the_entry_in_the_collection(client, person, entry, mine):
    response = client.post(_add(entry), {"collection": mine.pk})

    assert response.status_code == 302
    assert response["Location"] == reverse("entries:list")
    assert _held(entry, mine)
    assert _messages(response) == ["Added to “Mine”."]


def test_taking_out_removes_the_entry_from_the_collection(client, person, entry, mine):
    CollectionEntry.objects.create(collection=mine, entry=entry)

    response = client.post(_remove(entry), {"collection": mine.pk})

    assert response.status_code == 302
    assert not _held(entry, mine)
    assert _messages(response) == ["Taken out of “Mine”."]


def test_it_goes_back_to_the_page_it_came_from(client, person, entry, mine):
    response = client.post(
        _add(entry), {"collection": mine.pk, "next": "/entries/?page=2"}
    )
    assert response["Location"] == "/entries/?page=2"


def test_it_never_goes_back_off_site(client, person, entry, mine):
    response = client.post(
        _add(entry), {"collection": mine.pk, "next": "https://evil.example/"}
    )
    assert response["Location"] == reverse("entries:list")


@pytest.mark.parametrize(
    "view", ["entries:collection_add", "entries:collection_remove"]
)
def test_only_post_is_answered(client, person, entry, view):
    assert client.get(reverse(view, args=[entry.pk])).status_code == 405


@pytest.mark.parametrize(
    "view", ["entries:collection_add", "entries:collection_remove"]
)
def test_signed_out_is_sent_to_sign_in(client, entry, mine, view):
    client.logout()
    response = client.post(reverse(view, args=[entry.pk]), {"collection": mine.pk})
    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))


def test_somebody_elses_entry_is_not_found(client, person, mine):
    theirs = Entry.objects.create(
        owner=_person("marko@example.com"), url="https://example.com/b"
    )
    assert client.post(_add(theirs), {"collection": mine.pk}).status_code == 404
    assert client.post(_remove(theirs), {"collection": mine.pk}).status_code == 404
    assert not _held(theirs, mine)


def test_somebody_elses_collection_is_refused(client, person, entry):
    marko = _person("marko@example.com")
    theirs = Collection.objects.create(
        owner=marko, name="Theirs", kind=Collection.MANUAL
    )

    assert client.post(_add(entry), {"collection": theirs.pk}).status_code == 404
    assert not _held(entry, theirs)


def test_a_label_collection_is_refused(client, person, entry):
    tag = Tag.objects.create(owner=person, name="watches")
    by_label = Collection.objects.create(
        owner=person, name="Watches", kind=Collection.BY_LABEL, label=tag
    )

    assert client.post(_add(entry), {"collection": by_label.pk}).status_code == 404
    assert client.post(_remove(entry), {"collection": by_label.pk}).status_code == 404
    assert not _held(entry, by_label)


@pytest.mark.parametrize("value", ["", "x", "999999", "-1"])
def test_a_missing_or_unknown_collection_is_refused(client, person, entry, value):
    assert client.post(_add(entry), {"collection": value}).status_code == 404


def test_adding_twice_is_harmless(client, person, entry, mine):
    client.post(_add(entry), {"collection": mine.pk})
    response = client.post(_add(entry), {"collection": mine.pk})
    assert response.status_code == 302
    assert CollectionEntry.objects.filter(collection=mine, entry=entry).count() == 1


# The wish list "already got" notice, as the entry form gives it.


@pytest.fixture
def wishes(person):
    return Collection.objects.create(
        owner=person, name="Wants", kind=Collection.MANUAL, is_wish_list=True
    )


def _got_then_taken_off(entry, wishes):
    """Got by somebody while on the list, then taken off it by its owner."""
    CollectionEntry.objects.create(collection=wishes, entry=entry)
    GotIt.objects.create(
        collection=wishes, entry=entry, got_by=_person("ana@example.com")
    )
    CollectionEntry.objects.filter(collection=wishes, entry=entry).delete()


def test_adding_back_onto_a_wish_list_says_it_was_already_got(
    client, person, entry, wishes
):
    _got_then_taken_off(entry, wishes)

    response = client.post(_add(entry), {"collection": wishes.pk})

    assert "Somebody has already got this for “Wants”." in " ".join(_messages(response))


def test_adding_to_a_wish_list_nobody_got_it_from_says_nothing_more(
    client, person, entry, wishes
):
    response = client.post(_add(entry), {"collection": wishes.pk})
    assert _messages(response) == ["Added to “Wants”."]


def test_adding_again_to_a_wish_list_it_is_already_on_says_nothing_more(
    client, person, entry, wishes
):
    CollectionEntry.objects.create(collection=wishes, entry=entry)
    GotIt.objects.create(
        collection=wishes, entry=entry, got_by=_person("ana@example.com")
    )

    response = client.post(_add(entry), {"collection": wishes.pk})

    assert _messages(response) == ["Added to “Wants”."]


# With htmx: this entry's collections line, and the status line.


def test_htmx_gets_the_collections_line_and_a_status(client, person, entry, mine):
    response = client.post(_add(entry), {"collection": mine.pk}, headers=HTMX)

    assert response.status_code == 200
    body = response.text
    assert body.startswith(
        f'<div class="entry-collections" id="collections-{entry.pk}"'
    )
    assert re.search(r'id="status"[^>]*hx-swap-oob="innerHTML"', body)
    assert "Added to “Mine”." in body
    assert "<html" not in body
    assert "HX-Request" in response["Vary"]
    assert _held(entry, mine)


def test_htmx_taking_out_gets_the_line_and_a_status(client, person, entry, mine):
    CollectionEntry.objects.create(collection=mine, entry=entry)

    response = client.post(_remove(entry), {"collection": mine.pk}, headers=HTMX)

    assert response.status_code == 200
    assert "Taken out of “Mine”." in response.text
    assert "HX-Request" in response["Vary"]
    assert not _held(entry, mine)


def test_the_plain_answer_varies_on_htmx_too(client, person, entry, mine):
    response = client.post(_add(entry), {"collection": mine.pk})
    assert "HX-Request" in response["Vary"]


def test_htmx_drains_the_already_got_notice_in_place(client, person, entry, wishes):
    _got_then_taken_off(entry, wishes)

    response = client.post(_add(entry), {"collection": wishes.pk}, headers=HTMX)

    body = response.text
    assert 'id="messages" role="status" hx-swap-oob="true"' in body
    assert "Somebody has already got this for “Wants”." in body
    # Said once, here; not again on whatever page comes next.
    assert "already got" not in client.get(reverse("entries:list")).text


def test_htmx_queues_no_message_for_later(client, person, entry, mine):
    client.post(_add(entry), {"collection": mine.pk}, headers=HTMX)
    assert "Added to" not in client.get(reverse("entries:list")).text


# What the line offers.


def test_a_hand_picked_collection_has_a_way_out(client, person, entry, mine):
    CollectionEntry.objects.create(collection=mine, entry=entry)

    body = client.get(reverse("entries:list")).text

    assert 'aria-label="Take “A” out of “Mine”"' in body
    assert f'action="{_remove(entry)}"' in body


def test_a_label_collection_is_a_plain_link(client, person, entry):
    Tag.set_for(entry, ["watches"])
    tag = Tag.objects.get(owner=person, name="watches")
    by_label = Collection.objects.create(
        owner=person, name="Watches", kind=Collection.BY_LABEL, label=tag
    )

    body = client.get(reverse("entries:list")).text

    assert f'<a href="{reverse("collections:detail", args=[by_label.pk])}">' in body
    assert "out of “Watches”" not in body
    assert f'action="{_remove(entry)}"' not in body
    # Nor is it offered to add to.
    assert f'name="collection" value="{by_label.pk}"' not in body


def test_the_pill_offers_the_hand_picked_collections_it_is_not_in(
    client, person, entry, mine
):
    other = Collection.objects.create(
        owner=person, name="Other", kind=Collection.MANUAL
    )
    CollectionEntry.objects.create(collection=mine, entry=entry)
    Collection.objects.create(
        owner=_person("marko@example.com"), name="Theirs", kind=Collection.MANUAL
    )

    body = client.get(reverse("entries:list")).text

    assert 'class="add-pill collection-add js-only"' in body
    assert "+ Collection" in body
    match = re.search(r"<details.*?</details>", body, re.S)
    assert match
    pill = match.group(0)
    assert f'name="collection" value="{other.pk}"' in pill
    assert f'name="collection" value="{mine.pk}"' not in pill
    assert "Theirs" not in body


def test_no_pill_when_it_is_in_every_hand_picked_collection(
    client, person, entry, mine
):
    CollectionEntry.objects.create(collection=mine, entry=entry)
    body = client.get(reverse("entries:list")).text
    assert "+ Collection" not in body


def test_no_pill_and_no_line_without_hand_picked_collections(client, person, entry):
    body = client.get(reverse("entries:list")).text
    assert "+ Collection" not in body
    assert "entry-collections" not in body


def test_the_pill_alone_when_it_is_in_nothing_yet(client, person, entry, mine):
    body = client.get(reverse("entries:list")).text
    assert "+ Collection" in body
    assert "In:" not in body


def test_the_pill_is_for_javascript_only(client, person, entry, mine):
    """Without JavaScript the edit form is the way; the pill is drawn
    only once a script says it can work."""
    body = client.get(reverse("entries:list")).text
    assert '<details class="add-pill collection-add js-only"' in body


def test_after_taking_out_focus_goes_to_the_pill(client, person, entry, mine):
    CollectionEntry.objects.create(collection=mine, entry=entry)
    body = client.post(_remove(entry), {"collection": mine.pk}, headers=HTMX).text
    assert re.search(r"<summary[^>]*autofocus", body)


def test_after_adding_focus_goes_to_the_pill_while_there_is_more(
    client, person, entry, mine
):
    Collection.objects.create(owner=person, name="Other", kind=Collection.MANUAL)
    body = client.post(_add(entry), {"collection": mine.pk}, headers=HTMX).text
    assert re.search(r"<summary[^>]*autofocus", body)
    assert not re.search(r"<details[^>]* open", body)


def test_after_adding_the_last_one_focus_goes_to_its_way_out(
    client, person, entry, mine
):
    body = client.post(_add(entry), {"collection": mine.pk}, headers=HTMX).text
    assert "<summary" not in body
    assert re.search(
        r'<button[^>]*aria-label="Take “A” out of “Mine”"[^>]*autofocus', body
    )


def test_the_pill_alone_is_for_javascript_only_as_a_whole(client, person, entry, mine):
    """In nothing yet, the line is only the pill: without JavaScript the
    whole line must take no room, not just the pill inside it."""
    body = client.get(reverse("entries:list")).text
    assert (
        f'<div class="entry-collections js-only" id="collections-{entry.pk}">' in body
    )


def test_a_line_with_collections_is_shown_without_javascript(
    client, person, entry, mine
):
    CollectionEntry.objects.create(collection=mine, entry=entry)
    body = client.get(reverse("entries:list")).text
    assert f'<div class="entry-collections" id="collections-{entry.pk}">' in body
