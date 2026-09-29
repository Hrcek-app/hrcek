import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.entries.models import Entry, FieldDefinition, FieldValue
from tests.entries.helpers import _structure

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    """An account with a second field beside the seeded Priority.

    Only Priority is seeded now, so a test that wants two fields makes
    the other one.
    """
    person = _person("nina@example.com")
    FieldDefinition.objects.create(
        owner=person, name="Cost", kind=FieldDefinition.NUMBER
    )
    return person


def test_the_page_needs_a_session(client):
    assert client.get(reverse("entries:fields")).status_code == 302


def test_it_lists_your_fields(client, nina):
    client.force_login(nina)
    body = client.get(reverse("entries:fields")).content.decode()
    assert "Cost" in body
    assert "Priority" in body


def test_it_lists_nobody_elses(client, nina):
    marko = _person("marko@example.com")
    FieldDefinition.objects.create(owner=marko, name="Secret")
    client.force_login(nina)
    assert "Secret" not in client.get(reverse("entries:fields")).content.decode()


def test_the_fields_are_marked_up_as_a_list(client, nina):
    client.force_login(nina)
    parsed = _structure(client.get(reverse("entries:fields")))
    rename_links = [a for a in parsed.anchors if "/edit/" in a[0]]
    assert len(rename_links) == 2, "no rename links rendered"
    for href, ancestors in rename_links:
        assert "li" in ancestors, f"{href} is not inside a list item"
        assert "ul" in ancestors, f"{href} is not inside a list"


def test_a_field_can_be_added(client, nina):
    client.force_login(nina)
    response = client.post(
        reverse("entries:fields"), {"name": "Seller", "kind": "text"}
    )
    assert response.status_code == 302
    assert FieldDefinition.objects.filter(owner=nina, name="Seller").exists()


def test_a_new_field_belongs_to_the_person_who_added_it(client, nina):
    _person("marko@example.com")
    client.force_login(nina)
    client.post(reverse("entries:fields"), {"name": "Seller", "kind": "text"})
    assert FieldDefinition.objects.get(name="Seller").owner == nina


def test_a_duplicate_name_is_refused_in_any_casing(client, nina):
    client.force_login(nina)
    response = client.post(
        reverse("entries:fields"), {"name": "cost", "kind": "number"}
    )
    assert response.status_code == 200
    assert FieldDefinition.objects.filter(owner=nina).count() == 2


def test_choice_cannot_be_created_through_the_form(client, nina):
    # It exists in the model for the seeded priority, and nowhere else.
    client.force_login(nina)
    response = client.post(
        reverse("entries:fields"), {"name": "Mood", "kind": "choice"}
    )
    assert response.status_code == 200
    assert not FieldDefinition.objects.filter(owner=nina, name="Mood").exists()


def test_a_field_can_be_renamed(client, nina):
    priority = FieldDefinition.objects.get(owner=nina, name="Priority")
    client.force_login(nina)
    response = client.post(
        reverse("entries:field_edit", args=[priority.pk]), {"name": "Urgency"}
    )
    assert response.status_code == 302
    priority.refresh_from_db()
    assert priority.name == "Urgency"
    # Renaming must not change what it holds.
    assert priority.kind == FieldDefinition.CHOICE
    assert priority.options == ["high", "medium", "low"]


def test_a_rename_may_keep_the_same_name(client, nina):
    price = FieldDefinition.objects.get(owner=nina, name="Cost")
    client.force_login(nina)
    assert (
        client.post(
            reverse("entries:field_edit", args=[price.pk]), {"name": "Cost"}
        ).status_code
        == 302
    )


def test_a_rename_onto_another_field_is_refused(client, nina):
    price = FieldDefinition.objects.get(owner=nina, name="Cost")
    client.force_login(nina)
    response = client.post(
        reverse("entries:field_edit", args=[price.pk]), {"name": "priority"}
    )
    assert response.status_code == 200
    price.refresh_from_db()
    assert price.name == "Cost"


def test_editing_somebody_elses_field_is_a_404(client, nina):
    marko = _person("marko@example.com")
    theirs = FieldDefinition.objects.get(owner=marko, name="Priority")
    client.force_login(nina)
    assert (
        client.get(reverse("entries:field_edit", args=[theirs.pk])).status_code == 404
    )


def test_deleting_somebody_elses_field_is_a_404(client, nina):
    marko = _person("marko@example.com")
    theirs = FieldDefinition.objects.get(owner=marko, name="Priority")
    client.force_login(nina)
    assert (
        client.post(reverse("entries:field_delete", args=[theirs.pk])).status_code
        == 404
    )


def test_deleting_asks_first_and_says_how_many_entries(client, nina):
    price = FieldDefinition.objects.get(owner=nina, name="Cost")
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    FieldValue.objects.create(entry=entry, definition=price, value_number=1)
    client.force_login(nina)
    response = client.get(reverse("entries:field_delete", args=[price.pk]))
    assert response.status_code == 200
    assert response.context["value_count"] == 1
    assert FieldDefinition.objects.filter(pk=price.pk).exists()


def test_deleting_removes_the_field_and_its_values(client, nina):
    price = FieldDefinition.objects.get(owner=nina, name="Cost")
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    FieldValue.objects.create(entry=entry, definition=price, value_number=1)
    client.force_login(nina)
    assert (
        client.post(reverse("entries:field_delete", args=[price.pk])).status_code == 302
    )
    assert not FieldDefinition.objects.filter(pk=price.pk).exists()
    assert FieldValue.objects.count() == 0


def test_the_entry_list_does_not_link_to_the_fields_page(client, nina):
    """Fields are set up rarely; the list is for reading entries."""
    client.force_login(nina)
    body = client.get(reverse("entries:list")).content.decode()
    assert reverse("entries:fields") not in body


@pytest.mark.parametrize("page", ["create", "edit"])
def test_the_entry_form_links_to_the_fields_page(client, nina, page):
    """Where fields are filled in is where somebody finds one missing."""
    entry = Entry.objects.create(owner=nina, url="https://example.com/x")
    client.force_login(nina)
    url = (
        reverse("entries:create")
        if page == "create"
        else reverse("entries:edit", args=[entry.pk])
    )
    assert f'href="{reverse("entries:fields")}"' in client.get(url).text


def test_the_account_page_links_to_the_fields_page(client, nina):
    client.force_login(nina)
    body = client.get(reverse("accounts:account")).text
    assert f'href="{reverse("entries:fields")}"' in body


def test_the_fields_link_on_the_entry_form_opens_a_new_tab(client, nina):
    """Following it must not leave a half-filled form behind."""
    client.force_login(nina)
    body = client.get(reverse("entries:create")).text
    link = f'<a href="{reverse("entries:fields")}" target="_blank" rel="noopener">'
    assert link in body
