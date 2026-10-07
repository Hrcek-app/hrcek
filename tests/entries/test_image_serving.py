"""Serving an entry's picture.

Images go through Django rather than off a web server's disk, so that
one person's pictures are never readable by another account or by
anyone who guesses a URL.
"""

import io

import pytest
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from hrcek.accounts.models import User
from hrcek.entries.models import Entry, EntryImage

pytestmark = pytest.mark.django_db

AVIF = "image/avif,image/webp,*/*"
NO_AVIF = "image/webp,image/png,*/*"


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 80, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def _person(email):
    return User.objects.create_user(
        email=email,
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def nina():
    return _person("nina@example.com")


@pytest.fixture
def entry(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    EntryImage.attach(entry, _png())
    return entry


def _url(entry):
    return reverse("entries:image", args=[entry.pk])


def test_the_owner_gets_the_image(client, nina, entry):
    client.force_login(nina)
    response = client.get(_url(entry), headers={"accept": AVIF})
    assert response.status_code == 200
    assert response["content-type"] == "image/avif"
    assert response.content == bytes(EntryImage.objects.get(entry=entry).display)


def test_somebody_else_gets_a_404_not_a_403(client, entry):
    # A 403 would confirm the entry exists and who it belongs to.
    client.force_login(_person("marko@example.com"))
    assert client.get(_url(entry)).status_code == 404


def test_a_stranger_is_sent_to_sign_in(client, entry):
    assert client.get(_url(entry)).status_code == 302


def test_an_entry_without_an_image_is_a_404(client, nina):
    bare = Entry.objects.create(owner=nina, url="https://example.com/nothing")
    client.force_login(nina)
    assert client.get(_url(bare)).status_code == 404


def test_an_older_browser_gets_webp(client, nina, entry):
    client.force_login(nina)
    response = client.get(_url(entry), headers={"accept": NO_AVIF})
    assert response["content-type"] == "image/webp"
    assert "accept" in response["vary"].lower()


def test_the_response_is_private_and_revalidatable(client, nina, entry):
    client.force_login(nina)
    response = client.get(_url(entry), headers={"accept": AVIF})
    assert "private" in response["cache-control"]
    assert response["etag"]


def test_an_unchanged_image_is_not_sent_twice(client, nina, entry):
    client.force_login(nina)
    first = client.get(_url(entry), headers={"accept": AVIF})
    again = client.get(
        _url(entry), headers={"accept": AVIF, "if-none-match": first["etag"]}
    )
    assert again.status_code == 304


def test_the_original_is_never_served(client, nina, entry):
    client.force_login(nina)
    body = client.get(_url(entry), headers={"accept": AVIF}).content
    assert body != bytes(EntryImage.objects.get(entry=entry).original)


def test_the_list_does_not_query_per_entry_or_load_blobs(
    client, nina, django_assert_num_queries
):
    for n in range(5):
        entry = Entry.objects.create(owner=nina, url=f"https://example.com/{n}")
        EntryImage.attach(entry, _png())
    client.force_login(nina)

    # One query for the page of entries (image joined in), plus the
    # prefetches and session/user lookups, plus one for the owner's
    # collections (for the "In:" line) — empty here, so the second
    # query _attach_in_collections could run, for the page's manual
    # memberships, is skipped rather than issued with an empty id
    # list. Not one more per entry either way.
    with django_assert_num_queries(8):
        page = client.get(reverse("entries:list"))
    assert page.status_code == 200


def test_the_list_query_leaves_the_blobs_in_the_table(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/one")
    EntryImage.attach(entry, _png())

    fetched = (
        Entry.objects.filter(owner=nina)
        .select_related("image")
        .defer("image__original", "image__display")
        .first()
    )
    image = fetched.image  # ty: ignore[unresolved-attribute]
    assert {"original", "display"} <= image.get_deferred_fields()
    assert image.width == 40, "dimensions still come along"
