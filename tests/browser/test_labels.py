"""Labels on the list: in place with JavaScript, by round trip without."""

import pytest
from playwright.sync_api import expect

from hrcek.collections.models import Collection
from hrcek.entries.models import Entry, Tag
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.browser

LIST = "/entries/?tag=books"


@pytest.fixture
def entries(person):
    first, _ = save_entry(
        person, url="https://example.com/first", title="First", tag_names=["books"]
    )
    second, _ = save_entry(
        person, url="https://example.com/second", title="Second", tag_names=["books"]
    )
    return first, second


def _labels(page, title):
    return page.locator("article", has_text=title).locator(".entry-labels")


def _chips(page, title):
    return _labels(page, title).locator("a.tag")


def _names(entry):
    return list(Entry.objects.get(pk=entry.pk).tags.values_list("name", flat=True))


def _add(page, title, name):
    labels = _labels(page, title)
    labels.get_by_text("+ Label").click()
    field = labels.get_by_label("New label")
    field.fill(name)
    field.press("Enter")
    return field


def test_adding_a_label_in_place(signed_in_page, live_server, entries):
    page = signed_in_page
    first, _ = entries
    page.goto(live_server.url + LIST)
    # Mark the page's live region, to tell whether it survives the swap.
    page.evaluate("document.getElementById('status').hrcekMark = 'original'")

    field = _add(page, "First", "watch")

    expect(_chips(page, "First")).to_have_text(["books", "watch"])
    expect(page.locator("#status")).to_have_text("Label “watch” added.")
    # The same element, with new text: a live region that is replaced
    # rather than updated is often not read out at all.
    assert page.evaluate("document.getElementById('status').hrcekMark") == "original"
    assert page.locator("[role=status]#status").count() == 1
    # Ready for the next one: still open, empty, and focused.
    expect(field).to_be_focused()
    expect(field).to_have_value("")
    expect(_labels(page, "First").locator("details")).to_have_attribute("open", "")
    assert page.url == live_server.url + LIST
    # Saved, not only drawn: a request refused for want of a CSRF token
    # would leave the database alone.
    assert _names(first) == ["books", "watch"]


def _summary(page, title):
    return _labels(page, title).locator("summary")


def test_opening_the_form_shows_cancel(signed_in_page, live_server, entries):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    summary = _summary(page, "First")

    summary.click()

    expect(_labels(page, "First").locator("details")).to_have_attribute("open", "")
    expect(summary.locator(".add-pill-cancel-text")).to_be_visible()
    expect(summary.locator(".add-pill-text")).to_be_hidden()
    expect(summary).to_have_accessible_name("Cancel")


def test_clicking_cancel_closes_the_form(signed_in_page, live_server, entries):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    summary = _summary(page, "First")
    summary.click()
    expect(_labels(page, "First").locator("details")).to_have_attribute("open", "")

    summary.click()

    expect(_labels(page, "First").locator("details")).not_to_have_attribute("open", "")
    expect(summary.locator(".add-pill-text")).to_be_visible()
    expect(summary).to_have_accessible_name("+ Label")


