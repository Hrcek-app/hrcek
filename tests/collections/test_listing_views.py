"""A collection's own view: list or cards, chosen by its owner.

The collection's view is what everybody who opens it sees first, the
owner and visitors alike. Anyone may switch for the visit they are on;
that is never saved, so the next visit shows the collection's view
again.
"""

import io
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, GotIt
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


def _person(email, **extra):
    return User.objects.create_user(
        email=email,
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
        **extra,
    )


@pytest.fixture
def nina():
    return _person("nina@example.com", namespace="nina")


@pytest.fixture
def ana():
    return _person("ana@example.com")


def _collection(nina, title="https://example.com/watch", **extra):
    collection = Collection.objects.create(owner=nina, name="Watches", **extra)
    entry = Entry.objects.create(owner=nina, url=title)
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return collection, entry


def _list_classes(body: str) -> list[str]:
    match = re.search(r'<ul class="([^"]*\bentries\b[^"]*)"', body)
    assert match, "no entries list on the page"
    return match.group(1).split()


def _form_data(**extra):
    data = {"name": "Watches", "description": "", "kind": Collection.MANUAL}
    data.update(extra)
    return data


# --- The setting -----------------------------------------------------------


def test_a_new_collection_shows_a_list(nina):
    collection, _ = _collection(nina)
    assert collection.view == LIST


def test_the_owner_chooses_cards_on_the_form(client, nina):
    client.force_login(nina)
    client.post(reverse("collections:create"), _form_data(view=CARDS))
    assert Collection.objects.get(owner=nina).view == CARDS


def test_the_form_offers_both_views(client, nina):
    client.force_login(nina)
    body = client.get(reverse("collections:create")).text
    assert 'name="view" value="list"' in body
    assert 'name="view" value="cards"' in body


@pytest.mark.parametrize("visibility", [Collection.UNLISTED, Collection.PUBLIC])
def test_shared_cards_need_pictures(client, nina, visibility):
    client.force_login(nina)
    response = client.post(
        reverse("collections:create"),
        _form_data(view=CARDS, visibility=visibility),
    )
    assert response.status_code == 200
    assert not Collection.objects.exists()
    assert "Pictures" in response.text


def test_shared_cards_with_pictures_are_fine(client, nina):
    client.force_login(nina)
    client.post(
        reverse("collections:create"),
        _form_data(view=CARDS, visibility=Collection.UNLISTED, show_images="on"),
    )
    assert Collection.objects.get(owner=nina).view == CARDS


def test_private_cards_need_no_pictures_ticked(client, nina):
    client.force_login(nina)
    client.post(reverse("collections:create"), _form_data(view=CARDS))
    assert Collection.objects.get(owner=nina).view == CARDS


# --- The owner's page ------------------------------------------------------


def test_the_owner_page_uses_the_collections_view(client, nina):
    collection, _ = _collection(nina, view=CARDS)
    client.force_login(nina)
    body = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert "view-cards" in _list_classes(body)


def test_the_owner_can_switch_for_this_visit_only(client, nina):
    collection, _ = _collection(nina, view=CARDS)
    client.force_login(nina)
    url = reverse("collections:detail", args=[collection.pk])
    body = client.get(url + "?view=list").text
    assert "view-list" in _list_classes(body)
    collection.refresh_from_db()
    nina.refresh_from_db()
    assert collection.view == CARDS
    assert nina.entry_view == LIST
    assert "view-cards" in _list_classes(client.get(url).text)


def test_an_unknown_view_in_the_address_is_ignored(client, nina):
    collection, _ = _collection(nina, view=CARDS)
    client.force_login(nina)
    url = reverse("collections:detail", args=[collection.pk])
    assert "view-cards" in _list_classes(client.get(url + "?view=wall").text)


def test_your_own_saved_view_does_not_override_a_collection(client, nina):
    collection, _ = _collection(nina, view=LIST)
    nina.entry_view = CARDS
    nina.save()
    client.force_login(nina)
    body = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert "view-list" in _list_classes(body)


def test_the_switch_links_keep_the_reveal(client, nina):
    collection, _ = _collection(nina, is_wish_list=True)
    client.force_login(nina)
    url = reverse("collections:detail", args=[collection.pk])
    body = client.get(url + "?got=show").text
    switch = body[body.index('class="view-switch"') :]
    assert "?got=show&amp;view=cards" in switch


def test_the_owner_sees_pictures_on_their_own_page(client, nina):
    collection, entry = _collection(nina)
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    body = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert reverse("entries:image", args=[entry.pk]) in body


