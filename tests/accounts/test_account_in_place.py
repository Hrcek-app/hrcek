"""The account hub's forms answering htmx with their own section.

See docs/dev/accounts.md: each form posts with htmx and gets back only
the content of the section it sits in, so the tab it is on stays put.
Without htmx every view still redirects to ?section= (or re-renders the
whole page on an error), which test_account_page.py covers.
"""

import re

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"
HTMX = {"HX-Request": "true"}


@pytest.fixture
def person():
    return User.objects.create_user(
        email="nina@example.com",
        password=PASSWORD,
        display_name="Nina",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def pending(person):
    person.pending_email = "nina.new@example.com"
    person.save(update_fields=["pending_email"])
    return person


def _status(body):
    match = re.search(
        r'<div id="status"[^>]*hx-swap-oob="innerHTML"[^>]*>(.*?)</div>', body
    )
    assert match, "no out-of-band #status in the fragment"
    return match.group(1)


def _tag(pattern, body):
    match = re.search(pattern, body)
    assert match, f"nothing matches {pattern!r}"
    return match.group(0)


def _vary(response):
    return [v.strip() for v in response.get("Vary", "").split(",")]


SUCCESSES = [
    (
        "accounts:display_name",
        {"display_name": "Nina S"},
        "profile-content",
        "Your display name is now “Nina S”.",
    ),
    (
        "accounts:public_name",
        {"namespace": "ninaw"},
        "profile-content",
        "Your public name is now “ninaw”.",
    ),
    (
        "accounts:email_change",
        {"new_email": "nina2@example.com", "current_password": PASSWORD},
        "sign-in-content",
        "Check nina2@example.com for a confirmation link.",
    ),
]


@pytest.mark.parametrize("case", SUCCESSES)
def test_a_success_answers_htmx_with_its_section(client, person, case):
    url_name, data, content_id, said = case
    client.force_login(person)
    response = client.post(reverse(url_name), data, headers=HTMX)

    assert response.status_code == 200
    body = response.content.decode()
    assert "<html" not in body
    assert body.lstrip().startswith(f'<div class="tab-content" id="{content_id}"')
    assert said in _status(body)
    # The Django message is drained into #messages out of band, so it
    # does not wait for whatever page is loaded next.
    assert 'id="messages"' in body
    assert said in body.split('id="messages"', 1)[1]
    assert "HX-Request" in _vary(response)


def test_cancelling_answers_htmx_with_the_sign_in_section(client, pending):
    client.force_login(pending)
    response = client.post(reverse("accounts:email_change_cancel"), headers=HTMX)

    assert response.status_code == 200
    body = response.content.decode()
    assert body.lstrip().startswith('<div class="tab-content" id="sign-in-content"')
    assert "The change to nina.new@example.com has been cancelled." in _status(body)
    # The section no longer offers to cancel what is gone.
    assert "Cancel the change" not in body
    assert "HX-Request" in _vary(response)
    pending.refresh_from_db()
    assert pending.pending_email is None


def test_the_message_is_not_shown_again_on_the_next_page(client, person):
    client.force_login(person)
    client.post(
        reverse("accounts:display_name"), {"display_name": "Nina S"}, headers=HTMX
    )

    body = client.get(reverse("accounts:account")).content.decode()
    assert "Your display name is now" not in body


def test_the_saved_value_is_in_the_new_section(client, person):
    client.force_login(person)
    body = client.post(
        reverse("accounts:display_name"), {"display_name": "Nina S"}, headers=HTMX
    ).content.decode()
    assert 'value="Nina S"' in body
    person.refresh_from_db()
    assert person.display_name == "Nina S"


def test_an_email_change_shows_the_pending_address_in_place(client, person):
    client.force_login(person)
    body = client.post(
        reverse("accounts:email_change"),
        {"new_email": "nina2@example.com", "current_password": PASSWORD},
        headers=HTMX,
    ).content.decode()
    assert "Waiting for confirmation at nina2@example.com" in body
    assert "Cancel the change" in body


ERRORS = [
    (
        "accounts:display_name",
        {"display_name": "nina@example.com"},
        "profile-content",
        "display_name",
    ),
    (
        "accounts:public_name",
        {"namespace": "not a valid name!"},
        "profile-content",
        "namespace",
    ),
    (
        "accounts:email_change",
        {"new_email": "nina2@example.com", "current_password": "wrong"},
        "sign-in-content",
        "current_password",
    ),
]


@pytest.mark.parametrize("case", ERRORS)
def test_an_error_answers_htmx_with_422_and_its_section(client, person, case):
    url_name, data, content_id, field = case
    client.force_login(person)
    response = client.post(reverse(url_name), data, headers=HTMX)

    assert response.status_code == 422
    body = response.content.decode()
    assert "<html" not in body
    assert body.lstrip().startswith(f'<div class="tab-content" id="{content_id}"')
    assert 'class="errorlist' in body
    # Focus goes to the field that needs fixing; htmx focuses the first
    # [autofocus] in what it swaps in.
    tag = _tag(rf'<input[^>]*name="{field}"[^>]*>', body)
    assert "autofocus" in tag
    assert body.count("autofocus") == 1
    assert "HX-Request" in _vary(response)


def test_an_error_without_htmx_still_renders_the_whole_page(client, person):
    client.force_login(person)
    response = client.post(
        reverse("accounts:public_name"), {"namespace": "not a valid name!"}
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "<html" in body
    # The page's own focus is left to the browser, as before.
    assert "autofocus" not in body
    assert "HX-Request" in _vary(response)


def test_a_redirect_without_htmx_varies_on_htmx_too(client, person):
    client.force_login(person)
    response = client.post(reverse("accounts:display_name"), {"display_name": "Nina S"})
    assert response.status_code == 302
    assert "HX-Request" in _vary(response)


def test_the_page_includes_the_same_section_content(client, person):
    client.force_login(person)
    body = client.get(reverse("accounts:account")).content.decode()
    assert '<div class="tab-content" id="profile-content"' in body
    assert '<div class="tab-content" id="sign-in-content"' in body
    # Each form says where its answer goes: its own section's content,
    # never the <section> tabs.js turned into a tabpanel.
    for url_name, target in [
        ("accounts:display_name", "#profile-content"),
        ("accounts:public_name", "#profile-content"),
        ("accounts:email_change", "#sign-in-content"),
    ]:
        url = reverse(url_name)
        form = _tag(rf'<form[^>]*action="{url}"[^>]*>', body)
        assert f'hx-post="{url}"' in form
        assert f'hx-target="{target}"' in form
        assert 'hx-swap="outerHTML"' in form


def test_the_cancel_form_targets_the_sign_in_content(client, pending):
    client.force_login(pending)
    body = client.get(reverse("accounts:account")).content.decode()
    url = reverse("accounts:email_change_cancel")
    form = _tag(rf'<form[^>]*action="{url}"[^>]*>', body)
    assert f'hx-post="{url}"' in form
    assert 'hx-target="#sign-in-content"' in form
