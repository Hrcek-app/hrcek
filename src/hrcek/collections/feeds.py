"""Atom feeds, one per collection page.

Django's syndication framework writes the XML; nothing here invents a
feed format. The three classes differ only in how they find their
collection, which is also how each enforces its visibility — so a feed
can never be reachable where its page is not.
"""

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import AnonymousUser
from django.contrib.syndication.views import Feed
from django.db.models import QuerySet
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.feedgenerator import Atom1Feed

from hrcek.accounts.models import User
from hrcek.collections.models import Collection
from hrcek.collections.services import shared_entries
from hrcek.entries.models import Entry


class BaseCollectionFeed(Feed):
    """What every collection feed has in common.

    Django builds one instance per request, so keeping the collection
    on `self` is safe — `get_object` runs before anything reads it.
    """

    feed_type = Atom1Feed
    # Set by each subclass's get_object, which Django calls first.
    _collection: Collection

    def title(self, obj: Collection) -> str:
        return obj.name

    def description(self, obj: Collection) -> str:
        return obj.description

    def subtitle(self, obj: Collection) -> str:
        # Atom calls it a subtitle; the description above is what RSS
        # readers would want, and Django asks for both by name.
        return obj.description

    def items(self, obj: Collection) -> list[Entry]:
        return list(self.listed(obj)[:50])

    def listed(self, obj: Collection) -> QuerySet[Entry]:
        # The same function the page uses, so the two cannot drift apart
        # in what they hold or the order they hold it in. A feed reader
        # is nobody in particular, so a shared feed lists what an
        # anonymous visitor would see.
        return shared_entries(obj, AnonymousUser())

    def item_title(self, item: Entry) -> str:
        return item.display_title

    def item_link(self, item: Entry) -> str:
        return item.url

    def item_description(self, item: Entry) -> str:
        # Notes only where the collection shows them. A feed that
        # carried what its page hides would be a back door.
        return item.notes if self._collection.show_notes else ""


class PrivateCollectionFeed(BaseCollectionFeed):
    """The owner's own feed for a collection at any visibility."""

    def listed(self, obj: Collection) -> QuerySet[Entry]:
        # The owner's own feed: everything, got or not.
        return obj.entries()

    def get_object(self, request: HttpRequest, pk: int) -> Collection:
        if not request.user.is_authenticated:
            raise Http404
        self._collection = get_object_or_404(
            Collection, pk=pk, owner=cast("User", request.user)
        )
        return self._collection

    def link(self, obj: Collection) -> str:
        return f"/collections/{obj.pk}/"


class UnlistedCollectionFeed(BaseCollectionFeed):
    def get_object(self, request: HttpRequest, secret: str) -> Collection:
        self._collection = get_object_or_404(
            Collection, secret=secret, visibility=Collection.UNLISTED
        )
        return self._collection

    def link(self, obj: Collection) -> str:
        return obj.unlisted_url()


class PublicCollectionFeed(BaseCollectionFeed):
    def get_object(self, request: HttpRequest, namespace: str, slug: str) -> Collection:
        self._collection = get_object_or_404(
            Collection,
            owner__namespace__iexact=namespace,
            slug=slug,
            visibility=Collection.PUBLIC,
        )
        return self._collection

    def link(self, obj: Collection) -> str:
        return obj.public_url()
