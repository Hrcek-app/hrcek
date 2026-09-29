"""Adding a picture to an entry from the web form."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from hrcek.accounts.models import User
from hrcek.entries import fetching
from hrcek.entries.models import Entry, EntryImage
from tests.entries.helpers import _structure

pytestmark = pytest.mark.django_db


def _png(colour=(200, 80, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(name="watch.png", data=None):
    return SimpleUploadedFile(name, data or _png(), content_type="image/png")


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
def entry(nina):
    return Entry.objects.create(owner=nina, url="https://example.com/watch")


def _post(client, url, **extra):
    payload = {
        "url": "https://example.com/watch",
        "title": "A watch",
        "notes": "",
        "tags": "",
    }
    payload.update(extra)
    return client.post(url, payload, follow=True)


def test_an_uploaded_file_becomes_the_entry_image(client, nina):
    client.force_login(nina)
    response = _post(client, reverse("entries:create"), image_file=_upload())
    assert response.status_code == 200

    entry = Entry.objects.get(owner=nina, url="https://example.com/watch")
    image = EntryImage.objects.get(entry=entry)
    assert image.original == _png()
    assert image.source_url == ""


def test_an_address_is_fetched_and_kept(client, nina, monkeypatch):
    monkeypatch.setattr(fetching, "fetch", lambda address: _png())
    client.force_login(nina)
    _post(client, reverse("entries:create"), image_url="https://example.com/a.png")

    entry = Entry.objects.get(owner=nina, url="https://example.com/watch")
    assert EntryImage.objects.get(entry=entry).source_url == "https://example.com/a.png"


def test_giving_both_a_file_and_an_address_is_refused(client, nina):
    client.force_login(nina)
    response = _post(
        client,
        reverse("entries:create"),
        image_file=_upload(),
        image_url="https://example.com/a.png",
    )
    assert response.status_code == 200
    assert not EntryImage.objects.exists()


def test_a_file_that_is_not_an_image_is_refused_on_the_form(client, nina):
    client.force_login(nina)
    response = _post(
        client,
        reverse("entries:create"),
        image_file=SimpleUploadedFile(
            "notes.txt", b"just some text", content_type="image/png"
        ),
    )
    assert response.status_code == 200
    assert not EntryImage.objects.exists()
    assert "HRC-IMAGE-0001" not in response.text, "a code leaked into the page"


def test_a_refused_address_is_reported_on_the_form(client, nina, monkeypatch):
    client.force_login(nina)
    response = _post(
        client, reverse("entries:create"), image_url="http://127.0.0.1/secret.png"
    )
    assert response.status_code == 200
    assert not EntryImage.objects.exists()


def test_the_image_can_be_replaced(client, nina, entry):
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    _post(
        client,
        reverse("entries:edit", args=[entry.pk]),
        image_file=_upload(data=_png(colour=(1, 2, 3))),
    )
    assert EntryImage.objects.get(entry=entry).original == _png(colour=(1, 2, 3))


def test_the_image_can_be_removed(client, nina, entry):
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    _post(client, reverse("entries:edit", args=[entry.pk]), remove_image="on")
    assert not EntryImage.objects.filter(entry=entry).exists()


def test_editing_without_mentioning_the_image_keeps_it(client, nina, entry):
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    _post(client, reverse("entries:edit", args=[entry.pk]), title="Renamed")
    assert EntryImage.objects.filter(entry=entry).exists()


def test_the_form_accepts_files_at_all(client, nina):
    client.force_login(nina)
    page = client.get(reverse("entries:create"))
    assert 'enctype="multipart/form-data"' in page.text


def test_the_list_shows_the_picture(client, nina, entry):
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    page = client.get(reverse("entries:list"))
    assert reverse("entries:image", args=[entry.pk]) in page.text


def _thumbnails(response):
    parsed = _structure(response)
    return [(attrs, stack) for attrs, stack in parsed.images if "article" in stack]


def test_the_list_shows_the_picture_as_a_thumbnail_beside_the_text(client, nina, entry):
    """Small and to the side, so an entry with a picture sits level
    with one without: the titles line up either way."""
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    response = client.get(reverse("entries:list"))
    ((img, stack),) = _thumbnails(response)
    assert img["class"] == "thumb"
    assert (img["width"], img["height"]) == ("96", "96")
    assert "div" not in stack[stack.index("article") :], "thumb inside the text"
    body = response.text
    assert body.index("<h2>") < body.index('class="thumb"'), "thumb precedes title"


def test_the_thumbnail_link_is_not_a_second_tab_stop(client, nina, entry):
    """The title already links to the page; the picture repeats that
    link for the mouse, and is kept out of the keyboard's way."""
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    body = " ".join(client.get(reverse("entries:list")).text.split())
    assert '<a href="https://example.com/watch" tabindex="-1" aria-hidden="true">' in (
        body
    )


def _picture_group(body):
    start = body.index('<fieldset class="picture">')
    return body[start : body.index("</fieldset>", start)]


def test_every_picture_control_sits_with_the_picture(client, nina, entry):
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    body = client.get(reverse("entries:edit", args=[entry.pk])).text
    group = _picture_group(body)
    image = reverse("entries:image", args=[entry.pk])
    for piece in (
        image,
        'name="remove_image"',
        'name="image_file"',
        'name="image_url"',
    ):
        assert piece in group, f"{piece} is outside the picture group"
    assert body.count('name="image_file"') == 1


def test_removing_comes_straight_after_the_picture_it_removes(client, nina, entry):
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    group = _picture_group(client.get(reverse("entries:edit", args=[entry.pk])).text)
    image = group.index(reverse("entries:image", args=[entry.pk]))
    remove = group.index('name="remove_image"')
    assert image < remove < group.index('name="image_file"')


def test_the_remove_checkbox_label_has_no_colon(client, nina, entry):
    """A colon says "the control follows"; the box sits before its
    label, so the colon pointed at nothing."""
    EntryImage.attach(entry, _png())
    client.force_login(nina)
    body = client.get(reverse("entries:edit", args=[entry.pk])).text
    assert '<label for="id_remove_image">Remove the picture</label>' in body


def test_there_is_nothing_to_remove_without_a_picture(client, nina, entry):
    client.force_login(nina)
    for url in (
        reverse("entries:create"),
        reverse("entries:edit", args=[entry.pk]),
    ):
        body = client.get(url).text
        assert 'name="image_file"' in _picture_group(body)
        assert 'name="remove_image"' not in body
