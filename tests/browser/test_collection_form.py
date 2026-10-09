"""The make/edit collection form: the kind/label toggle and the Show group."""

import pytest
from playwright.sync_api import expect

from hrcek.collections.models import Collection
from hrcek.entries.models import FieldDefinition

pytestmark = pytest.mark.browser


def _create_url(live_server):
    return f"{live_server.url}/collections/new/"


def test_choosing_everything_with_a_label_reveals_the_picker(
    signed_in_page, live_server
):
    page = signed_in_page
    page.goto(_create_url(live_server))

    picker = page.locator("#id_label")
    expect(picker).to_be_hidden()

    page.locator("#id_kind").select_option(label="everything with a label")
    expect(picker).to_be_visible()

    page.locator("#id_kind").select_option(label="chosen by hand")
    expect(picker).to_be_hidden()


def test_without_javascript_the_picker_stays_visible(
    signed_in_page_without_js, live_server
):
    page = signed_in_page_without_js
    page.goto(_create_url(live_server))

    expect(page.locator("#id_label")).to_be_visible()


def test_saving_with_several_show_options_round_trips(
    signed_in_page, live_server, person
):
    FieldDefinition.objects.create(owner=person, name="Condition")
    page = signed_in_page
    page.goto(_create_url(live_server))

    page.get_by_label("Name").fill("Watches")
    page.locator("#id_show_notes").check()
    page.locator("#id_show_images").check()
    page.get_by_label("Condition", exact=True).check()
    page.get_by_role("button", name="Save").click()

    collection = Collection.objects.get(owner=person, name="Watches")
    expect(page).to_have_url(f"{live_server.url}/collections/{collection.pk}/")

    page.goto(f"{live_server.url}/collections/{collection.pk}/edit/")
    expect(page.locator("#id_show_notes")).to_be_checked()
    expect(page.locator("#id_show_images")).to_be_checked()
    expect(page.locator("#id_show_tags")).not_to_be_checked()
    expect(page.get_by_label("Condition", exact=True)).to_be_checked()
