"""Saving somebody else's collection, in place with htmx."""

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, SavedCollection
from hrcek.collections.services import save_collection
from hrcek.entries.models import Entry

pytestmark = pytest.mark.browser


@pytest.fixture
def owner(transactional_db):
    return User.objects.create_user(
        email="ana@example.com",
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
        namespace="ana",
    )


def _shared(owner, name):
    collection = Collection.objects.create(
        owner=owner, name=name, visibility=Collection.UNLISTED, is_wish_list=True
    )
    entry = Entry.objects.create(
        owner=owner, url=f"https://example.com/{name}", title=f"{name} item"
    )
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return collection


@pytest.fixture
def birthday(owner):
    return _shared(owner, "Birthday")


def _saving(page):
    return page.locator("#saving")


def test_save_and_unfollow_in_place_on_shared_page(
    signed_in_page, live_server, person, birthday
):
    page = signed_in_page
    url = f"{live_server.url}{birthday.unlisted_url()}"
    page.goto(url)
    page.evaluate("window.hrcekMark = 'original'")

    _saving(page).get_by_role("button", name="Save to your collections").click()

    expect(_saving(page)).to_contain_text("Saved to your collections.")
    expect(page.locator("#status")).to_have_text("Saved to your collections.")
    expect(_saving(page).get_by_role("button", name="Unfollow")).to_be_focused()
    assert page.evaluate("window.hrcekMark") == "original"
    assert page.url == url
    assert SavedCollection.objects.filter(user=person, via_secret=True).exists()

    _saving(page).get_by_role("button", name="Unfollow").click()

    expect(
        _saving(page).get_by_role("button", name="Save to your collections")
    ).to_be_focused()
    assert page.evaluate("window.hrcekMark") == "original"
    assert not SavedCollection.objects.exists()


def _saved_row(page, name):
    return page.locator("#saved-list > li", has_text=name)


def test_unfollow_in_place_on_list_focuses_the_next_row(
    signed_in_page, live_server, person, owner, birthday
):
    garden = _shared(owner, "Garden")
    save_collection(birthday, person, via_secret=True)
    save_collection(garden, person, via_secret=True)
    page = signed_in_page
    url = f"{live_server.url}/collections/"
    page.goto(url)

    _saved_row(page, "Garden").get_by_role("button", name="Unfollow").click()

    expect(_saved_row(page, "Garden")).to_have_count(0)
    expect(page.locator("#status")).to_have_text(
        "“Garden” is no longer in your saved collections."
    )
    expect(
        _saved_row(page, "Birthday").get_by_role("link", name="Birthday")
    ).to_be_focused()
    assert page.url == url


def test_unfollow_last_saved_in_place_on_list(
    signed_in_page, live_server, person, birthday
):
    save_collection(birthday, person, via_secret=True)
    page = signed_in_page
    page.goto(f"{live_server.url}/collections/")

    _saved_row(page, "Birthday").get_by_role("button", name="Unfollow").click()

    expect(
        page.get_by_text("You have not saved anyone else's collections yet.")
    ).to_be_visible()
    expect(page.get_by_role("heading", name="Saved collections")).to_be_focused()
    assert not SavedCollection.objects.exists()


def test_without_js_save_still_works(
    signed_in_page_without_js, live_server, person, birthday
):
    page = signed_in_page_without_js
    url = f"{live_server.url}{birthday.unlisted_url()}"
    page.goto(url)

    _saving(page).get_by_role("button", name="Save to your collections").click()

    expect(page).to_have_url(url)
    expect(_saving(page)).to_contain_text("Saved to your collections.")
    assert SavedCollection.objects.filter(user=person).exists()


def test_without_js_unfollow_from_list_still_works(
    signed_in_page_without_js, live_server, person, birthday
):
    save_collection(birthday, person, via_secret=True)
    page = signed_in_page_without_js
    page.goto(f"{live_server.url}/collections/")

    _saved_row(page, "Birthday").get_by_role("button", name="Unfollow").click()

    expect(page).to_have_url(f"{live_server.url}/collections/")
    expect(
        page.get_by_text("“Birthday” is no longer in your saved collections.")
    ).to_be_visible()
    assert not SavedCollection.objects.exists()


def test_saved_names_look_like_your_own(signed_in_page, live_server, person, birthday):
    Collection.objects.create(owner=person, name="Mine")
    save_collection(birthday, person, via_secret=True)
    page = signed_in_page
    page.goto(f"{live_server.url}/collections/")

    style = "e => [getComputedStyle(e).fontWeight, getComputedStyle(e).fontSize]"
    own = page.locator(".collection-item", has_text="Mine").locator("h2")
    saved = _saved_row(page, "Birthday").locator("h3")
    assert saved.evaluate(style) == own.evaluate(style)
