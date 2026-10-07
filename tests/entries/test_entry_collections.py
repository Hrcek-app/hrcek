"""Choosing an entry's collections from the entry's own form."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


@pytest.fixture
def entry(nina):
    return Entry.objects.create(owner=nina, url="https://example.com/watch")


def _post(client, entry, **extra):
    data = {"url": entry.url, "title": "", "notes": "", "tags": "", **extra}
    return client.post(reverse("entries:edit", args=[entry.pk]), data)


def test_the_form_lists_only_my_hand_picked_collections(client, nina, entry):
    mine = Collection.objects.create(owner=nina, name="Mine", kind=Collection.MANUAL)
    tag = Tag.objects.create(owner=nina, name="watches")
    Collection.objects.create(
        owner=nina, name="Watches", kind=Collection.BY_LABEL, label=tag
    )
    marko = _person("marko@example.com")
    Collection.objects.create(owner=marko, name="Theirs", kind=Collection.MANUAL)

    client.force_login(nina)
    form = client.get(reverse("entries:edit", args=[entry.pk])).context["form"]

    assert list(form.fields["collections"].queryset) == [mine]


def test_ticking_a_collection_adds_the_entry(client, nina, entry):
    collection = Collection.objects.create(
        owner=nina, name="Mine", kind=Collection.MANUAL
    )
    client.force_login(nina)

    response = _post(client, entry, collections=[collection.pk])

    assert response.status_code == 302
    assert CollectionEntry.objects.filter(collection=collection, entry=entry).exists()


def test_unticking_takes_it_out(client, nina, entry):
    collection = Collection.objects.create(
        owner=nina, name="Mine", kind=Collection.MANUAL
    )
    CollectionEntry.objects.create(collection=collection, entry=entry)
    client.force_login(nina)

    response = _post(client, entry)  # collections omitted: nothing ticked

    assert response.status_code == 302
    assert not CollectionEntry.objects.filter(
        collection=collection, entry=entry
    ).exists()


def test_another_owners_collection_cannot_be_ticked(client, nina, entry):
    stranger = _person("marko@example.com")
    theirs = Collection.objects.create(
        owner=stranger, name="Theirs", kind=Collection.MANUAL
    )
    client.force_login(nina)

    response = _post(client, entry, collections=[theirs.pk])

    assert response.status_code == 200  # form error, not saved
    assert not theirs.memberships.exists()  # ty: ignore[unresolved-attribute]
    # Visible, not swallowed: nina has no manual collections of her
    # own, so the fieldset would otherwise have nothing else to show
    # and could be left out entirely, hiding the error with it.
    assert "is not one of the available choices" in response.text


def test_a_by_label_collection_cannot_be_ticked(client, nina, entry):
    tag = Tag.objects.create(owner=nina, name="watches")
    by_label = Collection.objects.create(
        owner=nina, name="Watches", kind=Collection.BY_LABEL, label=tag
    )
    client.force_login(nina)

    response = _post(client, entry, collections=[by_label.pk])

    assert response.status_code == 200
    assert not CollectionEntry.objects.filter(collection=by_label).exists()


def test_label_collections_are_shown_but_not_offered(client, nina, entry):
    Tag.set_for(entry, ["watches"])
    tag = Tag.objects.get(owner=nina, name="watches")
    by_label = Collection.objects.create(
        owner=nina, name="Watches", kind=Collection.BY_LABEL, label=tag
    )
    client.force_login(nina)

    body = client.get(reverse("entries:edit", args=[entry.pk])).text

    assert "Also in" in body
    detail_url = reverse("collections:detail", args=[by_label.pk])
    assert f'href="{detail_url}" target="_blank" rel="noopener">Watches</a>' in body
    # Not offered as a tickable choice.
    assert f'value="{by_label.pk}"' not in body


def test_the_list_says_which_collections_hold_each_entry(client, nina, entry):
    manual = Collection.objects.create(owner=nina, name="Mine", kind=Collection.MANUAL)
    CollectionEntry.objects.create(collection=manual, entry=entry)
    Tag.set_for(entry, ["watches"])
    tag = Tag.objects.get(owner=nina, name="watches")
    by_label = Collection.objects.create(
        owner=nina, name="Watches", kind=Collection.BY_LABEL, label=tag
    )

    client.force_login(nina)
    body = client.get(reverse("entries:list")).text

    assert "In:" in body
    manual_url = reverse("collections:detail", args=[manual.pk])
    label_url = reverse("collections:detail", args=[by_label.pk])
    assert f'<a href="{manual_url}">Mine</a>' in body
    assert f'<a href="{label_url}">Watches</a>' in body


def test_an_entry_in_no_collection_shows_no_in_line(client, nina, entry):
    client.force_login(nina)
    body = client.get(reverse("entries:list")).text
    assert "in-collections" not in body


def test_create_with_an_already_held_url_adds_the_ticked_collection(
    client, nina, entry
):
    """Saving the create form under an address you already hold updates
    that entry instead of making a second one (see entries.services);
    ticking a collection there must add it, the same as editing would."""
    kept = Collection.objects.create(owner=nina, name="Kept", kind=Collection.MANUAL)
    CollectionEntry.objects.create(collection=kept, entry=entry)
    ticked = Collection.objects.create(
        owner=nina, name="Ticked", kind=Collection.MANUAL
    )
    client.force_login(nina)

    response = client.post(
        reverse("entries:create"),
        {
            "url": entry.url,
            "title": "",
            "notes": "",
            "tags": "",
            "collections": [ticked.pk],
        },
    )

    assert response.status_code == 302
    # The holder's other membership survives...
    assert CollectionEntry.objects.filter(collection=kept, entry=entry).exists()
    # ...and the newly ticked one is added.
    assert CollectionEntry.objects.filter(collection=ticked, entry=entry).exists()


def test_create_with_an_already_held_url_and_nothing_ticked_changes_nothing(
    client, nina, entry
):
    """The create form never shows what the holder already belongs to
    (there is no instance to pre-tick from), so nothing ticked must
    never be read as "take it out of everything"."""
    kept = Collection.objects.create(owner=nina, name="Kept", kind=Collection.MANUAL)
    CollectionEntry.objects.create(collection=kept, entry=entry)
    client.force_login(nina)

    response = client.post(
        reverse("entries:create"),
        {"url": entry.url, "title": "", "notes": "", "tags": ""},
    )

    assert response.status_code == 302
    assert CollectionEntry.objects.filter(collection=kept, entry=entry).exists()


def test_editing_onto_a_held_address_never_takes_the_holder_out_of_any_collection(
    client, nina, entry
):
    """Editing entry A to an address entry B already holds saves onto B
    (see entries.services). A's form was ticked with A's memberships,
    not B's, so what A's form left unticked says nothing about B."""
    other = Entry.objects.create(owner=nina, url="https://example.com/other")
    kept = Collection.objects.create(owner=nina, name="Kept", kind=Collection.MANUAL)
    CollectionEntry.objects.create(collection=kept, entry=entry)
    ticked = Collection.objects.create(
        owner=nina, name="Ticked", kind=Collection.MANUAL
    )
    client.force_login(nina)

    response = _post(client, other, url=entry.url, collections=[ticked.pk])

    assert response.status_code == 302
    assert CollectionEntry.objects.filter(collection=kept, entry=entry).exists()
    assert CollectionEntry.objects.filter(collection=ticked, entry=entry).exists()


def test_with_no_manual_collections_and_no_label_collections_nothing_is_shown(
    client, nina, entry
):
    client.force_login(nina)
    body = client.get(reverse("entries:edit", args=[entry.pk])).text
    assert "<legend>Collections</legend>" not in body


def test_with_only_label_collections_only_the_read_only_sentence_is_shown(
    client, nina, entry
):
    Tag.set_for(entry, ["watches"])
    tag = Tag.objects.get(owner=nina, name="watches")
    Collection.objects.create(
        owner=nina, name="Watches", kind=Collection.BY_LABEL, label=tag
    )
    client.force_login(nina)

    body = client.get(reverse("entries:edit", args=[entry.pk])).text

    assert "<legend>Collections</legend>" in body
    assert "Also in" in body
    # No checkbox group offered: nothing to tick.
    assert 'name="collections"' not in body
    assert "Collections that follow a label decide for themselves." not in body


def test_the_list_needs_no_query_per_entry(client, nina):
    collection = Collection.objects.create(
        owner=nina, name="Mine", kind=Collection.MANUAL
    )
    # Not joined by any entry, so every entry's "+ Collection" offers it:
    # the choices are built in memory, not asked for per entry.
    other = Collection.objects.create(owner=nina, name="Other", kind=Collection.MANUAL)

    def _set_up(count):
        Entry.objects.filter(owner=nina).delete()
        for n in range(count):
            e = Entry.objects.create(owner=nina, url=f"https://example.com/{n}")
            CollectionEntry.objects.create(collection=collection, entry=e)

    client.force_login(nina)

    _set_up(1)
    with CaptureQueriesContext(connection) as small:
        client.get(reverse("entries:list"))

    _set_up(6)
    with CaptureQueriesContext(connection) as big:
        body = client.get(reverse("entries:list")).text

    assert len(small.captured_queries) == len(big.captured_queries)
    assert body.count(f'name="collection" value="{other.pk}"') == 6
