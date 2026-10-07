"""Collections in place: from the entries list, and on a collection's page."""

import pytest
from playwright.sync_api import expect

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, GotIt
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.browser


@pytest.fixture
def first(person):
    entry, _ = save_entry(person, url="https://example.com/first", title="First")
    return entry


@pytest.fixture
def watches(person):
    return Collection.objects.create(
        owner=person, name="Watches", kind=Collection.MANUAL
    )


@pytest.fixture
def gifts(person):
    return Collection.objects.create(owner=person, name="Gifts", kind=Collection.MANUAL)


def _held(entry, collection):
    return CollectionEntry.objects.filter(collection=collection, entry=entry).exists()


def _line(page, title):
    return page.locator("article", has_text=title).locator(".entry-collections")


def _pill(page, title):
    return _line(page, title).locator("details.collection-add")


def _summary(page, title):
    return _pill(page, title).locator("summary")


def _mark_status(page):
    page.evaluate("document.getElementById('status').hrcekMark = 'original'")


def _status_kept(page):
    return page.evaluate("document.getElementById('status').hrcekMark") == "original"


# On the entries list.


def test_adding_to_a_collection_in_place(
    signed_in_page, live_server, first, watches, gifts
):
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")
    _mark_status(page)

    _summary(page, "First").click()
    _pill(page, "First").get_by_role("button", name="Add to “Watches”").click()

    expect(_line(page, "First").get_by_role("link", name="Watches")).to_be_visible()
    expect(page.locator("#status")).to_have_text("Added to “Watches”.")
    assert _status_kept(page)
    # Gifts is still there to add, so focus waits on the pill, closed.
    expect(_summary(page, "First")).to_be_focused()
    expect(_pill(page, "First")).not_to_have_attribute("open", "")
    expect(
        _pill(page, "First").get_by_role("button", name="Add to “Watches”")
    ).to_have_count(0)
    assert page.url == f"{live_server.url}/entries/"
    assert _held(first, watches)


def test_adding_the_last_one_moves_focus_to_its_way_out(
    signed_in_page, live_server, first, watches
):
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")

    _summary(page, "First").click()
    _pill(page, "First").get_by_role("button", name="Add to “Watches”").click()

    remove = _line(page, "First").get_by_role(
        "button", name="Take “First” out of “Watches”"
    )
    expect(remove).to_be_focused()
    expect(_pill(page, "First")).to_have_count(0)
    assert _held(first, watches)


def test_taking_out_with_the_cross_in_place(
    signed_in_page, live_server, first, watches
):
    CollectionEntry.objects.create(collection=watches, entry=first)
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")
    _mark_status(page)

    _line(page, "First").get_by_role(
        "button", name="Take “First” out of “Watches”"
    ).click()

    expect(_line(page, "First").get_by_role("link", name="Watches")).to_have_count(0)
    expect(page.locator("#status")).to_have_text("Taken out of “Watches”.")
    assert _status_kept(page)
    # The cross is gone; focus goes to the pill that can put it back.
    expect(_summary(page, "First")).to_be_focused()
    assert page.url == f"{live_server.url}/entries/"
    assert not _held(first, watches)


def test_a_label_collection_has_no_cross(signed_in_page, live_server, person):
    entry, _ = save_entry(
        person, url="https://example.com/first", title="First", tag_names=["watch"]
    )
    tag = entry.tags.get()
    Collection.objects.create(
        owner=person, name="Watching", kind=Collection.BY_LABEL, label=tag
    )
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")

    expect(_line(page, "First").get_by_role("link", name="Watching")).to_be_visible()
    expect(_line(page, "First").get_by_role("button")).to_have_count(0)


def test_opening_the_pill_shows_cancel(signed_in_page, live_server, first, watches):
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")
    summary = _summary(page, "First")
    expect(summary).to_have_accessible_name("+ Collection")

    summary.click()

    expect(_pill(page, "First")).to_have_attribute("open", "")
    expect(summary).to_have_accessible_name("Cancel")

    summary.click()

    expect(_pill(page, "First")).not_to_have_attribute("open", "")
    expect(summary).to_have_accessible_name("+ Collection")


def test_escape_closes_the_pill_and_focuses_its_summary(
    signed_in_page, live_server, first, watches
):
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")
    _summary(page, "First").click()
    _pill(page, "First").get_by_role("button", name="Add to “Watches”").focus()

    page.keyboard.press("Escape")

    expect(_pill(page, "First")).not_to_have_attribute("open", "")
    expect(_summary(page, "First")).to_be_focused()


def test_adding_back_onto_a_wish_list_says_it_was_already_got(
    signed_in_page, live_server, first
):
    wishes = Collection.objects.create(
        owner=first.owner, name="Wants", kind=Collection.MANUAL, is_wish_list=True
    )
    ana = User.objects.create_user(email="ana@example.com", password="x" * 20)
    CollectionEntry.objects.create(collection=wishes, entry=first)
    GotIt.objects.create(collection=wishes, entry=first, got_by=ana)
    CollectionEntry.objects.filter(collection=wishes, entry=first).delete()
    page = signed_in_page
    page.goto(f"{live_server.url}/entries/")

    _summary(page, "First").click()
    _pill(page, "First").get_by_role("button", name="Add to “Wants”").click()

    expect(page.locator("#status")).to_have_text("Added to “Wants”.")
    expect(page.locator("#messages")).to_contain_text(
        "Somebody has already got this for “Wants”."
    )
    assert page.url == f"{live_server.url}/entries/"
    assert _held(first, wishes)