def test_owner_cards_show_a_placeholder_without_a_picture(client, nina):
    collection, _ = _collection(nina, view=CARDS)
    client.force_login(nina)
    body = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert 'class="entry-thumb placeholder"' in body


def test_the_owner_page_leaves_the_blobs_in_the_table(client, nina):
    collection, entry = _collection(nina, view=CARDS)
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    url = reverse("collections:detail", args=[collection.pk])
    with CaptureQueriesContext(connection) as queries:
        client.get(url)
    blobs = [q["sql"] for q in queries if '"original"' in q["sql"]]
    assert blobs == []


@pytest.mark.parametrize("view", [LIST, CARDS])
def test_a_revealed_wish_list_marks_what_was_got_in_both_views(client, nina, ana, view):
    collection, entry = _collection(
        nina, is_wish_list=True, visibility=Collection.UNLISTED, show_images=True
    )
    GotIt.objects.create(collection=collection, entry=entry, got_by=ana)
    client.force_login(nina)
    url = reverse("collections:detail", args=[collection.pk])
    body = client.get(f"{url}?got=show&view={view}").text
    assert 'class="is-got"' in body
    assert reverse("collections:put_back", args=[collection.pk, entry.pk]) in body


def test_an_unrevealed_wish_list_marks_nothing(client, nina, ana):
    collection, entry = _collection(nina, is_wish_list=True, view=CARDS)
    GotIt.objects.create(collection=collection, entry=entry, got_by=ana)
    client.force_login(nina)
    body = client.get(reverse("collections:detail", args=[collection.pk])).text
    assert "is-got" not in body


# --- Shared pages ----------------------------------------------------------


def test_visitors_see_the_collections_view(client, nina):
    collection, _ = _collection(
        nina, visibility=Collection.UNLISTED, show_images=True, view=CARDS
    )
    body = client.get(collection.unlisted_url()).text
    assert "view-cards" in _list_classes(body)


def test_visitors_can_switch_for_their_visit(client, nina):
    collection, _ = _collection(
        nina, visibility=Collection.PUBLIC, show_images=True, view=CARDS
    )
    body = client.get(collection.public_url() + "?view=list").text
    assert "view-list" in _list_classes(body)
    assert 'class="view-switch"' in body


def test_without_pictures_a_shared_page_is_a_list_with_no_switch(client, nina):
    collection, _ = _collection(nina, visibility=Collection.UNLISTED)
    # Set behind the form's back, as an old row or the admin could.
    Collection.objects.filter(pk=collection.pk).update(view=CARDS)
    body = client.get(collection.unlisted_url() + "?view=cards").text
    assert "view-list" in _list_classes(body)
    assert 'class="view-switch"' not in body
    assert "placeholder" not in body


@pytest.mark.parametrize("view", [LIST, CARDS])
def test_a_visitor_can_get_an_item_in_both_views(client, nina, ana, view):
    collection, entry = _collection(
        nina,
        is_wish_list=True,
        visibility=Collection.UNLISTED,
        show_images=True,
        view=view,
    )
    client.force_login(ana)
    body = client.get(collection.unlisted_url()).text
    assert reverse("shared:unlisted_got_it", args=[collection.secret, entry.pk]) in body


@pytest.mark.parametrize("view", [LIST, CARDS])
def test_the_giver_sees_their_own_mark_in_both_views(client, nina, ana, view):
    collection, entry = _collection(
        nina,
        is_wish_list=True,
        visibility=Collection.UNLISTED,
        show_images=True,
        view=view,
    )
    GotIt.objects.create(collection=collection, entry=entry, got_by=ana)
    client.force_login(ana)
    body = client.get(collection.unlisted_url()).text
    assert 'class="is-got"' in body
    assert reverse("shared:unlisted_undo", args=[collection.secret, entry.pk]) in body


def test_a_shared_page_without_pictures_never_names_one(client, nina):
    collection, entry = _collection(nina, visibility=Collection.UNLISTED)
    EntryImage.attach(entry, _png())
    body = client.get(collection.unlisted_url()).text
    assert reverse("entries:image", args=[entry.pk]) not in body


def test_a_form_sent_without_a_view_keeps_the_one_it_had(client, nina):
    collection, _ = _collection(nina, view=CARDS)
    client.force_login(nina)
    client.post(
        reverse("collections:edit", args=[collection.pk]),
        {"name": "Watches", "description": ""},
    )
    collection.refresh_from_db()
    assert collection.view == CARDS