def test_escape_closes_the_form_and_focuses_the_summary(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    summary = _summary(page, "First")
    summary.click()
    _labels(page, "First").get_by_label("New label").fill("watch")

    page.keyboard.press("Escape")

    expect(_labels(page, "First").locator("details")).not_to_have_attribute("open", "")
    expect(summary).to_be_focused()
    expect(summary).to_have_accessible_name("+ Label")


def test_adding_a_label_keeps_the_summary_saying_cancel(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)

    _add(page, "First", "watch")

    expect(_labels(page, "First").locator("details")).to_have_attribute("open", "")
    expect(_summary(page, "First")).to_have_accessible_name("Cancel")


def test_the_next_label_can_be_typed_straight_away(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    first, _ = entries
    page.goto(live_server.url + LIST)
    field = _add(page, "First", "watch")
    expect(_chips(page, "First")).to_have_text(["books", "watch"])

    page.keyboard.type("diving")
    page.keyboard.press("Enter")

    expect(_chips(page, "First")).to_have_text(["books", "diving", "watch"])
    expect(page.locator("#status")).to_have_text("Label “diving” added.")
    expect(field).to_be_focused()
    assert _names(first) == ["books", "diving", "watch"]


def test_the_csrf_header_alone_is_enough(signed_in_page, live_server, entries):
    # The forms carry a token too; take it out, so only the header that
    # base.html gives every htmx request can get the post through.
    page = signed_in_page
    first, _ = entries
    page.goto(live_server.url + LIST)
    page.evaluate(
        "document.querySelectorAll('input[name=csrfmiddlewaretoken]')"
        ".forEach(input => input.remove())"
    )

    _add(page, "First", "watch")

    expect(_chips(page, "First")).to_have_text(["books", "watch"])
    assert _names(first) == ["books", "watch"]


def test_removing_a_label_in_place(signed_in_page, live_server, person, entries):
    page = signed_in_page
    first, _ = entries
    save_entry(person, url=first.url, tag_names=["books", "watch"])
    page.goto(live_server.url + LIST)

    page.evaluate("document.getElementById('status').hrcekMark = 'original'")
    _labels(page, "First").get_by_role("button", name="Remove label watch").click()

    expect(_chips(page, "First")).to_have_text(["books"])
    expect(page.locator("#status")).to_have_text("Label “watch” removed.")
    assert page.evaluate("document.getElementById('status').hrcekMark") == "original"
    # The removed chip's button is gone; focus goes to the entry's own
    # "+ Label", not back to the top of the page.
    expect(_labels(page, "First").locator("summary")).to_be_focused()
    assert page.url == live_server.url + LIST
    assert _names(first) == ["books"]


def test_a_refused_label_says_why_beside_the_input(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    first, _ = entries
    page.goto(live_server.url + LIST)

    field = _add(page, "First", "x" * 51)

    labels = _labels(page, "First")
    expect(labels.locator(".errorlist")).to_contain_text("at most 50 characters")
    expect(field).to_have_attribute("aria-invalid", "true")
    expect(field).to_be_focused()
    expect(page.locator("#status")).to_contain_text("at most 50 characters")
    assert _names(first) == ["books"]


def test_adding_a_label_changes_only_that_entry(signed_in_page, live_server, entries):
    page = signed_in_page
    _, second = entries
    page.goto(live_server.url + LIST)
    _labels(page, "Second").get_by_text("+ Label").click()

    _add(page, "First", "watch")

    expect(_chips(page, "First")).to_have_text(["books", "watch"])
    expect(_chips(page, "Second")).to_have_text(["books"])
    # The other entry's open form was left as it was.
    expect(_labels(page, "Second").locator("details")).to_have_attribute("open", "")
    assert _names(second) == ["books"]

    _labels(page, "First").get_by_role("button", name="Remove label books").click()

    expect(_chips(page, "First")).to_have_text(["watch"])
    expect(_chips(page, "Second")).to_have_text(["books"])
    assert _names(second) == ["books"]


def test_without_javascript_adding_returns_to_the_same_page(
    signed_in_page_without_js, live_server, entries
):
    page = signed_in_page_without_js
    first, _ = entries
    page.goto(live_server.url + LIST)

    _add(page, "First", "watch")

    expect(page.locator(".messages")).to_have_text("Label “watch” added.")
    expect(_chips(page, "First")).to_have_text(["books", "watch"])
    assert page.url == live_server.url + LIST
    assert _names(first) == ["books", "watch"]


def test_without_javascript_removing_returns_to_the_same_page(
    signed_in_page_without_js, live_server, person, entries
):
    page = signed_in_page_without_js
    first, _ = entries
    save_entry(person, url=first.url, tag_names=["books", "watch"])
    page.goto(live_server.url + LIST)

    _labels(page, "First").get_by_role("button", name="Remove label watch").click()

    expect(page.locator(".messages")).to_have_text("Label “watch” removed.")
    expect(_chips(page, "First")).to_have_text(["books"])
    assert page.url == live_server.url + LIST
    assert _names(first) == ["books"]


def test_removing_the_only_entry_with_the_filtered_label_navigates_away(
    signed_in_page, live_server, person
):
    """Pruning the label the page is filtered by must leave no stale
    page behind: the URL still said ?tag=watch, the entry was still
    listed, and reloading would 404 once the label was really gone."""
    save_entry(
        person, url="https://example.com/only", title="Only", tag_names=["watch"]
    )
    page = signed_in_page
    page.goto(live_server.url + "/entries/?tag=watch")

    _labels(page, "Only").get_by_role("button", name="Remove label watch").click()

    page.wait_for_url(live_server.url + "/entries/")
    expect(page.get_by_role("heading", name="Your entries")).to_be_visible()
    assert "tag=watch" not in page.url
    # The old filtered address really is gone, not merely unvisited.
    assert page.request.get(live_server.url + "/entries/?tag=watch").status == 404


def test_removing_a_surviving_filter_label_stays_on_the_filtered_list(
    signed_in_page, live_server, person, entries
):
    page = signed_in_page
    first, second = entries
    save_entry(person, url=first.url, tag_names=["books", "watch"])
    page.goto(live_server.url + LIST)

    _labels(page, "First").get_by_role("button", name="Remove label watch").click()

    expect(_chips(page, "First")).to_have_text(["books"])
    assert page.url == live_server.url + LIST
    assert _names(second) == ["books"]


def test_removing_a_label_drains_the_emptied_collection_notice_in_place(
    signed_in_page, live_server, person, entries
):
    page = signed_in_page
    first, _ = entries
    save_entry(person, url=first.url, tag_names=["books", "watch"])
    watch = Tag.objects.get(owner=person, name="watch")
    Collection.objects.create(
        owner=person, name="Watches", kind=Collection.BY_LABEL, label=watch
    )
    page.goto(live_server.url + LIST)

    _labels(page, "First").get_by_role("button", name="Remove label watch").click()

    expect(page.locator(".messages")).to_contain_text("“Watches” has nothing in it now")
    # Drained, not only shown: reloading does not see it again.
    page.reload()
    expect(page.locator(".messages")).not_to_contain_text("has nothing in it now")


def test_adding_a_label_updates_the_sidebar_without_reload(
    signed_in_page, live_server, entries
):
    page = signed_in_page
    page.goto(live_server.url + LIST)
    sidebar = page.locator("#tags-sidebar")
    expect(sidebar.get_by_role("link", name="watch")).to_have_count(0)

    _add(page, "First", "watch")

    expect(sidebar.get_by_role("link", name="watch")).to_be_visible()
    # Still on the "books" filter, and the sidebar still says so.
    expect(sidebar.get_by_role("link", name="books")).to_have_attribute(
        "aria-current", "true"
    )
    assert page.url == live_server.url + LIST


def test_removing_the_last_use_of_a_label_updates_the_sidebar_without_reload(
    signed_in_page, live_server, person, entries
):
    page = signed_in_page
    first, _ = entries
    save_entry(person, url=first.url, tag_names=["books", "watch"])
    page.goto(live_server.url + LIST)
    sidebar = page.locator("#tags-sidebar")
    expect(sidebar.get_by_role("link", name="watch")).to_be_visible()

    _labels(page, "First").get_by_role("button", name="Remove label watch").click()

    expect(sidebar.get_by_role("link", name="watch")).to_have_count(0)
    expect(sidebar.get_by_role("link", name="books")).to_have_attribute(
        "aria-current", "true"
    )
    assert page.url == live_server.url + LIST


def test_a_failed_add_swaps_nothing_in_and_says_so_visibly(
    signed_in_page, live_server, entries
):
    """The server's error page must never land inside the card."""
    page = signed_in_page
    first, _ = entries
    page.goto(live_server.url + LIST)
    page.route(
        f"**/entries/{first.pk}/labels/add/",
        lambda route: route.fulfill(
            status=500, body="<h1>Server error page</h1>", content_type="text/html"
        ),
    )

    _add(page, "First", "watch")

    error = page.locator("#messages > li.error")
    expect(error).to_have_text("Something went wrong. Please check and try again.")
    expect(error).to_be_visible()
    expect(page.locator("#status")).to_have_text(
        "Something went wrong. Please check and try again."
    )
    expect(page.get_by_text("Server error page")).to_have_count(0)
    expect(_chips(page, "First")).to_have_text(["books"])
    assert _names(first) == ["books"]
