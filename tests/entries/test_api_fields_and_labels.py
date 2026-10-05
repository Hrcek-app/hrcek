"""Reading what an account has defined, so a client can fit itself to
it: the fields entries may carry, and the labels already in use."""

import pytest
from django.utils import timezone

from hrcek.accounts.models import ApiToken, User
from hrcek.collections.models import Collection
from hrcek.entries.models import Entry, FieldDefinition, Tag

pytestmark = pytest.mark.django_db

FIELDS = "/api/fields/"
LABELS = "/api/labels/"
PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


@pytest.fixture
def signed_in(client, nina):
    client.force_login(nina)
    return client


def _label(owner, name):
    """A label in use: only labels an entry carries are listed."""
    tag = Tag.objects.create(owner=owner, name=name)
    carrier = Entry.objects.create(owner=owner, url=f"https://example.com/{name}")
    carrier.tags.add(tag)
    return tag


def _carry(owner, tags):
    """Many labels at once, all on one entry so they count as in use."""
    tags = Tag.objects.bulk_create(tags)
    carrier = Entry.objects.create(owner=owner, url="https://example.com/carrier")
    carrier.tags.add(*tags)


# --- fields ------------------------------------------------------------


def test_the_seeded_field_is_described(signed_in):
    body = signed_in.get(FIELDS).json()
    by_name = {field["name"]: field for field in body["items"]}

    assert by_name["Priority"]["kind"] == FieldDefinition.CHOICE


def test_a_field_somebody_made_is_described_too(signed_in, nina):
    FieldDefinition.objects.create(owner=nina, name="Cost", kind=FieldDefinition.NUMBER)
    by_name = {field["name"]: field for field in signed_in.get(FIELDS).json()["items"]}
    assert by_name["Cost"]["kind"] == FieldDefinition.NUMBER


def test_a_choice_field_says_what_the_choices_are(signed_in):
    """Without them a client cannot build the input for one."""
    priority = next(
        field
        for field in signed_in.get(FIELDS).json()["items"]
        if field["name"] == "Priority"
    )
    assert priority["options"], "a choice field with no choices is unusable"


def test_a_text_field_has_no_options(signed_in, nina):
    FieldDefinition.objects.create(owner=nina, name="Where", kind=FieldDefinition.TEXT)
    where = next(
        field
        for field in signed_in.get(FIELDS).json()["items"]
        if field["name"] == "Where"
    )
    assert where["options"] == []


def test_fields_come_back_in_a_settled_order(signed_in, nina):
    FieldDefinition.objects.create(owner=nina, name="Aardvark")
    names = [field["name"] for field in signed_in.get(FIELDS).json()["items"]]
    assert names == sorted(names)


def test_you_do_not_see_somebody_elses_fields(signed_in):
    marko = _person("marko@example.com")
    FieldDefinition.objects.create(owner=marko, name="Secret")
    names = [field["name"] for field in signed_in.get(FIELDS).json()["items"]]
    assert "Secret" not in names


def test_fields_need_authentication(client):
    assert client.get(FIELDS).status_code == 401


def test_a_token_can_read_the_fields(client, nina):
    _token, raw = ApiToken.issue(nina, name="extension")
    response = client.get(FIELDS, headers={"authorization": f"Bearer {raw}"})
    assert response.status_code == 200
    assert response.json()["count"] >= 1


# --- labels ------------------------------------------------------------


def test_all_of_your_labels_come_back_with_a_count(signed_in, nina):
    for name in ("watches", "recipes", "reading"):
        _label(nina, name)

    body = signed_in.get(LABELS).json()
    assert body["count"] == 3
    assert {item["name"] for item in body["items"]} == {
        "watches",
        "recipes",
        "reading",
    }


def test_labels_come_back_in_a_settled_order(signed_in, nina):
    for name in ("zebra", "apple", "mango"):
        _label(nina, name)
    names = [item["name"] for item in signed_in.get(LABELS).json()["items"]]
    assert names == sorted(names)


def test_you_do_not_see_somebody_elses_labels(signed_in, nina):
    marko = _person("marko@example.com")
    _label(nina, "mine")
    _label(marko, "theirs")

    body = signed_in.get(LABELS).json()
    assert body["count"] == 1
    assert body["items"][0]["name"] == "mine"


