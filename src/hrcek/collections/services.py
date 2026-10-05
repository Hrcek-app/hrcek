"""The one place membership changes, so ownership is checked once."""

from __future__ import annotations

from hrcek.accounts.models import User
from hrcek.collections.errors import NOT_A_MANUAL_COLLECTION, NOT_YOURS
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.core.errors import HrcekError
from hrcek.entries.models import Entry


def add_entry(collection: Collection, entry: Entry) -> CollectionEntry:
    """Put `entry` in `collection`, if it may go there.

    Adding the same entry twice is deliberately harmless: the page
    offers each entry once, but a double submission should not be an
    error worth showing anybody.
    """
    _check(collection, entry)
    membership, _created = CollectionEntry.objects.get_or_create(
        collection=collection, entry=entry
    )
    return membership


def remove_entry(collection: Collection, entry: Entry) -> None:
    """Take `entry` out. Doing so twice is not an error either."""
    CollectionEntry.objects.filter(collection=collection, entry=entry).delete()


def _check(collection: Collection, entry: Entry) -> None:
    if collection.kind != Collection.MANUAL:
        raise HrcekError(NOT_A_MANUAL_COLLECTION)
    # owner_id rather than owner: no query, and the comparison is
    # the same. ty does not run the django-stubs plugin, so it
    # cannot see the implicit attribute.
    if entry.owner_id != collection.owner_id:  # ty: ignore[unresolved-attribute]
        # 404 rather than 403, as everywhere else here: a 403 would
        # confirm that somebody else's entry exists.
        raise HrcekError(NOT_YOURS)


def emptied_label_collections(owner: User, tag_ids: set[int]) -> list[Collection]:
    """Label collections following one of `tag_ids` that now hold nothing.

    The caller passes the labels an entry carried before a change, so a
    collection that was already empty is not mentioned again.
    """
    return list(
        Collection.objects.filter(
            owner=owner,
            kind=Collection.BY_LABEL,
            label_id__in=tag_ids,
            label__entries__isnull=True,
        )
    )
