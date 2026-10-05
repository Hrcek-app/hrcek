"""A feed is exactly as visible as the page it belongs to."""

import pytest
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, GotIt
from hrcek.entries.models import Entry, FieldDefinition, FieldValue, Tag

pytestmark = pytest.mark.django_db


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


def test_a_public_feed_is_atom_and_open(client, collection):
    _publish(collection)
    response = client.get("/u/nina/watches/feed/")
    assert response.status_code == 200
    assert "application/atom+xml" in response["content-type"]
    assert b"A watch" in response.content
    assert b"https://example.com/watch" in response.content
    assert b"Things I like." in response.content


def test_an_unlisted_feed_lives_under_the_secret(client, collection):
    collection.visibility = Collection.UNLISTED
    collection.save()
    assert client.get(f"/c/{collection.secret}/feed/").status_code == 200
    assert client.get("/c/definitely-not-the-secret/feed/").status_code == 404


def test_a_private_feed_needs_its_owner(client, nina, collection):
    url = f"/collections/{collection.pk}/feed/"
    assert client.get(url).status_code in (302, 404)

    client.force_login(nina)
    assert client.get(url).status_code == 200


def test_somebody_elses_private_feed_is_a_404(client, collection):
    client.force_login(_person("marko@example.com"))
    assert client.get(f"/collections/{collection.pk}/feed/").status_code == 404


def test_a_private_collection_has_no_shared_feed(client, collection):
    assert client.get("/u/nina/watches/feed/").status_code == 404
    assert client.get(f"/c/{collection.secret}/feed/").status_code == 404


def test_an_unlisted_collection_has_no_public_feed(client, collection):
    collection.visibility = Collection.UNLISTED
    collection.save()
    assert client.get("/u/nina/watches/feed/").status_code == 404


def test_a_feed_hides_what_its_page_hides(client, collection):
    _publish(collection)
    assert b"Secret thoughts." not in client.get("/u/nina/watches/feed/").content

    collection.show_notes = True
    collection.save()
    assert b"Secret thoughts." in client.get("/u/nina/watches/feed/").content


def test_a_feed_hides_fields_its_page_hides(client, nina, collection):
    price = FieldDefinition.objects.create(
        owner=nina, name="Cost", kind=FieldDefinition.NUMBER
    )
    FieldValue.objects.create(
        entry=collection.entries().first(), definition=price, value_number=1450
    )
    _publish(collection, show_notes=True)
    assert b"1450" not in client.get("/u/nina/watches/feed/").content


def test_the_feed_orders_like_the_page(client, nina, collection):
    later = Entry.objects.create(
        owner=nina, url="https://example.com/later", title="Added later"
    )
    CollectionEntry.objects.create(collection=collection, entry=later)
    _publish(collection)

    body = client.get("/u/nina/watches/feed/").content
    assert body.index(b"Added later") < body.index(b"A watch")


def test_the_page_points_at_its_feed(client, collection):
    _publish(collection)
    page = client.get("/u/nina/watches/").text
    assert 'type="application/atom+xml"' in page
    assert "/u/nina/watches/feed/" in page


def test_a_shared_feed_leaves_out_what_has_been_got(client, collection):
    _publish(collection, is_wish_list=True)
    GotIt.objects.create(
        collection=collection,
        entry=collection.entries().get(),
        got_by=_person("ana@example.com"),
    )
    feed = client.get(f"/u/nina/{collection.slug}/feed/").content.decode()
    assert "A watch" not in feed


def test_the_private_feed_still_has_everything(client, nina, collection):
    _publish(collection, is_wish_list=True)
    GotIt.objects.create(
        collection=collection,
        entry=collection.entries().get(),
        got_by=_person("ana@example.com"),
    )
    client.force_login(nina)
    feed = client.get(f"/collections/{collection.pk}/feed/").content.decode()
    assert "A watch" in feed
