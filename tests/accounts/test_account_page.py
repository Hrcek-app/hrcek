import re

import pytest
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from hrcek.accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _section_tag(body, section_id):
    """The opening <section> tag for one id, for a data-open assertion."""
    match = re.search(rf'<section[^>]*\bid="{section_id}"[^>]*>', body)
    assert match, f"no section with id={section_id!r} in the page"
    return match.group(0)


@pytest.fixture
def person():
    return User.objects.create_user(
        email="nina@example.com",
        password=PASSWORD,
        display_name="Nina",
        email_verified_at=timezone.now(),
    )


def test_the_account_page_needs_a_session(client):
    response = client.get(reverse("accounts:account"))
    assert response.status_code == 302
    assert "/?next=" in response["Location"]


def test_it_shows_the_current_details(client, person):
    client.force_login(person)
    body = client.get(reverse("accounts:account")).content.decode()
    assert "nina@example.com" in body
    assert "Nina" in body


def test_the_display_name_can_be_changed(client, person):
    client.force_login(person)
    response = client.post(reverse("accounts:display_name"), {"display_name": "Nina S"})
    assert response.status_code == 302
    person.refresh_from_db()
    assert person.display_name == "Nina S"


def test_the_display_name_can_be_cleared(client, person):
    client.force_login(person)
    client.post(reverse("accounts:display_name"), {"display_name": ""})
    person.refresh_from_db()
    assert person.display_name is None


def test_a_name_another_person_holds_is_refused(client, person):
    User.objects.create_user(
        email="other@example.com", password=PASSWORD, display_name="Marko"
    )
    client.force_login(person)
    response = client.post(reverse("accounts:display_name"), {"display_name": "marko"})
    assert response.status_code == 200
    person.refresh_from_db()
    assert person.display_name == "Nina"


def test_keeping_your_own_name_is_not_a_collision(client, person):
    client.force_login(person)
    response = client.post(reverse("accounts:display_name"), {"display_name": "Nina"})
    assert response.status_code == 302


def test_an_at_sign_is_refused(client, person):
    client.force_login(person)
    response = client.post(
        reverse("accounts:display_name"), {"display_name": "nina@example.com"}
    )
    assert response.status_code == 200
    person.refresh_from_db()
    assert person.display_name == "Nina"


def test_signing_in_lands_on_the_entry_list(client, person):
    """The destination, named rather than inferred from a setting.

    test_landing.py can only assert against LOGIN_REDIRECT_URL, because
    it cannot depend on a page from a later layer. Here we can name it:
    signing in should land on your entries, not your settings.
    """
    response = client.post("/", {"username": "nina@example.com", "password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == reverse("entries:list")


def test_a_signed_in_visitor_at_the_root_goes_to_their_entries(client, person):
    client.force_login(person)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == reverse("entries:list")


def test_the_welcome_page_is_gone():
    with pytest.raises(NoReverseMatch):
        reverse("accounts:welcome")


def test_the_account_page_has_three_sections(client, person):
    client.force_login(person)
    body = client.get(reverse("accounts:account")).content.decode()
    assert "<div data-tabs" in body
    assert _section_tag(body, "profile")
    assert _section_tag(body, "sign-in")
    assert _section_tag(body, "fields")
    assert "Profile" in body
    assert "Sign-in" in body
    assert "Fields and clients" in body


@pytest.mark.parametrize(
    ("url_name", "data", "section"),
    [
        ("accounts:display_name", {"display_name": "Nina S"}, "profile"),
        ("accounts:public_name", {"namespace": "ninaw"}, "profile"),
        (
            "accounts:email_change",
            {"new_email": "nina2@example.com", "current_password": PASSWORD},
            "sign-in",
        ),
        ("accounts:email_change_cancel", {}, "sign-in"),
    ],
)
def test_each_form_returns_to_its_section(client, person, url_name, data, section):
    client.force_login(person)
    response = client.post(reverse(url_name), data)
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:account") + "?section=" + section


def test_an_error_marks_its_section_open(client, person):
    client.force_login(person)
    response = client.post(
        reverse("accounts:public_name"), {"namespace": "not a valid name!"}
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "data-open" in _section_tag(body, "profile")
    assert "data-open" not in _section_tag(body, "sign-in")
    assert "data-open" not in _section_tag(body, "fields")


def test_the_duplicated_intro_text_is_gone(client, person):
    client.force_login(person)
    body = client.get(reverse("accounts:account")).content.decode()
    # These sentences are the model fields' help_text, already shown
    # beside each input; the template used to repeat them above the
    # form.
    assert "You can sign in with this instead of your email." not in body
    assert "Your public name appears in the address of every public" not in body


def test_a_section_query_parameter_opens_that_section(client, person):
    client.force_login(person)
    body = client.get(
        reverse("accounts:account"), {"section": "sign-in"}
    ).content.decode()
    assert "data-open" in _section_tag(body, "sign-in")
    assert "data-open" not in _section_tag(body, "profile")
    assert "data-open" not in _section_tag(body, "fields")


def test_an_unknown_section_query_parameter_is_ignored(client, person):
    client.force_login(person)
    body = client.get(
        reverse("accounts:account"), {"section": "not-a-real-section"}
    ).content.decode()
    assert "data-open" not in _section_tag(body, "profile")
    assert "data-open" not in _section_tag(body, "sign-in")
    assert "data-open" not in _section_tag(body, "fields")


def test_the_sign_in_section_has_an_email_address_heading(client, person):
    client.force_login(person)
    body = client.get(reverse("accounts:account")).content.decode()
    assert re.search(r"<h3[^>]*>\s*Email address\s*</h3>", body)
