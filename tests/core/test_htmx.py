"""The htmx helper, and what every page gives htmx to work with."""

import pytest
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.core.htmx import is_htmx, vary_on_htmx
from hrcek.entries.services import save_entry

PASSWORD = "a-long-enough-passphrase"


@pytest.fixture
def person(db):
    return User.objects.create_user(
        email="htmx@example.com", password=PASSWORD, email_verified_at=timezone.now()
    )


def test_a_plain_request_is_not_htmx(rf):
    assert is_htmx(rf.get("/")) is False


def test_an_htmx_request_is_recognised(rf):
    assert is_htmx(rf.get("/", headers={"HX-Request": "true"})) is True


def test_responses_vary_on_htmx():
    response = vary_on_htmx(HttpResponse())
    assert "HX-Request" in response["Vary"]


def test_every_page_loads_htmx_and_has_a_status_region(client, person):
    client.force_login(person)
    body = client.get("/entries/").content.decode()
    assert "js/vendor/htmx-4.0.0.min.js" in body
    assert 'id="status"' in body and 'aria-live="polite"' in body
    assert "hx-headers:inherited" in body


def test_the_page_has_one_status_region_and_it_is_not_out_of_band(client, person):
    client.force_login(person)
    body = client.get("/entries/").content.decode()
    assert body.count('id="status"') == 1
    assert "hx-swap-oob" not in body


def test_a_fragment_status_region_swaps_out_of_band():
    html = render_to_string("_status.html", {"status": "Deleted.", "oob": True})
    assert 'id="status"' in html
    # Only the text moves into the page's own region: replacing the
    # live region itself is the least reliably announced pattern.
    assert 'hx-swap-oob="innerHTML"' in html
    assert "Deleted." in html


def test_every_entry_has_a_delete_dialog_with_the_same_post_form(client, person):
    entry, _ = save_entry(person, url="https://example.com/a", title="A thing")
    client.force_login(person)
    body = client.get("/entries/").content.decode()
    assert "js/confirm-dialog.js" in body
    assert f'data-confirm-dialog="delete-{entry.pk}"' in body
    assert f'<dialog id="delete-{entry.pk}"' in body
    assert f'action="{reverse("entries:delete", args=[entry.pk])}"' in body
