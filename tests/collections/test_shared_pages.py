"""Who may read a collection, and what they see when they do.

These tests are the boundary for everything a collection page shows to
somebody who is not its owner.
"""

import pytest
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.entries.models import Entry, FieldDefinition, FieldValue, Tag

pytestmark = pytest.mark.django_db


@pytest.fixture
def nina():
    return User.objects.create_user(
        email="nina@example.com",
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
        namespace="nina",
    )


@pytest.fixture
def collection(nina):
    collection = Collection.objects.create(
        owner=nina, name="Watches", description="Things I like."
    )
    entry = Entry.objects.create(
        owner=nina,
        url="https://example.com/watch",
        title="A watch",
        notes="Secret thoughts.",
    )
    entry.tags.add(Tag.objects.create(owner=nina, name="expensive"))
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return collection


def _publish(collection, **extra):
    collection.visibility = Collection.PUBLIC
    for key, value in extra.items():
        setattr(collection, key, value)
    collection.save()
    return collection


def _unlist(collection, **extra):
    collection.visibility = Collection.UNLISTED
    for key, value in extra.items():
        setattr(collection, key, value)
    collection.save()
    return collection


def test_a_private_collection_has_no_shared_page(client, collection):
    assert client.get(f"/c/{collection.secret}/").status_code == 404
    assert client.get("/u/nina/watches/").status_code == 404


def test_an_unlisted_collection_answers_on_its_secret(client, collection):
    _unlist(collection)
    response = client.get(f"/c/{collection.secret}/")
    assert response.status_code == 200
    assert "A watch" in response.text
    assert "Watches" in response.text
    assert "Things I like." in response.text, "the description is always shown"


def test_an_unlisted_collection_is_not_at_a_public_address(client, collection):
    _unlist(collection)
    assert client.get("/u/nina/watches/").status_code == 404


def test_a_wrong_secret_is_a_404_not_a_403(client, collection):
    _unlist(collection)
    assert client.get("/c/definitely-not-the-secret/").status_code == 404


def test_an_unknown_public_name_is_a_404(client, collection):
    _publish(collection)
    assert client.get("/u/nobody/watches/").status_code == 404


def test_a_public_collection_is_open_to_strangers(client, collection):
    _publish(collection)
    response = client.get("/u/nina/watches/")
    assert response.status_code == 200
    assert "A watch" in response.text
    assert "Things I like." in response.text


def test_making_it_private_again_closes_both_doors(client, collection):
    _publish(collection)
    collection.visibility = Collection.PRIVATE
    collection.save()
    assert client.get("/u/nina/watches/").status_code == 404
    assert client.get(f"/c/{collection.secret}/").status_code == 404


def test_hidden_things_are_absent_from_the_source(client, collection):
    _publish(collection)
    body = client.get("/u/nina/watches/").text
    assert "Secret thoughts." not in body
    assert "expensive" not in body


def test_shown_things_appear(client, collection):
    _publish(collection, show_notes=True, show_tags=True)
    body = client.get("/u/nina/watches/").text
    assert "Secret thoughts." in body
    assert "expensive" in body


def test_a_shared_pages_tags_are_not_links(client, collection):
    """A visitor has no entry list to filter; a link to one would
    only lead to a sign-in page."""
    _publish(collection, show_tags=True)
    body = client.get("/u/nina/watches/").text
    assert "expensive" in body
    assert "?tag=" not in body


def test_only_chosen_custom_fields_appear(client, nina, collection):
    price = FieldDefinition.objects.create(
        owner=nina, name="Cost", kind=FieldDefinition.NUMBER
    )
    entry = collection.entries().first()
    FieldValue.objects.create(entry=entry, definition=price, value_number=1450)
    _publish(collection)
    assert "1450" not in client.get("/u/nina/watches/").text

    collection.visible_fields.add(price)
    assert "1450" in client.get("/u/nina/watches/").text


def test_an_unlisted_page_asks_not_to_be_indexed(client, collection):
    _unlist(collection)
    response = client.get(f"/c/{collection.secret}/")
    assert "noindex" in response.headers.get("X-Robots-Tag", "")


def test_a_public_page_is_indexable(client, collection):
    _publish(collection)
    response = client.get("/u/nina/watches/")
    assert "noindex" not in response.headers.get("X-Robots-Tag", "")


def test_a_label_collection_can_be_shared_too(client, nina):
    tag = Tag.objects.create(owner=nina, name="watches")
    collection = Collection.objects.create(
        owner=nina,
        name="Labelled",
        kind=Collection.BY_LABEL,
        label=tag,
        visibility=Collection.PUBLIC,
    )
    entry = Entry.objects.create(
        owner=nina, url="https://example.com/x", title="Tagged thing"
    )
    entry.tags.add(tag)
    assert "Tagged thing" in client.get(collection.public_url()).text