def test_a_prefix_narrows_the_list(signed_in, nina):
    for name in ("watches", "water", "recipes"):
        _label(nina, name)

    body = signed_in.get(LABELS, {"starts_with": "wat"}).json()
    assert {item["name"] for item in body["items"]} == {"watches", "water"}
    assert body["count"] == 2, "the count describes the match, not the whole list"


def test_a_prefix_ignores_capitals(signed_in, nina):
    _label(nina, "Watches")
    body = signed_in.get(LABELS, {"starts_with": "wat"}).json()
    assert [item["name"] for item in body["items"]] == ["Watches"]


def test_a_prefix_matches_the_start_and_not_the_middle(signed_in, nina):
    _label(nina, "watches")
    _label(nina, "smartwatches")
    body = signed_in.get(LABELS, {"starts_with": "wat"}).json()
    assert [item["name"] for item in body["items"]] == ["watches"]


def test_a_prefix_with_no_matches_is_an_empty_list_not_an_error(signed_in, nina):
    _label(nina, "watches")
    body = signed_in.get(LABELS, {"starts_with": "zzz"}).json()
    assert body["items"] == []
    assert body["count"] == 0


def test_a_prefix_of_regex_characters_is_taken_literally(signed_in, nina):
    """`startswith` is not a pattern; a client typing punctuation into
    an autocomplete box must not get surprising matches."""
    _label(nina, "c++")
    _label(nina, "csharp")
    body = signed_in.get(LABELS, {"starts_with": "c+"}).json()
    assert [item["name"] for item in body["items"]] == ["c++"]


def test_surrounding_space_in_a_prefix_is_ignored(signed_in, nina):
    _label(nina, "watches")
    body = signed_in.get(LABELS, {"starts_with": "  wat "}).json()
    assert [item["name"] for item in body["items"]] == ["watches"]


def test_an_empty_prefix_is_the_same_as_asking_for_everything(signed_in, nina):
    _label(nina, "watches")
    _label(nina, "recipes")
    assert signed_in.get(LABELS, {"starts_with": ""}).json()["count"] == 2


def test_labels_are_paginated_and_say_how_many_there_are(signed_in, nina):
    for n in range(12):
        _label(nina, f"label-{n:02d}")

    body = signed_in.get(LABELS, {"limit": 5}).json()
    assert len(body["items"]) == 5, "the page is the size that was asked for"
    assert body["count"] == 12, "the count is how many there are, not how many came"

    later = signed_in.get(
        LABELS, {"limit": 5, "after": body["items"][-1]["name"]}
    ).json()
    assert [item["name"] for item in later["items"]] == [
        f"label-{n:02d}" for n in range(5, 10)
    ]


def test_labels_are_ordered_ignoring_capitals(signed_in, nina):
    """The order a reader expects, and the order paging relies on."""
    for name in ("Zebra", "apple", "Mango"):
        _label(nina, name)
    names = [item["name"] for item in signed_in.get(LABELS).json()["items"]]
    assert names == ["apple", "Mango", "Zebra"]


def test_the_next_page_starts_after_the_last_name_seen(signed_in, nina):
    for name in ("apple", "banana", "cherry", "damson"):
        _label(nina, name)

    first = signed_in.get(LABELS, {"limit": 2}).json()
    assert [item["name"] for item in first["items"]] == ["apple", "banana"]

    second = signed_in.get(LABELS, {"limit": 2, "after": "banana"}).json()
    assert [item["name"] for item in second["items"]] == ["cherry", "damson"]


def test_paging_all_the_way_through_sees_everything_once(signed_in, nina):
    _carry(nina, [Tag(owner=nina, name=f"label-{n:03d}") for n in range(25)])

    seen: list[str] = []
    after = ""
    reached_the_end = False
    # Bounded: an endpoint that ignored the cursor would serve the same
    # page forever, and a test should fail rather than hang.
    for _ in range(10):
        body = signed_in.get(LABELS, {"limit": 10, "after": after}).json()
        names = [item["name"] for item in body["items"]]
        if not names:
            reached_the_end = True
            break
        seen.extend(names)
        after = names[-1]
    assert reached_the_end, "the cursor was ignored; paging never ended"

    assert len(seen) == 25
    assert len(set(seen)) == 25, "a label was served twice"
    assert seen == sorted(seen, key=str.casefold)


