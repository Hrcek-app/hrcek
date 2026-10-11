"""The two views of a list of entries, as a browser lays them out.

The server-side tests check which view a page asks for; these check
that each view's CSS puts things where they belong.
"""

import io

import pytest
from PIL import Image

from hrcek.collections.models import Collection, CollectionEntry
from hrcek.core.listing import CARDS, LIST
from hrcek.entries.models import EntryImage
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.browser


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 80, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def _entries(person):
    with_picture, _ = save_entry(
        person, url="https://example.com/watch", title="A watch", notes="Blue."
    )
    EntryImage.attach(with_picture, _png())
    without, _ = save_entry(person, url="https://example.com/book", title="A book")
    return with_picture, without


def _box(page, title, selector):
    box = page.locator("article", has_text=title).locator(selector).first
    found = box.bounding_box()
    assert found is not None, f"{selector} of {title!r} is not on the page"
    return found


@pytest.mark.parametrize("width", [390, 1280])
def test_a_listed_picture_sits_before_the_title(
    signed_in_page, live_server, person, width
):
    page = signed_in_page
    _entries(person)
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(live_server.url + "/entries/")

    picture = _box(page, "A watch", ".entry-thumb")
    title = _box(page, "A watch", "h2 a")
    assert picture["x"] + picture["width"] <= title["x"], "picture covers the title"
    # Rows with and without a picture start their titles at one edge.
    other = _box(page, "A book", "h2 a")
    assert abs(other["x"] - title["x"]) <= 1


def test_a_listed_picture_stays_in_its_row_on_a_collection(
    signed_in_page, live_server, person
):
    page = signed_in_page
    watch, _book = _entries(person)
    collection = Collection.objects.create(owner=person, name="Things", view=LIST)
    CollectionEntry.objects.create(collection=collection, entry=watch)
    page.goto(live_server.url + f"/collections/{collection.pk}/")

    article = page.locator("article", has_text="A watch").bounding_box()
    picture = _box(page, "A watch", ".entry-thumb")
    title = _box(page, "A watch", "h2 a")
    assert article is not None
    assert article["y"] <= picture["y"] < article["y"] + article["height"]
    assert picture["x"] + picture["width"] <= title["x"]


def test_a_card_leads_with_its_picture_across_its_width(
    signed_in_page, live_server, person
):
    page = signed_in_page
    _entries(person)
    person.entry_view = CARDS
    person.save()
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(live_server.url + "/entries/")

    for title in ("A watch", "A book"):
        article = page.locator("article", has_text=title).bounding_box()
        picture = _box(page, title, ".entry-thumb")
        heading = _box(page, title, "h2 a")
        assert article is not None
        assert abs(picture["width"] - article["width"]) <= 1
        assert picture["y"] + picture["height"] <= heading["y"]


def test_the_switch_changes_the_view_and_keeps_it(signed_in_page, live_server, person):
    page = signed_in_page
    _entries(person)
    page.goto(live_server.url + "/entries/")
    page.get_by_role("button", name="Cards").click()
    page.wait_for_url("**/entries/")
    assert "view-cards" in (page.locator("ul.entries").get_attribute("class") or "")
    page.goto(live_server.url + "/entries/")
    assert "view-cards" in (page.locator("ul.entries").get_attribute("class") or "")
