from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from hrcek.accounts.models import User
from hrcek.collections.errors import NOT_ON_THE_LIST
from hrcek.collections.forms import CollectionForm
from hrcek.collections.models import Collection
from hrcek.collections.services import (
    get_it,
    got_by_viewer,
    got_entry_ids,
    put_back,
    remove_entry,
    shared_entries,
    undo_got_it,
)
from hrcek.core.errors import HrcekError
from hrcek.core.htmx import is_htmx, vary_on_htmx
from hrcek.entries.models import Entry


@login_required
def collection_list(request: HttpRequest) -> HttpResponse:
    owner = cast("User", request.user)
    return render(
        request,
        "collections/list.html",
        {"collections": Collection.objects.filter(owner=owner)},
    )


@login_required
def collection_create(request: HttpRequest) -> HttpResponse:
    owner = cast("User", request.user)
    if request.method != "POST":
        return render(request, "collections/form.html", {"form": CollectionForm(owner)})

    form = CollectionForm(owner, request.POST)
    if not form.is_valid():
        return render(request, "collections/form.html", {"form": form})

    collection = form.save(commit=False)
    collection.owner = owner
    collection.save()
    # commit=False skips the many-to-many fields (visible_fields):
    # they need the row's pk, which only exists after save() above.
    form.save_m2m()
    messages.success(request, _("Collection made."))
    return redirect("collections:detail", pk=collection.pk)


