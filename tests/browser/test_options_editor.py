"""A choice field's options: in place with JavaScript, by round trip without."""

import pytest
from playwright.sync_api import expect

from hrcek.entries.models import Entry, FieldDefinition, FieldValue

pytestmark = pytest.mark.browser


@pytest.fixture
def size(person):
    return FieldDefinition.objects.create(
        owner=person, name="Size", kind=FieldDefinition.CHOICE, options=["s", "m", "l"]
    )


def _open(page, live_server, size):
    page.goto(f"{live_server.url}/entries/fields/{size.pk}/edit/")
    return page.locator("[data-options-editor]")


def _rows(editor):
    return editor.locator("li.option-row input[name=option]")


def _texts(editor):
    return [_rows(editor).nth(i).input_value() for i in range(_rows(editor).count())]


def _saved(size):
    size.refresh_from_db()
    return size.options


def _save(editor):
    editor.get_by_role("button", name="Save", exact=True).click()


def _no_navigation(page):
    """Mark the document; a page load would wipe the mark."""
    page.evaluate("window.hrcekMark = 'here'")
    return lambda: page.evaluate("window.hrcekMark") == "here"


def test_moving_a_row_in_place(signed_in_page, live_server, size):
    page = signed_in_page
    editor = _open(page, live_server, size)
    stayed = _no_navigation(page)

    editor.get_by_role("button", name="Move “l” up").click()

    assert _texts(editor) == ["s", "l", "m"]
    expect(page.locator("#status")).to_have_text("“l” moved to position 2 of 3.")
    assert stayed()
    _save(editor)
    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["s", "l", "m"]


def test_moving_keeps_focus_on_the_row(signed_in_page, live_server, size):
    page = signed_in_page
    editor = _open(page, live_server, size)

    editor.get_by_role("button", name="Move “m” up").click()

    # Now first, "up" is disabled; focus goes to the same row's "down".
    expect(editor.get_by_role("button", name="Move “m” up")).to_be_disabled()
    expect(editor.get_by_role("button", name="Move “m” down")).to_be_focused()
    page.keyboard.press("Enter")
    assert _texts(editor) == ["s", "m", "l"]
    expect(editor.get_by_role("button", name="Move “m” down")).to_be_focused()


def test_removing_a_row_in_place(signed_in_page, live_server, size):
    page = signed_in_page
    editor = _open(page, live_server, size)
    stayed = _no_navigation(page)

    editor.get_by_role("button", name="Remove “m”").click()

    assert _texts(editor) == ["s", "l"]
    expect(page.locator("#status")).to_have_text("“m” removed.")
    expect(editor.get_by_role("button", name="Remove “l”")).to_be_focused()
    assert stayed()
    _save(editor)
    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["s", "l"]


def test_adding_a_row_in_place(signed_in_page, live_server, size):
    page = signed_in_page
    editor = _open(page, live_server, size)
    stayed = _no_navigation(page)
    new = editor.get_by_label("New option")

    new.fill("xl")
    new.press("Enter")

    assert _texts(editor) == ["s", "m", "l", "xl"]
    expect(new).to_have_value("")
    expect(new).to_be_focused()
    expect(page.locator("#status")).to_have_text("“xl” added.")
    # The new row's controls are named after it, and "down" moved on.
    expect(editor.get_by_role("button", name="Move “l” down")).to_be_enabled()
    expect(editor.get_by_role("button", name="Move “xl” down")).to_be_disabled()
    assert stayed()
    _save(editor)
    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["s", "m", "l", "xl"]


def test_enter_in_a_row_saves(signed_in_page, live_server, size):
    page = signed_in_page
    editor = _open(page, live_server, size)

    _rows(editor).first.fill("small")
    _rows(editor).first.press("Enter")

    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["small", "m", "l"]


def test_dragging_a_row(signed_in_page, live_server, size):
    page = signed_in_page
    editor = _open(page, live_server, size)
    handle = editor.locator(".option-handle").first
    target = editor.locator("li.option-row").last.bounding_box()

    box = handle.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(target["x"] + 10, target["y"] + target["height"] * 0.9, steps=10)
    page.mouse.up()

    assert _texts(editor) == ["m", "l", "s"]
    expect(page.locator("#status")).to_have_text("“s” moved to position 3 of 3.")
    expect(editor.get_by_role("button", name="Move “s” down")).to_be_disabled()


def test_a_used_option_asks_first_and_going_back_keeps_the_edits(
    signed_in_page, live_server, size, person
):
    entry = Entry.objects.create(owner=person, url="https://example.com/1")
    FieldValue.objects.create(entry=entry, definition=size, value_text="m")
    page = signed_in_page
    editor = _open(page, live_server, size)
    expect(editor.get_by_text("used by 1 entry")).to_be_visible()

    _rows(editor).first.fill("small")
    editor.get_by_role("button", name="Remove “m”").click()
    _save(editor)

    expect(
        page.get_by_role("heading", name="Remove options that are in use?")
    ).to_be_visible()
    expect(page.get_by_text("This will clear the field on 1 entry.")).to_be_visible()
    page.get_by_role("button", name="Go back").click()

    editor = page.locator("[data-options-editor]")
    assert _texts(editor) == ["small", "l"]
    _save(editor)
    page.get_by_role("button", name="Yes, remove them").click()
    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["small", "l"]
    assert not FieldValue.objects.filter(definition=size).exists()


def test_without_javascript_every_button_is_a_round_trip(
    signed_in_page_without_js, live_server, size
):
    page = signed_in_page_without_js
    editor = _open(page, live_server, size)
    expect(editor.locator(".option-handle").first).to_be_hidden()

    _rows(editor).first.fill("small")
    editor.get_by_role("button", name="Move “l” up").click()
    editor = page.locator("[data-options-editor]")
    assert _texts(editor) == ["small", "l", "m"]

    editor.get_by_role("button", name="Remove “m”").click()
    editor = page.locator("[data-options-editor]")
    assert _texts(editor) == ["small", "l"]

    editor.get_by_label("New option").fill("xl")
    editor.get_by_role("button", name="Add", exact=True).click()
    editor = page.locator("[data-options-editor]")
    assert _texts(editor) == ["small", "l", "xl"]
    assert _saved(size) == ["s", "m", "l"]

    _save(editor)
    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["small", "l", "xl"]


def test_without_javascript_enter_in_the_new_option_keeps_it(
    signed_in_page_without_js, live_server, size
):
    page = signed_in_page_without_js
    editor = _open(page, live_server, size)

    editor.get_by_label("New option").fill("xl")
    editor.get_by_label("New option").press("Enter")

    expect(page.get_by_text("Field saved.")).to_be_visible()
    assert _saved(size) == ["s", "m", "l", "xl"]
