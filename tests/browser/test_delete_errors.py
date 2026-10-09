"""What happens when deleting in place goes wrong: a failed request, or
a session that is no longer there to answer it."""

import pytest
from playwright.sync_api import expect

from hrcek.entries.models import Entry
from hrcek.entries.services import save_entry
from tests.browser.conftest import PASSWORD

pytestmark = pytest.mark.browser

ERROR_TEXT = "Something went wrong. Please check and try again."


@pytest.fixture
def doomed(person):
    entry, _ = save_entry(person, url="https://example.com/doomed", title="Doomed")
    return entry


def _delete_link(page, title):
    return page.locator("article", has_text=title).get_by_role("link", name="Delete")


@pytest.mark.parametrize("status", [500, 404])
def test_a_failed_delete_leaves_the_card_and_says_so_visibly(
    signed_in_page, live_server, doomed, status
):
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    page.route(
        f"**/entries/{doomed.pk}/delete/",
        lambda route: route.fulfill(
            status=status, body="<p>An error page</p>", content_type="text/html"
        ),
    )

    _delete_link(page, "Doomed").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.locator("article", has_text="Doomed")).to_have_count(1)
    expect(page.locator("#status")).to_have_text(ERROR_TEXT)
    error = page.locator("#messages > li.error")
    expect(error).to_have_text(ERROR_TEXT)
    expect(error).to_be_visible()
    expect(page.get_by_text("An error page")).to_have_count(0)
    assert Entry.objects.filter(pk=doomed.pk).exists()


def test_a_second_failure_replaces_the_first_error(signed_in_page, live_server, doomed):
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    page.route(
        f"**/entries/{doomed.pk}/delete/",
        lambda route: route.fulfill(status=500, body="boom", content_type="text/plain"),
    )

    for _ in range(2):
        _delete_link(page, "Doomed").click()
        page.get_by_role("button", name="Yes, delete it").click()
        expect(page.get_by_role("dialog")).to_have_count(0)

    expect(page.locator("#messages > li")).to_have_count(1)
    expect(page.locator("#messages > li.error")).to_have_text(ERROR_TEXT)


def test_a_failed_delete_closes_the_dialog_so_the_message_is_heard(
    signed_in_page, live_server, doomed
):
    """#status is inert behind an open modal dialog; closing it is what
    makes the announcement above reachable at all."""
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    page.route(
        f"**/entries/{doomed.pk}/delete/",
        lambda route: route.fulfill(status=500, body="boom", content_type="text/plain"),
    )

    _delete_link(page, "Doomed").click()
    page.get_by_role("button", name="Yes, delete it").click()

    expect(page.get_by_role("dialog")).to_have_count(0)


def test_the_dialog_closes_before_the_status_text_is_set(
    signed_in_page, live_server, doomed
):
    """#status is inert while a modal dialog is open, so the write has
    to happen after the dialog is gone, not before.

    A MutationObserver cannot tell these two apart: its callback only
    ever runs as a microtask once the whole synchronous handler has
    finished, by which point the dialog is closed either way,
    regardless of which statement ran first inside it. Intercepting
    the two calls themselves — dialog.close() and the #status
    textContent setter — and recording the order they actually fire in
    is what distinguishes the fix from the bug it replaced."""
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    page.route(
        f"**/entries/{doomed.pk}/delete/",
        lambda route: route.fulfill(status=500, body="boom", content_type="text/plain"),
    )
    _delete_link(page, "Doomed").click()
    page.evaluate(
        """() => {
            window.__order = [];
            const status = document.getElementById("status");
            const dialog = document.querySelector("dialog[open]");
            const originalClose = dialog.close.bind(dialog);
            dialog.close = (...args) => {
                window.__order.push("dialog-closed");
                return originalClose(...args);
            };
            const descriptor = Object.getOwnPropertyDescriptor(
                Node.prototype, "textContent"
            );
            Object.defineProperty(status, "textContent", {
                configurable: true,
                get() {
                    return descriptor.get.call(this);
                },
                set(value) {
                    if (value) window.__order.push(`status-text-set:${value}`);
                    return descriptor.set.call(this, value);
                },
            });
        }"""
    )

    page.get_by_role("button", name="Yes, delete it").click()
    expect(page.locator("#status")).to_have_text(ERROR_TEXT)

    order = page.evaluate("window.__order")
    assert "dialog-closed" in order, order
    final_text = f"status-text-set:{ERROR_TEXT}"
    assert final_text in order, order
    assert order.index("dialog-closed") < order.index(final_text), order


