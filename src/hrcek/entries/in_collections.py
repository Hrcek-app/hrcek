"""Adding an entry to a hand-picked collection, and taking it out, from
the entries list itself.

One view per action answers both a plain form post (redirect back, with
a message) and htmx (this entry's collections line, plus a status line).
The list only offers these with JavaScript; the entry's edit form is the
way without it. See docs/dev/entries.md and docs/dev/javascript.md.
"""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.collections.services import add_entry, remove_entry
from hrcek.core.htmx import is_htmx, vary_on_htmx
from hrcek.core.navigation import safe_next
from hrcek.entries.models import Entry
from hrcek.entries.views import _attach_in_collections, _say_if_already_got


@require_http_methods(["POST"])
@login_required
def collection_add(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    entry = get_object_or_404(Entry, pk=pk, owner=owner)
    collection = _hand_picked(request, owner)
    joining = not CollectionEntry.objects.filter(
        collection=collection, entry=entry
    ).exists()
    add_entry(collection, entry)
    if joining and collection.is_wish_list:
        # The same notice the entry form gives for the same change.
        _say_if_already_got(request, entry, {collection.pk})
    return _answer(
        request,
        entry,
        status=_("Added to “%(collection)s”.") % {"collection": collection.name},
        added=collection,
    )


@require_http_methods(["POST"])
@login_required
def collection_remove(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    entry = get_object_or_404(Entry, pk=pk, owner=owner)
    collection = _hand_picked(request, owner)
    remove_entry(collection, entry)
    return _answer(
        request,
        entry,
        status=_("Taken out of “%(collection)s”.") % {"collection": collection.name},
    )


def _hand_picked(request: HttpRequest, owner: User) -> Collection:
    """The posted collection, if it is one of the owner's hand-picked ones.

    Anything else — somebody else's, one that follows a label, one that
    does not exist, or no number at all — is the same 404, so a crafted
    post learns nothing about what exists.
    """
    posted = request.POST.get("collection", "")
    if not posted.isdecimal():
        raise Http404
    return get_object_or_404(
        Collection, pk=int(posted), owner=owner, kind=Collection.MANUAL
    )


def _answer(
    request: HttpRequest,
    entry: Entry,
    *,
    status: str,
    added: Collection | None = None,
) -> HttpResponse:
    """Redirect back with `status` as a message, or answer htmx with
    this entry's collections line and `status` in the status region.

    Focus, with htmx, goes to the line's "+ Collection" while there is
    still something to add; after adding the last one, to that one's
    own way back out, so it never falls to the top of the page.
    """
    target = safe_next(request, reverse("entries:list"))
    if not is_htmx(request):
        messages.success(request, status)
        return vary_on_htmx(redirect(target))

    _attach_in_collections(entry.owner, [entry])
    addable = entry.addable_collections  # ty: ignore[unresolved-attribute]
    response = render(
        request,
        "entries/_entry_collections.html",
        {
            "entry": entry,
            "status": status,
            "next": target,
            "focus_pill": bool(addable),
            "focus_remove": added.pk if added and not addable else None,
        },
    )
    return vary_on_htmx(response)
