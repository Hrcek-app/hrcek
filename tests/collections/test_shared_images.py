"""Who may fetch an entry's picture once a collection can share it.

This widens an access rule that used to be "the owner, nobody else",
so these tests are the boundary: read them before changing
`entries.views.entry_image`.
"""

import io

import pytest
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.entries.models import Entry, EntryImage, Tag

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
        namespace="nina",
    )


@pytest.fixture
def entry(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    EntryImage.attach(entry, _png())
    return entry


def _collect(nina, entry, **extra):
    collection = Collection.objects.create(owner=nina, name="Watches", **extra)
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return collection


def _url(entry):
    return reverse("entries:image", args=[entry.pk])


def test_a_stranger_cannot_see_a_private_entrys_picture(client, nina, entry):
    _collect(nina, entry)
    assert client.get(_url(entry)).status_code == 302


def test_a_stranger_can_see_a_shown_picture_in_a_public_collection(client, nina, entry):
    _collect(nina, entry, visibility=Collection.PUBLIC, show_images=True)
    assert client.get(_url(entry)).status_code == 200


def test_a_public_collection_that_hides_pictures_keeps_them_private(
    client, nina, entry
):
    _collect(nina, entry, visibility=Collection.PUBLIC, show_images=False)
    assert client.get(_url(entry)).status_code == 302


def test_an_unlisted_collection_shows_pictures_too(client, nina, entry):
    _collect(nina, entry, visibility=Collection.UNLISTED, show_images=True)
    assert client.get(_url(entry)).status_code == 200


def test_turning_it_off_makes_the_picture_private_again(client, nina, entry):
    collection = _collect(nina, entry, visibility=Collection.PUBLIC, show_images=True)
    assert client.get(_url(entry)).status_code == 200

    collection.show_images = False
    collection.save()
    assert client.get(_url(entry)).status_code == 302


def test_making_the_collection_private_makes_the_picture_private(client, nina, entry):
    collection = _collect(nina, entry, visibility=Collection.PUBLIC, show_images=True)
    collection.visibility = Collection.PRIVATE
    collection.save()
    assert client.get(_url(entry)).status_code == 302


def test_a_label_collection_shares_pictures_as_well(client, nina, entry):
    tag = Tag.objects.create(owner=nina, name="watches")
    entry.tags.add(tag)
    Collection.objects.create(
        owner=nina,
        name="Labelled",
        kind=Collection.BY_LABEL,
        label=tag,
        visibility=Collection.PUBLIC,
        show_images=True,
    )
    assert client.get(_url(entry)).status_code == 200


def test_an_entry_in_no_collection_stays_private(client, nina, entry):
    assert client.get(_url(entry)).status_code == 302


def test_another_persons_private_picture_is_a_404_when_signed_in(client, nina, entry):
    marko = User.objects.create_user(
        email="marko@example.com",
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )
    _collect(nina, entry)
    client.force_login(marko)
    assert client.get(_url(entry)).status_code == 404


def test_a_public_picture_is_not_cached_privately(client, nina, entry):
    _collect(nina, entry, visibility=Collection.PUBLIC, show_images=True)
    response = client.get(_url(entry))
    assert "private" not in response.headers["Cache-Control"]


def test_a_private_picture_is_still_cached_privately(client, nina, entry):
    client.force_login(nina)
    response = client.get(_url(entry))
    assert "private" in response.headers["Cache-Control"]


def test_the_owner_still_sees_their_own(client, nina, entry):
    client.force_login(nina)
    assert client.get(_url(entry)).status_code == 200


def test_a_shared_page_shows_pictures_as_thumbnails(client, nina, entry):
    collection = _collect(nina, entry, visibility=Collection.UNLISTED, show_images=True)
    body = client.get(f"/c/{collection.secret}/").text
    assert 'class="thumb"' in body
    assert body.index("<h2>") < body.index('class="thumb"')
