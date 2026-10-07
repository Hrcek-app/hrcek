"""Choosing an entry's collections from the entry's own edit form."""

import pytest
from playwright.sync_api import expect

from hrcek.collections.models import Collection
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.browser


@pytest.fixture
def entry(person):
    entry, _ = save_entry(person, url="https://example.com/first", title="First")
    return entry


@pytest.fixture
def collection(person):
    return Collection.objects.create(
        owner=person, name="Watches", kind=Collection.MANUAL
    )


def _edit_url(live_server, entry):
    return f"{live_server.url}/entries/{entry.pk}/edit/"


def test_ticking_a_collection_shows_up_on_the_list_and_the_collection(
    signed_in_page, live_server, entry, collection
):
    page = signed_in_page
    page.goto(_edit_url(live_server, entry))

    page.get_by_label("Watches").check()
    page.get_by_role("button", name="Save").click()

    expect(page).to_have_url(f"{live_server.url}/entries/")
    row = page.locator("article", has_text="First")
    link = row.get_by_role("link", name="Watches")
    expect(link).to_be_visible()
    expect(link).to_have_attribute("href", f"/collections/{collection.pk}/")

    page.goto(f"{live_server.url}/collections/{collection.pk}/")
    expect(page.locator("article", has_text="First")).to_be_visible()


def test_without_javascript_ticking_a_collection_still_works(
    signed_in_page_without_js, live_server, entry, collection
):
    page = signed_in_page_without_js
    page.goto(_edit_url(live_server, entry))

    page.get_by_label("Watches").check()
    page.get_by_role("button", name="Save").click()

    expect(page).to_have_url(f"{live_server.url}/entries/")
    row = page.locator("article", has_text="First")
    expect(row.get_by_role("link", name="Watches")).to_be_visible()

    page.goto(f"{live_server.url}/collections/{collection.pk}/")
    expect(page.locator("article", has_text="First")).to_be_visible()
