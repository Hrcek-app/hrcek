"""Card alignment across a mixed-height row of entries.

This is the browser test for ui/entries-list's card revision (a long
title and a short title sharing a grid row): it lives here, not on
that branch, because pytest-playwright is only introduced on this one
(controller ruling R-3).
"""

import io

import pytest
from PIL import Image

from hrcek.entries.models import EntryImage
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.browser

LONG_TITLE = "A very long title that wraps onto several lines in its card " * 2
SHORT_TITLE = "Short"


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 80, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def _make_row(person, *, picture):
    long_entry, _ = save_entry(
        person, url="https://example.com/long", title=LONG_TITLE, notes="Long notes."
    )
    short_entry, _ = save_entry(
        person, url="https://example.com/short", title=SHORT_TITLE, notes="Short notes."
    )
    if picture:
        for entry in (long_entry, short_entry):
            EntryImage.attach(entry, _png())


def _edit_link_y(page, title):
    box = (
        page.locator("article", has_text=title)
        .get_by_role("link", name="Edit")
        .bounding_box()
    )
    assert box is not None
    return box["y"]


def _root_font_size(page):
    return page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).fontSize)"
    )


def _assert_row_lines_up(page):
    long_y = _edit_link_y(page, LONG_TITLE)
    short_y = _edit_link_y(page, SHORT_TITLE)
    assert abs(long_y - short_y) <= 1, (
        f"Edit links are {abs(long_y - short_y)}px apart, not lined up"
    )


def _assert_short_card_body_is_tight(page):
    # "Below its title" means below the head block's own last line (the
    # date added), measured from *that* element's box rather than
    # .entry-head's: subgrid used to stretch .entry-head itself to the
    # row's height, so measuring the div's box passed even on the old
    # layout — it is the gap after the head's actual content that has
    # to be a tight flex row-gap, not a stretch borrowed from the long
    # card's extra height.
    card = page.locator("article", has_text=SHORT_TITLE)
    head_last_box = card.locator(".entry-head > :last-child").bounding_box()
    body_box = card.locator(".entry-body").bounding_box()
    assert head_last_box is not None
    assert body_box is not None
    gap = body_box["y"] - (head_last_box["y"] + head_last_box["height"])
    limit = 1.5 * _root_font_size(page)
    assert 0 <= gap <= limit, f"body starts {gap}px below the title, limit {limit}px"


def test_cards_line_up_without_pictures(signed_in_page, live_server, person):
    page = signed_in_page
    _make_row(person, picture=False)
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(live_server.url + "/entries/")

    _assert_row_lines_up(page)
    _assert_short_card_body_is_tight(page)


def test_cards_line_up_with_pictures(signed_in_page, live_server, person):
    page = signed_in_page
    _make_row(person, picture=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(live_server.url + "/entries/")

    _assert_row_lines_up(page)
    _assert_short_card_body_is_tight(page)