def test_without_javascript_there_is_no_pill(
    signed_in_page_without_js, live_server, first, watches
):
    page = signed_in_page_without_js
    page.goto(f"{live_server.url}/entries/")

    expect(_pill(page, "First")).to_be_hidden()
    expect(page.get_by_text("+ Collection")).to_be_hidden()


def test_without_javascript_the_cross_still_takes_it_out(
    signed_in_page_without_js, live_server, first, watches
):
    CollectionEntry.objects.create(collection=watches, entry=first)
    page = signed_in_page_without_js
    page.goto(f"{live_server.url}/entries/")

    _line(page, "First").get_by_role(
        "button", name="Take “First” out of “Watches”"
    ).click()

    expect(page).to_have_url(f"{live_server.url}/entries/")
    expect(page.locator(".messages")).to_have_text("Taken out of “Watches”.")
    expect(_line(page, "First").get_by_role("link", name="Watches")).to_have_count(0)
    assert not _held(first, watches)


# On a collection's own page.


@pytest.fixture
def three(person, watches):
    """Three entries on Watches; the page lists the newest first."""
    entries = []
    for title in ("Third", "Second", "First"):
        entry, _ = save_entry(
            person, url=f"https://example.com/{title.lower()}", title=title
        )
        CollectionEntry.objects.create(collection=watches, entry=entry)
        entries.append(entry)
    return entries


def _row(page, title):
    return page.locator("ul.entries > li", has_text=title)


def _take_out(page, title):
    _row(page, title).get_by_role("button", name="Take it out").click()


def test_taking_it_out_on_the_collection_page_in_place(
    signed_in_page, live_server, watches, three
):
    page = signed_in_page
    url = f"{live_server.url}/collections/{watches.pk}/"
    page.goto(url)
    expect(page.locator("ul.entries > li h2")).to_have_text(
        ["First", "Second", "Third"]
    )
    _mark_status(page)

    _take_out(page, "Second")

    expect(_row(page, "Second")).to_have_count(0)
    expect(page.locator("#status")).to_have_text("“Second” taken out of “Watches”.")
    assert _status_kept(page)
    # The next row along takes focus.
    expect(_row(page, "Third").get_by_role("link", name="Third")).to_be_focused()
    assert page.url == url
    assert [e.title for e in watches.entries()] == ["First", "Third"]


def test_taking_out_the_last_row_focuses_the_one_before(
    signed_in_page, live_server, watches, three
):
    page = signed_in_page
    page.goto(f"{live_server.url}/collections/{watches.pk}/")

    _take_out(page, "Third")

    expect(_row(page, "Third")).to_have_count(0)
    expect(_row(page, "Second").get_by_role("link", name="Second")).to_be_focused()


def test_taking_out_the_only_entry_says_the_collection_is_empty(
    signed_in_page, live_server, watches, first
):
    CollectionEntry.objects.create(collection=watches, entry=first)
    page = signed_in_page
    url = f"{live_server.url}/collections/{watches.pk}/"
    page.goto(url)

    _take_out(page, "First")

    expect(page.locator("ul.entries")).to_have_count(0)
    expect(page.get_by_text("Nothing in this collection yet.")).to_be_visible()
    expect(page.get_by_role("heading", name="In this collection")).to_be_focused()
    expect(page.locator("#status")).to_have_text("“First” taken out of “Watches”.")
    assert page.url == url
    assert not watches.entries().exists()


def test_without_javascript_taking_it_out_still_works(
    signed_in_page_without_js, live_server, watches, first
):
    CollectionEntry.objects.create(collection=watches, entry=first)
    page = signed_in_page_without_js
    url = f"{live_server.url}/collections/{watches.pk}/"
    page.goto(url)

    _take_out(page, "First")

    expect(page).to_have_url(url)
    expect(page.get_by_text("Nothing in this collection yet.")).to_be_visible()
    assert not watches.entries().exists()


def test_without_javascript_an_entry_in_nothing_has_no_blank_row(
    signed_in_page_without_js, live_server, first, watches
):
    page = signed_in_page_without_js
    page.goto(f"{live_server.url}/entries/")

    article = page.locator("article", has_text="First")
    head = article.locator(".entry-head").bounding_box()
    labels = article.locator(".entry-labels").bounding_box()
    gap = float(article.evaluate("a => getComputedStyle(a).rowGap").removesuffix("px"))
    assert head and labels
    # One gap between head and labels: the body, holding only a pill
    # that cannot work here, takes no row of its own.
    assert labels["y"] - (head["y"] + head["height"]) == pytest.approx(gap, abs=1)


def test_the_pill_is_there_before_htmx_arrives(
    signed_in_page, live_server, first, watches
):
    """The page is marked as having JavaScript before first paint, not
    once the deferred scripts (htmx first) have loaded, so the pill
    never pops in and pushes the card taller."""
    page = signed_in_page
    held = []

    def hold(route):
        held.append(route)

    page.route("**/js/vendor/htmx-*.js", hold)

    page.goto(f"{live_server.url}/entries/", wait_until="commit")
    # Measure the styled card: the stylesheet can still be arriving.
    page.wait_for_function(
        "[...document.querySelectorAll('link[rel=stylesheet]')].every(l => l.sheet)"
    )
    article = page.locator("article", has_text="First")
    expect(article).to_be_visible()
    assert page.evaluate("document.documentElement.classList.contains('js')")
    expect(_pill(page, "First")).to_be_visible()
    assert page.evaluate("typeof window.htmx") == "undefined"
    before = article.bounding_box()

    assert held, "the htmx request was never made"
    for route in held:
        route.continue_()
    page.wait_for_function("typeof window.htmx !== 'undefined'")
    page.wait_for_load_state("load")

    assert article.bounding_box() == before
