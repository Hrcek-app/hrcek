"""The one place membership changes, so ownership is checked once."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q, QuerySet

from hrcek.accounts.models import User
from hrcek.collections.errors import (
    ALREADY_GOT,
    NOT_A_MANUAL_COLLECTION,
    NOT_A_WISH_LIST,
    NOT_ON_THE_LIST,
    NOT_YOURS,
    NOT_YOURS_TO_UNDO,
    OWN_COLLECTION,
    OWN_WISH_LIST,
)
from hrcek.collections.models import (
    Collection,
    CollectionEntry,
    GotIt,
    SavedCollection,
)
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


def got_entry_ids(collection: Collection) -> set[int]:
    """The ids of items on the list right now that somebody has got.

    Starting from `entries()` is what makes marks on departed items
    inert. Empty for a collection that is not a wish list, so switching
    the flag off suspends every mark without touching one.
    """
    if not collection.is_wish_list:
        return set()
    return set(
        GotIt.objects.filter(
            collection=collection, entry__in=collection.entries().values("pk")
        ).values_list("entry_id", flat=True)
    )


def got_by_viewer(collection: Collection, viewer: User | AnonymousUser) -> set[int]:
    """The items on this list that `viewer` said "Got it" for."""
    if not viewer.is_authenticated:
        return set()
    return set(
        GotIt.objects.filter(collection=collection, got_by=viewer).values_list(
            "entry_id", flat=True
        )
    )


def shared_entries(
    collection: Collection, viewer: User | AnonymousUser
) -> QuerySet[Entry]:
    """What a shared page or feed lists for `viewer`.

    Everybody sees everything on an ordinary collection. On a wish list
    the owner still does — that is the surprise — and a giver keeps
    seeing what they got, so they can undo it; everybody else loses
    whatever has been got.
    """
    entries = collection.entries()
    if not collection.is_wish_list or viewer.pk == collection.owner_id:  # ty: ignore[unresolved-attribute]
        return entries
    hidden = GotIt.objects.filter(collection=collection)
    if viewer.is_authenticated:
        hidden = hidden.exclude(got_by=viewer)
    return entries.exclude(pk__in=hidden.values("entry_id"))


def get_it(collection: Collection, entry: Entry, user: User) -> GotIt:
    """Record that `user` got `entry` for this list's owner.

    Saying it twice is harmless, as with `add_entry`.
    """
    if not (collection.is_wish_list and collection.is_shared()):
        raise HrcekError(NOT_A_WISH_LIST)
    if user.pk == collection.owner_id:  # ty: ignore[unresolved-attribute]
        raise HrcekError(OWN_WISH_LIST)
    if not collection.entries().filter(pk=entry.pk).exists():
        raise HrcekError(NOT_ON_THE_LIST)
    got, _created = GotIt.objects.get_or_create(
        collection=collection, entry=entry, defaults={"got_by": user}
    )
    if got.got_by_id != user.pk:  # ty: ignore[unresolved-attribute]
        raise HrcekError(ALREADY_GOT)
    return got


def undo_got_it(collection: Collection, entry: Entry, user: User) -> None:
    """Take back a "Got it". Taking back nothing is not an error.

    The owner is refused before anything is looked up: otherwise the
    two different answers would tell them whether the item was got.
    """
    if user.pk == collection.owner_id:  # ty: ignore[unresolved-attribute]
        raise HrcekError(OWN_WISH_LIST)
    got = GotIt.objects.filter(collection=collection, entry=entry).first()
    if got is None:
        return
    if got.got_by_id != user.pk:  # ty: ignore[unresolved-attribute]
        raise HrcekError(NOT_YOURS_TO_UNDO)
    got.delete()


def put_back(collection: Collection, entry_pk: int) -> None:
    """The owner clears a mark, whoever made it.

    Ownership is the caller's check: it already fetched the collection
    scoped to the signed-in owner.
    """
    GotIt.objects.filter(collection=collection, entry_id=entry_pk).delete()


def label_wish_lists_holding(entry: Entry) -> set[int]:
    """The owner's label wish lists that `entry` is in right now."""
    return set(
        Collection.objects.filter(
            owner_id=entry.owner_id,  # ty: ignore[unresolved-attribute]
            kind=Collection.BY_LABEL,
            is_wish_list=True,
            label__in=entry.tags.all(),
        ).values_list("pk", flat=True)
    )


def already_got_on(entry: Entry, collection_ids: set[int]) -> list[Collection]:
    """Those of `collection_ids` where `entry` is already got."""
    return list(Collection.objects.filter(pk__in=collection_ids, got_its__entry=entry))


def save_collection(
    collection: Collection, user: User, *, via_secret: bool
) -> SavedCollection:
    """Keep somebody else's collection in `user`'s saved list.

    Saving twice is harmless. A save made with the secret link upgrades
    one made at the public address, and nothing downgrades it: the link
    was given to them once, and that does not change.
    """
    if user.pk == collection.owner_id:  # ty: ignore[unresolved-attribute]
        raise HrcekError(OWN_COLLECTION)
    saved, created = SavedCollection.objects.get_or_create(
        user=user, collection=collection, defaults={"via_secret": via_secret}
    )
    if not created and via_secret and not saved.via_secret:
        saved.via_secret = True
        saved.save(update_fields=["via_secret"])
    return saved


def unfollow(collection_id: int, user: User) -> None:
    """Drop the collection from `user`'s saved list. Dropping nothing is
    not an error, and the answer is the same either way."""
    SavedCollection.objects.filter(user=user, collection_id=collection_id).delete()


def saved_collections(user: User) -> QuerySet[SavedCollection]:
    """The saves `user` may still follow, newest first.

    A public collection is open to anyone. A link-only one is listed
    only for those who saved it with the link: having found it while it
    was public is no claim on its secret address. A private one is
    nobody's but the owner's. Saves are kept through all of this, so
    sharing again brings them back.
    """
    return (
        SavedCollection.objects.filter(user=user)
        .filter(
            Q(collection__visibility=Collection.PUBLIC)
            | Q(collection__visibility=Collection.UNLISTED, via_secret=True)
        )
        .select_related("collection__owner")
        .order_by("-saved_at", "-pk")
    )


def is_saved(collection: Collection, user: User | AnonymousUser) -> bool:
    """Whether the collection is in `user`'s saved list right now."""
    if not user.is_authenticated:
        return False
    return saved_collections(user).filter(collection=collection).exists()
