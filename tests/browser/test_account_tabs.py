"""The account page's three sections, as tabs: see docs/dev/javascript.md."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser

ACCOUNT = "/accounts/me/"
PASSWORD = "a-long-enough-passphrase"


def test_arrow_keys_and_home_end_move_and_select(signed_in_page, live_server):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT)

    profile = page.get_by_role("tab", name="Profile")
    sign_in = page.get_by_role("tab", name="Sign-in")
    fields = page.get_by_role("tab", name="Fields and clients")

    profile.focus()
    page.keyboard.press("ArrowRight")
    expect(sign_in).to_be_focused()
    expect(sign_in).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("tabpanel", name="Sign-in")).to_be_visible()

    page.keyboard.press("ArrowRight")
    expect(fields).to_be_focused()
    expect(fields).to_have_attribute("aria-selected", "true")

    # Wraps from the last tab back to the first.
    page.keyboard.press("ArrowRight")
    expect(profile).to_be_focused()

    # And from the first back to the last.
    page.keyboard.press("ArrowLeft")
    expect(fields).to_be_focused()

    page.keyboard.press("Home")
    expect(profile).to_be_focused()
    expect(profile).to_have_attribute("aria-selected", "true")

    page.keyboard.press("End")
    expect(fields).to_be_focused()
    expect(fields).to_have_attribute("aria-selected", "true")


def test_only_the_active_tab_is_in_the_tab_order(signed_in_page, live_server):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT)

    expect(page.get_by_role("tab", name="Profile")).to_have_attribute("tabindex", "0")
    expect(page.get_by_role("tab", name="Sign-in")).to_have_attribute("tabindex", "-1")
    expect(page.get_by_role("tab", name="Fields and clients")).to_have_attribute(
        "tabindex", "-1"
    )


def test_a_hashless_load_does_not_scroll(signed_in_page, live_server):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT)

    assert page.evaluate("window.scrollY") == 0
    expect(
        page.get_by_role("heading", name="Your account", level=1)
    ).to_be_in_viewport()


def test_loading_with_a_hash_opens_that_tab(signed_in_page, live_server):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT + "#sign-in")

    expect(page.get_by_role("tab", name="Sign-in")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_role("tabpanel", name="Sign-in")).to_be_visible()
    expect(page.get_by_role("tabpanel", name="Profile")).to_be_hidden()


def test_a_failed_email_change_opens_sign_in(signed_in_page, live_server, person):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT + "#sign-in")

    # Same address as already in use: the form fails validation, and
    # the hub must come back open on Sign-in rather than on Profile.
    page.get_by_label("New email address").fill(person.email)
    page.get_by_label("Current password").fill(PASSWORD)
    page.get_by_role("button", name="Change my email address").click()

    expect(page.get_by_role("tab", name="Sign-in")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_role("tabpanel", name="Sign-in")).to_be_visible()


def test_without_javascript_all_three_sections_are_shown(
    signed_in_page_without_js, live_server
):
    page = signed_in_page_without_js
    page.goto(live_server.url + ACCOUNT)

    expect(page.get_by_role("heading", name="Profile")).to_be_visible()
    expect(page.get_by_role("heading", name="Sign-in")).to_be_visible()
    expect(page.get_by_role("heading", name="Fields and clients")).to_be_visible()
    expect(page.get_by_role("tablist")).to_have_count(0)


def test_the_success_message_is_visible_after_an_email_change(
    signed_in_page, live_server, person
):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT)
    page.get_by_role("tab", name="Sign-in").click()
    page.get_by_label("New email address").fill("nina2@example.com")
    page.get_by_label("Current password").fill(PASSWORD)
    page.get_by_role("button", name="Change my email address").click()

    expect(page.locator("ul.messages")).to_be_in_viewport()


def test_the_success_message_is_visible_after_an_email_change_without_js(
    signed_in_page_without_js, live_server, person
):
    page = signed_in_page_without_js
    page.goto(live_server.url + ACCOUNT)
    page.get_by_label("New email address").fill("nina2@example.com")
    page.get_by_label("Current password").fill(PASSWORD)
    page.get_by_role("button", name="Change my email address").click()

    expect(page.locator("ul.messages")).to_be_in_viewport()


# The borders a person sees between the tab row and the first thing in
# the open panel: the tablist's own bottom edge, then the top edge of
# every element from the panel down to the first form control's parent
# (the control's own box is not a line between the two).
BORDERS_UNDER_THE_TABS = """
() => {
  const list = document.querySelector("[role=tablist]");
  const control = document.querySelector("[role=tabpanel]:not([hidden]) input");
  const widths = [parseFloat(getComputedStyle(list).borderBottomWidth)];
  const root = list.parentElement;
  for (let el = control.parentElement; el && el !== root; el = el.parentElement) {
    widths.push(parseFloat(getComputedStyle(el).borderTopWidth));
  }
  return widths.filter((width) => width > 0).length;
}
"""


def test_one_line_between_the_tabs_and_the_first_form(signed_in_page, live_server):
    page = signed_in_page
    page.goto(live_server.url + ACCOUNT)
    expect(page.get_by_role("tablist")).to_be_visible()

    assert page.evaluate(BORDERS_UNDER_THE_TABS) == 1

    # Every tab, not only the first: none of them brings a second line.
    for name in ("Sign-in", "Fields and clients"):
        page.get_by_role("tab", name=name).click()
        assert (
            page.evaluate(
                """() => getComputedStyle(
                 document.querySelector("[role=tabpanel]:not([hidden])")
               ).borderTopWidth"""
            )
            == "0px"
        )


def test_without_javascript_the_sections_are_still_set_apart(
    signed_in_page_without_js, live_server
):
    page = signed_in_page_without_js
    page.goto(live_server.url + ACCOUNT)

    widths = page.locator("[data-tabs] > section").evaluate_all(
        "(sections) => sections.map((s) => getComputedStyle(s).borderTopWidth)"
    )
    assert widths == ["0px", "1px", "1px"]


def _mark_the_page(page):
    # Gone if the page is navigated, kept through an in-place swap.
    page.evaluate("window.hrcekMark = 'same page'")


def _still_the_same_page(page, url):
    assert page.evaluate("window.hrcekMark") == "same page"
    assert page.url == url


def _expect_tab_still_open(page, name):
    expect(page.get_by_role("tab", name=name)).to_have_attribute(
        "aria-selected", "true"
    )
    panel = page.get_by_role("tabpanel", name=name)
    expect(panel).to_be_visible()
    expect(panel).to_have_attribute("role", "tabpanel")


def test_saving_the_display_name_in_place(signed_in_page, live_server, person):
    page = signed_in_page
    url = live_server.url + ACCOUNT
    page.goto(url)
    _mark_the_page(page)

    page.get_by_label("Display name").fill("Nina S")
    page.get_by_role("button", name="Save display name").click()

    expect(page.locator("#status")).to_have_text("Your display name is now “Nina S”.")
    expect(page.locator("#messages")).to_have_text("Your display name is now “Nina S”.")
    expect(page.get_by_label("Display name")).to_have_value("Nina S")
    expect(page.get_by_role("button", name="Save display name")).to_be_focused()
    _expect_tab_still_open(page, "Profile")
    _still_the_same_page(page, url)
    person.refresh_from_db()
    assert person.display_name == "Nina S"


def test_a_display_name_error_in_place(signed_in_page, live_server, person):
    page = signed_in_page
    url = live_server.url + ACCOUNT
    page.goto(url)
    _mark_the_page(page)

    # Twice in a row: focus has to land on the field both times, not
    # only the first.
    for value in ("nina@example.com", "nina@example.org"):
        page.get_by_label("Display name").fill(value)
        page.get_by_role("button", name="Save display name").click()
        field = page.get_by_label("Display name")
        expect(field).to_have_attribute("aria-invalid", "true")
        expect(field).to_have_value(value)
        expect(field).to_be_focused()

    expect(page.locator("#profile-content .errorlist")).to_be_visible()
    _expect_tab_still_open(page, "Profile")
    _still_the_same_page(page, url)
    person.refresh_from_db()
    assert person.display_name is None


def test_changing_the_email_address_in_place(signed_in_page, live_server, person):
    page = signed_in_page
    url = live_server.url + ACCOUNT + "#sign-in"
    page.goto(url)
    _mark_the_page(page)

    page.get_by_label("New email address").fill("nina2@example.com")
    page.get_by_label("Current password").fill(PASSWORD)
    page.get_by_role("button", name="Change my email address").click()

    expect(page.locator("#status")).to_contain_text(
        "Check nina2@example.com for a confirmation link."
    )
    panel = page.get_by_role("tabpanel", name="Sign-in")
    expect(panel).to_contain_text("Waiting for confirmation at nina2@example.com")
    expect(page.get_by_role("button", name="Change my email address")).to_be_focused()
    _expect_tab_still_open(page, "Sign-in")
    _still_the_same_page(page, url)
    person.refresh_from_db()
    assert person.pending_email == "nina2@example.com"

    # And cancelling it, in place as well.
    page.get_by_role("button", name="Cancel the change").click()
    expect(page.locator("#status")).to_have_text(
        "The change to nina2@example.com has been cancelled."
    )
    expect(panel).not_to_contain_text("Waiting for confirmation")
    expect(page.get_by_role("button", name="Change my email address")).to_be_focused()
    _expect_tab_still_open(page, "Sign-in")
    _still_the_same_page(page, url)
    person.refresh_from_db()
    assert person.pending_email is None


def test_an_email_change_error_in_place(signed_in_page, live_server, person):
    page = signed_in_page
    url = live_server.url + ACCOUNT + "#sign-in"
    page.goto(url)
    _mark_the_page(page)

    page.get_by_label("New email address").fill("nina2@example.com")
    page.get_by_label("Current password").fill("not the password")
    page.get_by_role("button", name="Change my email address").click()

    password = page.get_by_label("Current password")
    expect(password).to_have_attribute("aria-invalid", "true")
    expect(password).to_be_focused()
    expect(page.get_by_label("New email address")).to_have_value("nina2@example.com")
    _expect_tab_still_open(page, "Sign-in")
    _still_the_same_page(page, url)
    person.refresh_from_db()
    assert person.pending_email is None


FAILING_FORMS = {
    "profile": {
        "anchor": "",
        "tab": "Profile",
        "path": "display-name",
        "fill": "Display name",
        "button": "Save display name",
    },
    "sign-in": {
        "anchor": "#sign-in",
        "tab": "Sign-in",
        "path": "email",
        "fill": "New email address",
        "button": "Change my email address",
    },
}


@pytest.mark.parametrize("form", FAILING_FORMS.values(), ids=FAILING_FORMS.keys())
def test_a_failed_save_swaps_nothing_into_the_tab_and_says_so_visibly(
    signed_in_page, live_server, form
):
    """The server's error page must never land inside a section."""
    page = signed_in_page
    url = live_server.url + ACCOUNT + form["anchor"]
    page.goto(url)
    _mark_the_page(page)
    page.route(
        f"**/accounts/me/{form['path']}/",
        lambda route: route.fulfill(
            status=500, body="<h1>Server error page</h1>", content_type="text/html"
        ),
    )

    page.get_by_label(form["fill"]).fill("nina2@example.com")
    if form["tab"] == "Sign-in":
        page.get_by_label("Current password").fill(PASSWORD)
    page.get_by_role("button", name=form["button"]).click()

    error = page.locator("#messages > li.error")
    expect(error).to_have_text("Something went wrong. Please check and try again.")
    expect(error).to_be_visible()
    expect(page.locator("#status")).to_have_text(
        "Something went wrong. Please check and try again."
    )
    expect(page.get_by_text("Server error page")).to_have_count(0)
    expect(page.get_by_role("button", name=form["button"])).to_be_visible()
    _expect_tab_still_open(page, form["tab"])
    _still_the_same_page(page, url)