def test_double_clicking_yes_sends_only_one_request(
    signed_in_page, live_server, doomed
):
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    requests = []
    page.on(
        "request",
        lambda request: (
            requests.append(request)
            if request.method == "POST" and "/delete/" in request.url
            else None
        ),
    )
    # Hold the response open long enough for a second click to land
    # while the button should be disabled.
    page.route(
        f"**/entries/{doomed.pk}/delete/",
        lambda route: (
            page.wait_for_timeout(300),
            route.continue_(),
        )[-1],
    )

    _delete_link(page, "Doomed").click()
    yes = page.get_by_role("button", name="Yes, delete it")
    yes.click()
    expect(yes).to_be_disabled()
    yes.click(force=True)

    expect(page.locator("article", has_text="Doomed")).to_have_count(0)
    assert len(requests) == 1


def test_an_expired_session_ends_on_the_sign_in_page(
    signed_in_page, live_server, doomed
):
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    _delete_link(page, "Doomed").click()
    page.context.clear_cookies()

    page.get_by_role("button", name="Yes, delete it").click()

    expect(page).to_have_url(f"{live_server.url}/?next=/entries/")
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
    assert Entry.objects.filter(pk=doomed.pk).exists()


def test_signing_in_again_returns_to_the_list_not_the_delete_url(
    signed_in_page, live_server, doomed, person
):
    """The delete URL only takes a POST; landing there after signing in
    would be a blank 405."""
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    _delete_link(page, "Doomed").click()
    page.context.clear_cookies()
    page.get_by_role("button", name="Yes, delete it").click()
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()

    page.locator('input[name="username"]').fill(person.email)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()

    expect(page).to_have_url(f"{live_server.url}/entries/")
    expect(page.locator("article", has_text="Doomed")).to_have_count(1)


def test_a_swapped_4xx_does_not_trigger_the_generic_announcer(
    signed_in_page, live_server, doomed
):
    """A 4xx a control swaps into itself is its own feedback — the
    announcer must not overwrite it, or close a dialog that has
    nothing to do with it. There is no such control on this branch
    yet (the entries list's only in-place control, delete, declares
    hx-status:4xx="swap:none"), so this probes the announcer's rule in
    isolation with a synthetic one, the same way a future control that
    swaps a 422 (adding a label, say) would be expected to behave."""
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    page.evaluate(
        """() => {
            const probe = document.createElement("div");
            probe.innerHTML =
                '<form id="probe-form" hx-post="/probe/422/" ' +
                'hx-target="#probe-target" hx-swap="innerHTML">' +
                '<button type="submit">Probe</button></form>' +
                '<div id="probe-target"></div>';
            document.body.append(probe);
            htmx.process(probe);
        }"""
    )
    page.route(
        "**/probe/422/",
        lambda route: route.fulfill(
            status=422, body="<p>Fix this field.</p>", content_type="text/html"
        ),
    )

    page.locator("#probe-form button").click()

    expect(page.locator("#probe-target")).to_have_text("Fix this field.")
    expect(page.locator("#status")).to_have_text("")
    expect(page.locator("#messages > li")).to_have_count(0)


def _probe(page, status, body):
    """A control declaring nothing about errors: whatever htmx does
    with its failure is the page-wide configuration's doing."""
    page.evaluate(
        """() => {
            const probe = document.createElement("div");
            probe.innerHTML =
                '<form id="probe-form" hx-post="/probe/" ' +
                'hx-target="#probe-target" hx-swap="innerHTML">' +
                '<button type="submit">Probe</button></form>' +
                '<div id="probe-target">Untouched</div>';
            document.body.append(probe);
            htmx.process(probe);
        }"""
    )
    page.route(
        "**/probe/",
        lambda route: route.fulfill(status=status, body=body, content_type="text/html"),
    )
    page.locator("#probe-form button").click()


@pytest.mark.parametrize("status", [404, 500, 502, 503])
def test_an_error_page_is_never_swapped_in_and_is_shown(
    signed_in_page, live_server, status
):
    page = signed_in_page
    page.goto(live_server.url + "/entries/")

    _probe(page, status, "<h1>An error page</h1>")

    expect(page.locator("#messages > li.error")).to_have_text(ERROR_TEXT)
    expect(page.locator("#status")).to_have_text(ERROR_TEXT)
    expect(page.locator("#probe-target")).to_have_text("Untouched")


def test_a_network_failure_is_shown(signed_in_page, live_server):
    page = signed_in_page
    page.goto(live_server.url + "/entries/")
    page.route("**/probe/", lambda route: route.abort())
    page.evaluate(
        """() => {
            const probe = document.createElement("div");
            probe.innerHTML =
                '<form id="probe-form" hx-post="/probe/" ' +
                'hx-target="#probe-target" hx-swap="innerHTML">' +
                '<button type="submit">Probe</button></form>' +
                '<div id="probe-target">Untouched</div>';
            document.body.append(probe);
            htmx.process(probe);
        }"""
    )
    page.locator("#probe-form button").click()

    expect(page.locator("#messages > li.error")).to_have_text(ERROR_TEXT)
    expect(page.locator("#status")).to_have_text(ERROR_TEXT)
