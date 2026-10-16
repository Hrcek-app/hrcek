"""The options editor on a choice field's page, by plain round trips."""

import json

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.entries.models import Entry, FieldDefinition, FieldValue

pytestmark = pytest.mark.django_db


@pytest.fixture
def nina():
    return User.objects.create_user(
        email="nina@example.com",
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def size(nina):
    return FieldDefinition.objects.create(
        owner=nina, name="Size", kind=FieldDefinition.CHOICE, options=["s", "m", "l"]
    )


@pytest.fixture
def signed_in(client, nina):
    client.force_login(nina)
    return client


def _post(client, definition, op, rows, **extra):
    """Post the editor as a browser would: every row, plus one button."""
    known = extra.pop("known", None)
    new = extra.pop("new", "")
    data = {
        "name": extra.pop("name", definition.name),
        "option": [text for text, _ in rows],
        "original": [original for _, original in rows],
        "known": json.dumps(definition.options if known is None else known),
        "new_option": new,
        "op": op,
        **extra,
    }
    return client.post(reverse("entries:field_options", args=[definition.pk]), data)


def _same(*texts):
    return [(text, text) for text in texts]


def _shown(response):
    return [(row["text"], row["original"]) for row in response.context["rows"]]


def _value(owner, definition, text, n=[0]):  # noqa: B006
    n[0] += 1
    entry = Entry.objects.create(owner=owner, url=f"https://example.com/{n[0]}")
    FieldValue.objects.create(entry=entry, definition=definition, value_text=text)


# Creating one.


def test_a_choice_field_can_be_created_and_opens_its_editor(signed_in, nina):
    response = signed_in.post(
        reverse("entries:fields"), {"name": "Mood", "kind": "choice"}
    )
    mood = FieldDefinition.objects.get(owner=nina, name="Mood")
    assert mood.kind == FieldDefinition.CHOICE
    assert mood.options == []
    assert response.status_code == 302
    assert response.url == reverse("entries:field_edit", args=[mood.pk])


def test_the_entry_form_leaves_out_a_choice_field_without_options(signed_in, nina):
    FieldDefinition.objects.create(owner=nina, name="Mood", kind="choice")
    body = signed_in.get(reverse("entries:create")).text
    assert "Mood" not in body
    assert "Priority" in body


def test_the_fields_list_links_to_edit(signed_in, size):
    body = signed_in.get(reverse("entries:fields")).text
    assert ">Edit<" in body
    assert ">Rename<" not in body


# The edit page.


def test_the_editor_shows_for_a_choice_field(signed_in, size):
    response = signed_in.get(reverse("entries:field_edit", args=[size.pk]))
    assert _shown(response) == _same("s", "m", "l")
    assert "data-options-editor" in response.text


def test_the_editor_is_absent_for_other_kinds(signed_in, nina):
    cost = FieldDefinition.objects.create(owner=nina, name="Cost", kind="number")
    response = signed_in.get(reverse("entries:field_edit", args=[cost.pk]))
    assert "data-options-editor" not in response.text


def test_the_editor_says_how_many_entries_use_each_option(signed_in, nina, size):
    _value(nina, size, "m")
    _value(nina, size, "m")
    response = signed_in.get(reverse("entries:field_edit", args=[size.pk]))
    used = {row["text"]: row["used"] for row in response.context["rows"]}
    assert used == {"s": 0, "m": 2, "l": 0}
    assert "used by 2 entries" in response.text


def test_somebody_elses_field_is_a_404(client, size):
    marko = User.objects.create_user(
        email="marko@example.com", password="a-long-enough-passphrase"
    )
    client.force_login(marko)
    assert _post(client, size, "save", _same("s")).status_code == 404


def test_a_get_goes_back_to_the_edit_page(signed_in, size):
    response = signed_in.get(reverse("entries:field_options", args=[size.pk]))
    assert response.status_code == 302
    assert response.url == reverse("entries:field_edit", args=[size.pk])


# Round trips: each button changes the list on the page and saves nothing.


@pytest.mark.parametrize(
    ("op", "expected"),
    [
        ("up:1", [("m", "m"), ("small", "s"), ("l", "l")]),
        ("down:1", [("small", "s"), ("l", "l"), ("m", "m")]),
        ("remove:0", [("m", "m"), ("l", "l")]),
        ("add", [("small", "s"), ("m", "m"), ("l", "l"), ("xl", "")]),
    ],
)
def test_a_button_redraws_the_list_and_saves_nothing(signed_in, size, op, expected):
    rows = [("small", "s"), ("m", "m"), ("l", "l")]
    response = _post(signed_in, size, op, rows, new="xl")
    assert response.status_code == 200
    # The typed rename survives every round trip.
    assert _shown(response) == expected
    size.refresh_from_db()
    assert size.options == ["s", "m", "l"]


def test_the_new_option_survives_a_move(signed_in, size):
    response = _post(signed_in, size, "up:1", _same("s", "m", "l"), new="xl")
    assert response.context["new_option"] == "xl"


def test_add_empties_the_new_option(signed_in, size):
    response = _post(signed_in, size, "add", _same("s"), new="xl")
    assert response.context["new_option"] == ""


def test_a_redrawn_list_is_marked_unsaved(signed_in, size):
    response = _post(signed_in, size, "remove:0", _same("s", "m", "l"))
    assert 'data-unsaved="true"' in response.text


def test_the_known_list_is_carried_through(signed_in, size):
    response = _post(signed_in, size, "add", _same("s", "m", "l"), new="xl")
    assert json.loads(response.context["known_json"]) == ["s", "m", "l"]


# Saving.


def test_save_stores_the_list(signed_in, size):
    response = _post(signed_in, size, "save", _same("l", "m", "s"))
    assert response.status_code == 302
    assert response.url == reverse("entries:field_edit", args=[size.pk])
    size.refresh_from_db()
    assert size.options == ["l", "m", "s"]


def test_save_says_so(signed_in, size):
    response = _post(signed_in, size, "save", _same("l", "m", "s"))
    assert "Field saved." in signed_in.get(response.url).text


def test_save_includes_the_pending_new_option(signed_in, size):
    _post(signed_in, size, "save", _same("s", "m", "l"), new="xl")
    size.refresh_from_db()
    assert size.options == ["s", "m", "l", "xl"]


def test_save_renames_values(signed_in, nina, size):
    _value(nina, size, "s")
    _post(signed_in, size, "save", [("small", "s"), ("m", "m"), ("l", "l")])
    assert FieldValue.objects.get(definition=size).value_text == "small"


def test_an_unused_removal_saves_silently(signed_in, size):
    response = _post(signed_in, size, "save", _same("s", "m"))
    assert response.status_code == 302
    size.refresh_from_db()
    assert size.options == ["s", "m"]


def test_a_used_removal_asks_first(signed_in, nina, size):
    _value(nina, size, "l")
    _value(nina, size, "l")
    response = _post(signed_in, size, "save", _same("s", "m"))
    assert response.status_code == 200
    assert response.context["affected"] == {"l": 2}
    assert "This will clear the field on 2 entries." in response.text
    size.refresh_from_db()
    assert size.options == ["s", "m", "l"]
    assert FieldValue.objects.filter(definition=size).count() == 2


def test_confirming_removes_and_clears(signed_in, nina, size):
    _value(nina, size, "l")
    response = _post(signed_in, size, "save", _same("s", "m"), confirmed="1")
    assert response.status_code == 302
    size.refresh_from_db()
    assert size.options == ["s", "m"]
    assert not FieldValue.objects.filter(definition=size).exists()


def test_the_confirmation_carries_every_row(signed_in, nina, size):
    _value(nina, size, "l")
    response = _post(signed_in, size, "save", [("small", "s"), ("m", "m")], new="xl")
    assert _shown(response) == [("small", "s"), ("m", "m"), ("xl", "")]
    assert 'name="confirmed"' in response.text


def test_going_back_restores_the_rows(signed_in, size):
    rows = [("small", "s"), ("m", "m")]
    response = _post(signed_in, size, "back", rows)
    assert response.status_code == 200
    assert "data-options-editor" in response.text
    assert _shown(response) == rows


def test_a_stale_form_saves_nothing_and_keeps_what_was_typed(signed_in, size):
    # Another tab added xl after this one opened.
    size.options = ["s", "m", "l", "xl"]
    size.save()
    rows = [("small", "s"), ("m", "m")]
    response = _post(signed_in, size, "save", rows, known=["s", "m", "l"], new="xs")
    assert response.status_code == 200
    assert "changed somewhere else" in response.text
    # What was typed stays, l stays removed, and the other tab's xl is
    # brought in rather than dropped.
    assert _shown(response) == [*rows, ("xs", ""), ("xl", "xl")]
    assert json.loads(response.context["known_json"]) == ["s", "m", "l", "xl"]
    assert 'data-unsaved="true"' in response.text
    size.refresh_from_db()
    assert size.options == ["s", "m", "l", "xl"]


def test_a_stale_row_whose_option_went_elsewhere_becomes_new(signed_in, size):
    # Another tab renamed s to S.
    size.options = ["S", "m", "l"]
    size.save()
    rows = [("small", "s"), *_same("m", "l")]
    response = _post(signed_in, size, "save", rows, known=["s", "m", "l"])
    assert _shown(response) == [("small", ""), *_same("m", "l"), ("S", "S")]


def test_saving_again_after_a_stale_form_works(signed_in, size):
    size.options = ["s", "m", "l", "xl"]
    size.save()
    stale = _post(signed_in, size, "save", _same("l", "m", "s"), known=["s", "m", "l"])
    rows = [(row["text"], row["original"]) for row in stale.context["rows"]]
    known = json.loads(stale.context["known_json"])
    _post(signed_in, size, "save", rows, known=known)
    size.refresh_from_db()
    assert size.options == ["l", "m", "s", "xl"]


# The name rides in the same form, so neither loses the other.


def test_a_round_trip_keeps_the_typed_name(signed_in, size):
    response = _post(signed_in, size, "up:1", _same("s", "m", "l"), name="Fit")
    assert 'value="Fit"' in response.text
    size.refresh_from_db()
    assert size.name == "Size"


def test_save_stores_the_name_and_the_options(signed_in, size):
    _post(signed_in, size, "save", _same("l", "m", "s"), name="Fit")
    size.refresh_from_db()
    assert (size.name, size.options) == ("Fit", ["l", "m", "s"])


def test_a_refused_name_saves_nothing_and_keeps_the_rows(signed_in, nina, size):
    FieldDefinition.objects.create(owner=nina, name="Fit", kind="text")
    rows = [("small", "s"), ("m", "m")]
    response = _post(signed_in, size, "save", rows, name="fit")
    assert response.status_code == 200
    assert "You already have a field with that name." in response.text
    assert _shown(response) == rows
    size.refresh_from_db()
    assert (size.name, size.options) == ("Size", ["s", "m", "l"])


def test_the_confirmation_carries_the_name(signed_in, nina, size):
    _value(nina, size, "l")
    response = _post(signed_in, size, "save", _same("s", "m"), name="Fit")
    assert 'name="name" value="Fit"' in response.text


def test_the_choice_page_is_one_form(signed_in, size):
    response = signed_in.get(reverse("entries:field_edit", args=[size.pk]))
    # The page frame has forms of its own (signing out, the language).
    assert response.text.count(f'action="/entries/fields/{size.pk}/') == 1


def test_a_refused_list_keeps_the_input(signed_in, size):
    rows = [("s", "s"), ("M", ""), ("m", "m")]
    response = _post(signed_in, size, "save", rows)
    assert response.status_code == 200
    assert "is in the list twice" in response.text
    assert _shown(response) == rows
    size.refresh_from_db()
    assert size.options == ["s", "m", "l"]


def test_a_row_without_an_original_counts_as_new(signed_in, size):
    # Only a hand-made request can send fewer originals than rows.
    url = reverse("entries:field_options", args=[size.pk])
    response = signed_in.post(
        url,
        {
            "option": ["s", "m", "l", "xl"],
            "original": ["s", "m", "l"],
            "known": json.dumps(["s", "m", "l"]),
            "op": "add",
        },
    )
    assert _shown(response) == [*_same("s", "m", "l"), ("xl", "")]


@pytest.mark.parametrize("known", ["nonsense", "{}", "[1, 2]"])
def test_an_unreadable_known_list_counts_as_stale(signed_in, size, known):
    url = reverse("entries:field_options", args=[size.pk])
    response = signed_in.post(
        url, {"option": ["s"], "original": ["s"], "known": known, "op": "save"}
    )
    assert "changed somewhere else" in response.text
    size.refresh_from_db()
    assert size.options == ["s", "m", "l"]