@login_required
def collection_detail(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    collection = get_object_or_404(Collection, pk=pk, owner=owner)
    got = got_entry_ids(collection)
    reveal = collection.is_wish_list and request.GET.get("got") == "show"
    back = request.GET.get("back", "")
    return render(
        request,
        "collections/detail.html",
        {
            "collection": collection,
            "entries": collection.entries().prefetch_related("tags"),
            "reveal": reveal,
            # Only handed to the template when asked for, so a slip
            # there cannot spoil the surprise.
            "got": got if reveal else set(),
            # An item just brought back onto the list that somebody had
            # already got: the one thing said without being asked.
            "came_back": (
                collection.entries().filter(pk=int(back)).first()
                if back.isdecimal() and int(back) in got
                else None
            ),
        },
    )


@login_required
def collection_edit(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    collection = get_object_or_404(Collection, pk=pk, owner=owner)
    if request.method != "POST":
        return render(
            request,
            "collections/form.html",
            {
                "form": CollectionForm(owner, instance=collection),
                "collection": collection,
            },
        )

    form = CollectionForm(owner, request.POST, instance=collection)
    if not form.is_valid():
        return render(
            request,
            "collections/form.html",
            {"form": form, "collection": collection},
        )
    form.save()
    messages.success(request, _("Saved."))
    return redirect("collections:detail", pk=collection.pk)


@login_required
def collection_delete(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    collection = get_object_or_404(Collection, pk=pk, owner=owner)
    if request.method != "POST":
        return render(
            request, "collections/confirm_delete.html", {"collection": collection}
        )
    collection.delete()
    messages.success(request, _("Collection deleted. Its entries are untouched."))
    return redirect("collections:list")


@require_http_methods(["POST"])
@login_required
def collection_put_back(request: HttpRequest, pk: int, entry_pk: int) -> HttpResponse:
    """The owner clears a "Got it", whoever said it."""
    owner = cast("User", request.user)
    collection = get_object_or_404(Collection, pk=pk, owner=owner)
    put_back(collection, entry_pk)
    messages.success(request, _("Back on the list."))
    url = reverse("collections:detail", args=[collection.pk])
    # Back to the revealed view only when that is where the button
    # was; the reveal itself is never remembered.
    return redirect(f"{url}?got=show" if request.POST.get("reveal") else url)


@require_http_methods(["POST"])
@login_required
def collection_remove_entry(
    request: HttpRequest, pk: int, entry_pk: int
) -> HttpResponse:
    owner = cast("User", request.user)
    # Only a hand-picked collection has entries to take out — the same
    # rule as the entry's own "+ Collection" line
    # (entries.in_collections._hand_picked); anything else is a 404.
    collection = get_object_or_404(
        Collection, pk=pk, owner=owner, kind=Collection.MANUAL
    )
    entry = get_object_or_404(Entry, pk=entry_pk, owner=owner)
    remove_entry(collection, entry)
    if not is_htmx(request):
        return vary_on_htmx(redirect("collections:detail", pk=collection.pk))

    # The row itself goes by the form's own hx-swap="delete"; everything
    # this answer says lands out of band. See docs/dev/collections.md.
    response = render(
        request,
        "collections/_remove_result.html",
        {
            "status": _("“%(entry)s” taken out of “%(collection)s”.")
            % {"entry": entry.display_title, "collection": collection.name},
            "empty": not collection.entries().exists(),
        },
    )
    return vary_on_htmx(response)


def _unlisted(secret: str) -> Collection:
    """The secret is the whole of the access control, so a wrong one is
    a 404 like any other unknown address — and a collection that has
    stopped being unlisted stops answering here at once."""
    return get_object_or_404(Collection, secret=secret, visibility=Collection.UNLISTED)


def _public(namespace: str, slug: str) -> Collection:
    return get_object_or_404(
        Collection,
        owner__namespace__iexact=namespace,
        slug=slug,
        visibility=Collection.PUBLIC,
    )


def _shared_context(collection: Collection, request: HttpRequest) -> dict[str, object]:
    """What both shared pages need.

    `visible_fields` is a set of ids rather than objects, because the
    template asks the question once per field per entry.
    """
    viewer = cast("User | AnonymousUser", request.user)
    is_owner = viewer.pk == collection.owner_id  # ty: ignore[unresolved-attribute]
    entries = shared_entries(collection, viewer)
    wish_list = collection.is_wish_list
    return {
        "collection": collection,
        "feed_url": (
            reverse(
                "shared:public_feed",
                kwargs={
                    "namespace": collection.owner.namespace,
                    "slug": collection.slug,
                },
            )
            if collection.visibility == Collection.PUBLIC
            else reverse("shared:unlisted_feed", kwargs={"secret": collection.secret})
        ),
        "entries": entries.prefetch_related("tags", "field_values__definition"),
        "visible_field_ids": set(
            collection.visible_fields.values_list("pk", flat=True)
        ),
        # Only a signed-in visitor who is not the owner gets buttons:
        # the owner must not learn what is got by visiting the link.
        "can_get": wish_list and viewer.is_authenticated and not is_owner,
        "mine": got_by_viewer(collection, viewer) if wish_list else set(),
        "everything_got": (
            wish_list
            and not is_owner
            and collection.entries().exists()
            and not entries.exists()
        ),
    }


def unlisted_collection(request: HttpRequest, secret: str) -> HttpResponse:
    """A collection shared by link."""
    collection = _unlisted(secret)
    response = render(
        request, "collections/shared.html", _shared_context(collection, request)
    )
    # A search engine that learned the link would end the point of it.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def public_collection(request: HttpRequest, namespace: str, slug: str) -> HttpResponse:
    """A collection anybody may read, at an address anybody may guess."""
    collection = _public(namespace, slug)
    return render(
        request, "collections/shared.html", _shared_context(collection, request)
    )


def _got_it(
    request: HttpRequest, collection: Collection, entry_pk: int, *, undo: bool
) -> HttpResponse:
    """Say, or take back, "Got it" — then return to the shared page.

    A visitor who is not signed in never sees the buttons; one arrives
    here only from a page loaded before signing out. They are sent to
    sign in and back to the *page*: this address only answers POST, so
    returning here would fail.
    """
    page = collection.shared_url()
    if not request.user.is_authenticated:
        return redirect_to_login(page)
    user = cast("User", request.user)
    # Scoped to the list's owner and checked against the list by the
    # service, so an unknown id, a stranger's entry and one of the
    # owner's entries elsewhere all get the same answer.
    entry = Entry.objects.filter(pk=entry_pk, owner_id=collection.owner_id).first()  # ty: ignore[unresolved-attribute]
    try:
        if entry is None:
            raise HrcekError(NOT_ON_THE_LIST)
        if undo:
            undo_got_it(collection, entry, user)
            messages.success(request, _("Undone. It is back on the list."))
        else:
            get_it(collection, entry, user)
            messages.success(
                request, _("Got it. Nobody else will see it on the list now.")
            )
    except HrcekError as error:
        messages.error(request, str(error.error_code.message))
    return redirect(page)


@require_http_methods(["POST"])
def unlisted_got_it(
    request: HttpRequest, secret: str, entry_pk: int, *, undo: bool = False
) -> HttpResponse:
    return _got_it(request, _unlisted(secret), entry_pk, undo=undo)


@require_http_methods(["POST"])
def public_got_it(
    request: HttpRequest,
    namespace: str,
    slug: str,
    entry_pk: int,
    *,
    undo: bool = False,
) -> HttpResponse:
    return _got_it(request, _public(namespace, slug), entry_pk, undo=undo)
