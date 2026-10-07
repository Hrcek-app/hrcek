"""The "Take it out" on a collection's own page, in place with htmx."""

import re

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db

HTMX = {"HX-Request": "true"}


def _person(email):
    return User.objects.create_user(
        email=email,
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def nina(client):
    nina = _person("nina@example.com")
    client.force_login(nina)
    return nina


@pytest.fixture
def collection(nina):
    return Collection.objects.create(owner=nina, name="Watches")


def _on(collection, title):
    entry = Entry.objects.create(
        owner=collection.owner, url=f"https://example.com/{title}", title=title
    )
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return entry


def _take_out(collection, entry):
    return reverse("collections:remove_entry", args=[collection.pk, entry.pk])


def test_without_htmx_it_still_goes_back_to_the_collection(client, collection):
    entry = _on(collection, "First")

    response = client.post(_take_out(collection, entry))

    assert response.status_code == 302
    assert response["Location"] == reverse("collections:detail", args=[collection.pk])
    assert not collection.entries().exists()
    assert "HX-Request" in response["Vary"]


def test_htmx_answers_with_a_status_line(client, collection):
    entry = _on(collection, "First")
    _on(collection, "Second")

    response = client.post(_take_out(collection, entry), headers=HTMX)

    assert response.status_code == 200
    body = response.text
    assert "<html" not in body
    assert re.search(r'id="status"[^>]*hx-swap-oob="innerHTML"', body)
    assert "“First” taken out of “Watches”." in body
    assert "HX-Request" in response["Vary"]
    assert list(collection.entries()) == [Entry.objects.get(title="Second")]
    # Something is left, so the list stays.
    assert "Nothing in this collection yet." not in body


def test_htmx_taking_out_the_last_one_says_it_is_empty(client, collection):
    entry = _on(collection, "First")

    body = client.post(_take_out(collection, entry), headers=HTMX).text

    assert (
        '<p id="collection-entries" hx-swap-oob="true">'
        "Nothing in this collection yet.</p>"
    ) in body


def test_htmx_leaves_no_message_for_later(client, collection):
    entry = _on(collection, "First")
    client.post(_take_out(collection, entry), headers=HTMX)
    page = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert "taken out" not in page


def test_somebody_elses_collection_is_not_found(client, nina):
    marko = _person("marko@example.com")
    theirs = Collection.objects.create(owner=marko, name="Theirs")
    entry = _on(theirs, "Theirs")

    response = client.post(_take_out(theirs, entry), headers=HTMX)

    assert response.status_code == 404
    assert theirs.entries().exists()


def test_the_page_enhances_take_it_out(client, collection):
    entry = _on(collection, "First")

    body = client.get(reverse("collections:detail", args=[collection.pk])).text

    match = re.search(
        rf'<form method="post" action="{_take_out(collection, entry)}"[^>]*>', body
    )
    assert match
    form = match.group(0)
    assert f'hx-post="{_take_out(collection, entry)}"' in form
    assert 'hx-target="closest li"' in form
    assert 'hx-swap="delete"' in form
    assert 'hx-status:4xx="swap:none"' in form
    assert 'hx-status:5xx="swap:none"' in form
    assert '<ul class="entries" id="collection-entries">' in body
    assert "data-focus-after-delete" in body
    assert "data-focus-after-delete-fallback" in body


def test_an_empty_collection_page_has_the_same_empty_text(client, collection):
    body = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert '<p id="collection-entries">Nothing in this collection yet.</p>' in body


@pytest.mark.parametrize("headers", [{}, HTMX])
def test_a_label_collection_has_nothing_hand_picked_to_take_out(client, nina, headers):
    """Only the owner's hand-picked collections take entries out, the
    same rule the entry's own "+ Collection" line follows; a label
    collection is a 404 and keeps whatever it holds."""
    label = Tag.objects.create(owner=nina, name="watch")
    by_label = Collection.objects.create(
        owner=nina, name="Watched", kind=Collection.BY_LABEL, label=label
    )
    entry = Entry.objects.create(owner=nina, url="https://example.com/a", title="A")
    CollectionEntry.objects.create(collection=by_label, entry=entry)

    response = client.post(_take_out(by_label, entry), headers=headers)

    assert response.status_code == 404
    assert CollectionEntry.objects.filter(collection=by_label, entry=entry).exists()


def test_somebody_elses_collection_is_a_404(client, nina):
    other = _person("other@example.com")
    theirs = Collection.objects.create(owner=other, name="Theirs")
    entry = Entry.objects.create(owner=nina, url="https://example.com/a", title="A")

    response = client.post(_take_out(theirs, entry))

    assert response.status_code == 404
