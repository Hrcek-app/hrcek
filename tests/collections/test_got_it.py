"""The rules of a wish list, below the pages."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections import errors
from hrcek.collections.models import Collection, CollectionEntry, GotIt
from hrcek.collections.services import (
    already_got_on,
    get_it,
    got_by_viewer,
    got_entry_ids,
    label_wish_lists_holding,
    put_back,
    shared_entries,
    undo_got_it,
)
from hrcek.core.errors import HrcekError
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db


def _person(email, **extra):
    return User.objects.create_user(
        email=email,
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
        **extra,
    )


@pytest.fixture
def nina():
    return _person("nina@example.com", namespace="nina")


@pytest.fixture
def ana():
    return _person("ana@example.com")


@pytest.fixture
def bor():
    return _person("bor@example.com")


@pytest.fixture
def wishes(nina):
    return Collection.objects.create(
        owner=nina,
        name="Birthday",
        visibility=Collection.UNLISTED,
        is_wish_list=True,
    )


def _on(collection, url="https://example.com/watch"):
    entry = Entry.objects.create(owner=collection.owner, url=url, title="A watch")
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return entry


def _raises(code, fn, *args):
    with pytest.raises(HrcekError) as caught:
        fn(*args)
    assert caught.value.error_code is code


def test_a_visitor_gets_an_item(wishes, ana):
    entry = _on(wishes)
    got = get_it(wishes, entry, ana)
    assert (got.collection, got.entry, got.got_by) == (wishes, entry, ana)
    assert got_entry_ids(wishes) == {entry.pk}


def test_getting_it_twice_is_harmless(wishes, ana):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    get_it(wishes, entry, ana)
    assert GotIt.objects.count() == 1


def test_somebody_else_cannot_get_it_again(wishes, ana, bor):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    _raises(errors.ALREADY_GOT, get_it, wishes, entry, bor)


def test_the_owner_cannot_get_from_their_own_list(wishes, nina):
    _raises(errors.OWN_WISH_LIST, get_it, wishes, _on(wishes), nina)


def test_an_ordinary_collection_is_not_a_wish_list(wishes, ana):
    entry = _on(wishes)
    wishes.is_wish_list = False
    wishes.save()
    _raises(errors.NOT_A_WISH_LIST, get_it, wishes, entry, ana)


def test_a_private_wish_list_cannot_be_got_from(wishes, ana):
    entry = _on(wishes)
    wishes.visibility = Collection.PRIVATE
    wishes.save()
    _raises(errors.NOT_A_WISH_LIST, get_it, wishes, entry, ana)


def test_an_entry_off_the_list_cannot_be_got(wishes, nina, ana):
    elsewhere = Entry.objects.create(owner=nina, url="https://example.com/x")
    _raises(errors.NOT_ON_THE_LIST, get_it, wishes, elsewhere, ana)


def test_a_mark_belongs_to_one_list(wishes, nina, ana):
    entry = _on(wishes)
    other = Collection.objects.create(
        owner=nina, name="Christmas", visibility=Collection.UNLISTED, is_wish_list=True
    )
    CollectionEntry.objects.create(collection=other, entry=entry)
    get_it(wishes, entry, ana)
    assert got_entry_ids(other) == set()


def test_whoever_got_it_can_undo(wishes, ana):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    undo_got_it(wishes, entry, ana)
    assert got_entry_ids(wishes) == set()


def test_undoing_nothing_is_harmless(wishes, ana):
    undo_got_it(wishes, _on(wishes), ana)


def test_nobody_else_can_undo(wishes, ana, bor):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    _raises(errors.NOT_YOURS_TO_UNDO, undo_got_it, wishes, entry, bor)


def test_the_owner_puts_it_back(wishes, ana):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    put_back(wishes, entry.pk)
    assert got_entry_ids(wishes) == set()


def test_a_mark_off_the_list_is_inert_and_returns_with_it(wishes, ana):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    CollectionEntry.objects.filter(entry=entry).delete()
    assert got_entry_ids(wishes) == set()
    CollectionEntry.objects.create(collection=wishes, entry=entry)
    assert got_entry_ids(wishes) == {entry.pk}


def test_switching_off_suspends_marks_and_on_restores_them(wishes, ana):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    wishes.is_wish_list = False
    wishes.save()
    assert got_entry_ids(wishes) == set()
    assert list(shared_entries(wishes, AnonymousUser())) == [entry]
    wishes.is_wish_list = True
    wishes.save()
    assert got_entry_ids(wishes) == {entry.pk}


def test_what_each_viewer_is_shown(wishes, nina, ana, bor):
    got = _on(wishes, "https://example.com/got")
    free = _on(wishes, "https://example.com/free")
    get_it(wishes, got, ana)
    assert set(shared_entries(wishes, AnonymousUser())) == {free}
    assert set(shared_entries(wishes, bor)) == {free}
    assert set(shared_entries(wishes, ana)) == {got, free}
    assert set(shared_entries(wishes, nina)) == {got, free}


def test_label_wish_lists_work_too(nina, ana):
    tag = Tag.objects.create(owner=nina, name="want")
    wishes = Collection.objects.create(
        owner=nina,
        name="Wants",
        kind=Collection.BY_LABEL,
        label=tag,
        visibility=Collection.UNLISTED,
        is_wish_list=True,
    )
    entry = Entry.objects.create(owner=nina, url="https://example.com/w")
    entry.tags.add(tag)
    assert label_wish_lists_holding(entry) == {wishes.pk}
    get_it(wishes, entry, ana)
    assert already_got_on(entry, {wishes.pk}) == [wishes]
    entry.tags.clear()
    assert label_wish_lists_holding(entry) == set()


def test_the_form_can_make_a_wish_list(client, nina):
    client.force_login(nina)
    client.post(
        "/collections/new/",
        {
            "name": "Birthday",
            "kind": "manual",
            "visibility": "unlisted",
            "is_wish_list": "on",
        },
    )
    assert Collection.objects.get(name="Birthday").is_wish_list


def test_a_giver_knows_what_they_got(wishes, ana, bor):
    entry = _on(wishes)
    get_it(wishes, entry, ana)
    assert got_by_viewer(wishes, ana) == {entry.pk}
    assert got_by_viewer(wishes, bor) == set()
    assert got_by_viewer(wishes, AnonymousUser()) == set()