def test_a_label_added_mid_paging_does_not_hide_another(signed_in, nina):
    """The reason for a cursor rather than an offset.

    With an offset, inserting a row before the current position pushes
    everything along, and the next page skips whatever slid over the
    boundary.
    """
    for name in ("bravo", "charlie", "delta"):
        _label(nina, name)

    first = signed_in.get(LABELS, {"limit": 2}).json()
    assert [item["name"] for item in first["items"]] == ["bravo", "charlie"]

    _label(nina, "alpha")  # sorts before everything already served

    second = signed_in.get(LABELS, {"limit": 2, "after": "charlie"}).json()
    assert [item["name"] for item in second["items"]] == ["delta"], (
        "delta was skipped because the page moved under the reader"
    )


def test_the_cursor_ignores_capitals_like_the_order_does(signed_in, nina):
    for name in ("Apple", "banana"):
        _label(nina, name)
    body = signed_in.get(LABELS, {"after": "APPLE"}).json()
    assert [item["name"] for item in body["items"]] == ["banana"]


def test_a_cursor_naming_nothing_still_makes_sense(signed_in, nina):
    """Whatever comes after it alphabetically, rather than an error:
    a label can be deleted while somebody is reading."""
    for name in ("apple", "cherry"):
        _label(nina, name)
    body = signed_in.get(LABELS, {"after": "banana"}).json()
    assert [item["name"] for item in body["items"]] == ["cherry"]


def test_a_cursor_past_the_end_is_an_empty_page(signed_in, nina):
    _label(nina, "apple")
    body = signed_in.get(LABELS, {"after": "zebra"}).json()
    assert body["items"] == []


def test_a_cursor_works_alongside_a_prefix(signed_in, nina):
    for name in ("watches", "water", "waterfall", "recipes"):
        _label(nina, name)

    body = signed_in.get(
        LABELS, {"starts_with": "wat", "after": "watches", "limit": 1}
    ).json()
    assert [item["name"] for item in body["items"]] == ["water"]
    assert body["count"] == 3, "the count describes the whole match"


def test_asking_plainly_brings_back_up_to_a_thousand(signed_in, nina):
    """Enough labels exist here that the page size is what limits the
    answer, not the data."""
    _carry(nina, [Tag(owner=nina, name=f"label-{n:05d}") for n in range(1005)])

    body = signed_in.get(LABELS).json()
    assert len(body["items"]) == 1000, "a plain request should fill a page"
    assert body["count"] == 1005, "the count still says how many there are"

    rest = signed_in.get(LABELS, {"after": body["items"][-1]["name"]}).json()
    assert len(rest["items"]) == 5, "the rest is reachable by paging"


def test_asking_for_more_than_a_page_is_refused_plainly(signed_in, nina):
    """Told, not silently truncated: a client that believes it asked
    for five thousand and got a thousand would page wrongly. The limit
    is published in the schema as a maximum, so this is not a
    surprise."""
    response = signed_in.get(LABELS, {"limit": 5000})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "HRC-CORE-0002"


def test_labels_need_authentication(client):
    assert client.get(LABELS).status_code == 401


def test_a_label_no_entry_uses_is_not_listed(signed_in, nina):
    """Tags are pruned when nothing carries them, so an autocomplete
    never offers a label that has already gone."""
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    entry.tags.add(Tag.objects.create(owner=nina, name="watches"))
    assert signed_in.get(LABELS).json()["count"] == 1

    entry.delete()
    Tag.prune_orphans(nina)
    assert signed_in.get(LABELS).json()["count"] == 0


def test_a_label_kept_for_a_collection_is_not_listed(signed_in, nina):
    """A collection can keep a label nothing carries; an autocomplete
    must still not offer it."""
    Collection.objects.create(
        owner=nina,
        name="Wants",
        kind=Collection.BY_LABEL,
        label=Tag.objects.create(owner=nina, name="want"),
    )
    assert signed_in.get(LABELS).json()["count"] == 0
