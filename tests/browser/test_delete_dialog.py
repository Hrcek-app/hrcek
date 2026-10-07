"""Deleting an entry from the list: a dialog with JavaScript, a page without."""

import pytest
from playwright.sync_api import expect

from hrcek.entries.models import Entry
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.browser

LIST = "/entries/?tag=books"


@pytest.fixture
def entries(person):
    doomed, _ = save_entry(
        person, url="https://example.com/doomed", title="Doomed", tag_names=["books"]
    )
    kept, _ = save_entry(
        person, url="https://example.com/kept", title="Kept", tag_names=["books"]
    )
    return doomed, kept


def _delete_link(page, title):
    return page.locator("article", has_text=title).get_by_role("link", name="Delete")


def _focused_dialog_id(page):
    return page.evaluate("document.activeElement.closest('dialog')?.id ?? null")


def test_delete_opens_a_dialog_and_moves_focus_into_it(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    doomed, _ = entries
    page.goto(live_server.url + LIST)
    _delete_link(page, "Doomed").click()

    dialog = page.get_by_role("dialog", name="Delete this entry?")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Doomed")
    assert page.url == live_server.url + LIST
    assert _focused_dialog_id(page) == f"delete-{doomed.pk}"
    # The safe choice first: a stray Enter must not delete.
    expect(dialog.get_by_role("button", name="Keep it")).to_be_focused()


def test_enter_straight_after_opening_deletes_nothing(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    link = _delete_link(page, "Doomed")
    link.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("dialog")).to_be_visible()

    page.keyboard.press("Enter")

    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.locator("article", has_text="Doomed")).to_have_count(1)
    assert page.url == live_server.url + LIST
    assert Entry.objects.count() == 2


def test_escape_closes_the_dialog_and_returns_focus_to_the_link(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    link = _delete_link(page, "Doomed")
    link.click()
    expect(page.get_by_role("dialog")).to_be_visible()

    page.keyboard.press("Escape")

    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(link).to_be_focused()
    assert Entry.objects.count() == 2


def test_keep_it_closes_the_dialog_and_deletes_nothing(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    link = _delete_link(page, "Doomed")
    link.click()

    page.get_by_role("button", name="Keep it").click()

    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(link).to_be_focused()
    assert page.url == live_server.url + LIST
    assert Entry.objects.count() == 2


def test_yes_deletes_in_place_without_reloading(signed_in_page, live_server, entries):
    page = signed_in_page
    _, kept = entries
    page.goto(live_server.url + LIST)
    page.evaluate("window.__noReload = true")
    _delete_link(page, "Doomed").click()
    dialog = page.get_by_role("dialog", name="Delete this entry?")
    expect(dialog).to_be_visible()

    dialog.get_by_role("button", name="Yes, delete it").click()

    expect(page.locator("article", has_text="Doomed")).to_have_count(0)
    expect(page.locator("article", has_text="Kept")).to_have_count(1)
    assert page.url == live_server.url + LIST
    # A real navigation would have reset the page, wiping this out.
    assert page.evaluate("window.__noReload") is True
    assert list(Entry.objects.values_list("pk", flat=True)) == [kept.pk]
    expect(page.locator("#status")).to_have_text("Deleted “Doomed”.")


def test_deleting_leaves_the_status_region_the_same_node(
    signed_in_page, live_server, entries
):
    """An in-place delete must announce through the live region that
    was already in the page, not a fresh one swapped in to replace it:
    screen readers often miss an announcement from a freshly inserted
    role="status" element. Mark the node before the delete and check
    the mark is still there after."""
    page = signed_in_page
    page.goto(live_server.url + LIST)
    page.evaluate("document.querySelector('#status').__markedNode = true")

    _delete_link(page, "Doomed").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.locator("article", has_text="Doomed")).to_have_count(0)
    expect(page.locator("#status")).to_have_text("Deleted “Doomed”.")
    assert page.evaluate("document.querySelector('#status').__markedNode") is True


def test_deleting_removes_the_dialog_and_leaves_nothing_inert(
    signed_in_page, live_server, entries
):
    """The open <dialog> goes with its <li>; the rest of the page must
    not stay behind the modal top layer once it is gone."""
    page = signed_in_page
    _, kept = entries
    page.goto(live_server.url + LIST)
    _delete_link(page, "Doomed").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.get_by_role("dialog")).to_have_count(0)
    kept_edit = page.locator("article", has_text="Kept").get_by_role(
        "link", name="Edit"
    )
    expect(kept_edit).to_be_visible()
    kept_edit.click()
    expect(page).to_have_url(f"{live_server.url}/entries/{kept.pk}/edit/")


def test_focus_goes_to_the_next_entry_when_one_follows(
    signed_in_page, live_server, person
):
    page = signed_in_page
    save_entry(person, url="https://example.com/first", title="First")
    save_entry(person, url="https://example.com/middle", title="Middle")
    save_entry(person, url="https://example.com/last", title="Last")
    page.goto(live_server.url + "/entries/")

    _delete_link(page, "Middle").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.locator("article", has_text="Middle")).to_have_count(0)
    expect(page.get_by_role("link", name="First")).to_be_focused()


def test_focus_goes_to_the_previous_entry_when_nothing_follows(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)

    _delete_link(page, "Doomed").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.locator("article", has_text="Doomed")).to_have_count(0)
    expect(page.get_by_role("link", name="Kept")).to_be_focused()


def test_deleting_the_last_entry_shows_nothing_saved_yet_and_focuses_save(
    signed_in_page, live_server, person
):
    page = signed_in_page
    save_entry(person, url="https://example.com/only", title="Only")
    page.goto(live_server.url + "/entries/")

    _delete_link(page, "Only").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.get_by_text("Nothing saved yet.")).to_be_visible()
    expect(page.get_by_role("link", name="Save something")).to_be_focused()


def test_deleting_the_last_tagged_entry_navigates_to_all_entries(
    signed_in_page, live_server, entries
):
    """Pruning the filtered label leaves nothing for a fragment to
    update: a real navigation, same as JavaScript off."""
    page = signed_in_page
    _, kept = entries
    kept.tags.clear()
    page.goto(live_server.url + LIST)

    _delete_link(page, "Doomed").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page).to_have_url(f"{live_server.url}/entries/")
    expect(page.get_by_role("link", name="Kept")).to_be_visible()


def test_without_javascript_the_link_reaches_the_confirmation_page(
    signed_in_page_without_js, live_server, entries
):
    page = signed_in_page_without_js
    doomed, kept = entries
    page.goto(live_server.url + LIST)
    _delete_link(page, "Doomed").click()

    expect(page).to_have_url(
        f"{live_server.url}/entries/{doomed.pk}/delete/?next=/entries/%3Ftag%3Dbooks"
    )
    expect(page.get_by_role("heading", name="Delete this entry?")).to_be_visible()

    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.locator("article", has_text="Doomed")).to_have_count(0)
    assert page.url == live_server.url + LIST
    assert list(Entry.objects.values_list("pk", flat=True)) == [kept.pk]
