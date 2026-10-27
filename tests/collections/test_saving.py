"""Saving somebody else's collection, below the pages."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, SavedCollection
from hrcek.collections.services import (
    is_saved,
    save_collection,
    saved_collections,
    unfollow,
)
from hrcek.core.errors import HrcekError

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
def bor():
    return _person("bor@example.com")


@pytest.fixture
def ana():
    return _person("ana@example.com")


def _collection(owner, visibility=Collection.UNLISTED, name="Birthday"):
    return Collection.objects.create(owner=owner, name=name, visibility=visibility)


def _listed(user):
    return [saved.collection for saved in saved_collections(user)]


def test_saving_a_link_shared_collection_lists_it(nina, bor):
    birthday = _collection(nina)
    save_collection(birthday, bor, via_secret=True)
    assert _listed(bor) == [birthday]


def test_owner_cannot_save_own_collection(nina):
    birthday = _collection(nina)
    with pytest.raises(HrcekError) as raised:
        save_collection(birthday, nina, via_secret=True)
    assert raised.value.error_code.code == "HRC-COLL-0008"
    assert not SavedCollection.objects.exists()


def test_saving_twice_keeps_one_row(nina, bor):
    birthday = _collection(nina)
    save_collection(birthday, bor, via_secret=True)
    save_collection(birthday, bor, via_secret=True)
    assert SavedCollection.objects.filter(user=bor).count() == 1


def test_saving_from_secret_upgrades_a_public_save(nina, bor):
    birthday = _collection(nina, Collection.PUBLIC)
    save_collection(birthday, bor, via_secret=False)
    save_collection(birthday, bor, via_secret=True)
    assert SavedCollection.objects.get(user=bor).via_secret is True


def test_saving_from_public_never_downgrades(nina, bor):
    birthday = _collection(nina, Collection.PUBLIC)
    save_collection(birthday, bor, via_secret=True)
    save_collection(birthday, bor, via_secret=False)
    assert SavedCollection.objects.get(user=bor).via_secret is True


def test_public_save_hidden_once_link_only(nina, bor):
    """Finding it while it was public is no claim on its secret link."""
    birthday = _collection(nina, Collection.PUBLIC)
    save_collection(birthday, bor, via_secret=False)
    birthday.visibility = Collection.UNLISTED
    birthday.save()
    assert _listed(bor) == []
    assert is_saved(birthday, bor) is False


@pytest.mark.parametrize("visibility", [Collection.PUBLIC, Collection.UNLISTED])
def test_secret_save_listed_when_public_or_unlisted(nina, bor, visibility):
    birthday = _collection(nina)
    save_collection(birthday, bor, via_secret=True)
    birthday.visibility = visibility
    birthday.save()
    assert _listed(bor) == [birthday]
    assert is_saved(birthday, bor) is True


def test_private_hides_and_resharing_restores(nina, bor):
    birthday = _collection(nina)
    save_collection(birthday, bor, via_secret=True)
    birthday.visibility = Collection.PRIVATE
    birthday.save()
    assert _listed(bor) == []
    birthday.visibility = Collection.UNLISTED
    birthday.save()
    assert _listed(bor) == [birthday]


def test_deleting_collection_removes_save(nina, bor):
    birthday = _collection(nina)
    save_collection(birthday, bor, via_secret=True)
    birthday.delete()
    assert SavedCollection.objects.count() == 0


def test_unfollow_removes_only_own_save(nina, bor, ana):
    birthday = _collection(nina)
    save_collection(birthday, bor, via_secret=True)
    save_collection(birthday, ana, via_secret=True)
    unfollow(birthday.pk, bor)
    assert list(SavedCollection.objects.values_list("user", flat=True)) == [ana.pk]


def test_unfollow_without_save_is_harmless(nina, bor):
    birthday = _collection(nina)
    unfollow(birthday.pk, bor)
    assert not SavedCollection.objects.exists()


def test_saved_list_newest_first(nina, bor):
    birthday = _collection(nina)
    garden = _collection(nina, name="Garden")
    save_collection(birthday, bor, via_secret=True)
    save_collection(garden, bor, via_secret=True)
    assert _listed(bor) == [garden, birthday]


def test_is_saved_false_for_anonymous(nina):
    assert is_saved(_collection(nina), AnonymousUser()) is False
