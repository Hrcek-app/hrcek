from __future__ import annotations

from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotModified,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from hrcek.accounts.models import User
from hrcek.collections.services import (
    already_got_on,
    emptied_label_collections,
    label_wish_lists_holding,
)
from hrcek.core.navigation import safe_next
from hrcek.entries import imaging
from hrcek.entries.forms import EntryForm, FieldDefinitionForm
from hrcek.entries.models import Entry, EntryImage, FieldDefinition, FieldValue, Tag
from hrcek.entries.navigation import still_there
from hrcek.entries.services import save_entry


def _tag_ids(entries: list[Entry]) -> set[int]:
    return set(Tag.objects.filter(entries__in=entries).values_list("pk", flat=True))


def _save(
    request: HttpRequest, owner: User, form: EntryForm, editing: Entry | None = None
) -> Entry:
    """Save the entry form and its picture, then say what happened.

    "Saved." comes first, then any label collection the change emptied,
    then any label wish list it brought the entry back onto where it
    was already got. The labels carried before are those of the entry
    being edited and of whichever entry already holds the address,
    because saving under an address already held updates that one
    instead.
    """
    address = Entry.normalise_url(form.cleaned_data["url"])
    holder = Entry.objects.filter(owner=owner, url=address).first()
    carried = _tag_ids([e for e in (editing, holder) if e])
    # The entry that will be saved is the one holding the address; only
    # a wish list it *arrives* on is news.
    on_wish_lists = label_wish_lists_holding(holder) if holder else set()
    entry, _created = save_entry(
        owner,
        url=form.cleaned_data["url"],
        title=form.cleaned_data["title"],
        notes=form.cleaned_data["notes"],
        tag_names=form.tag_names(),
        fields=form.field_values(),
    )
    _apply_picture(entry, form)
    messages.success(request, _("Saved."))
    _say_if_emptied(request, owner, carried)
    _say_if_already_got(request, entry, label_wish_lists_holding(entry) - on_wish_lists)
    return entry


def _say_if_emptied(request: HttpRequest, owner: User, carried: set[int]) -> None:
    """Tell the owner which label collections this change left empty.

    The collection is kept: deleting it is the owner's call, so the
    notice links to its delete page rather than asking first, which
    would cost anything typed or chosen on the form.
    """
    for collection in emptied_label_collections(owner, carried):
        messages.info(
            request,
            format_html(
                '{} <a href="{}">{}</a>',
                _("“%(name)s” has nothing in it now. It stays until you delete it.")
                % {"name": collection.name},
                reverse("collections:delete", args=[collection.pk]),
                _("Delete it"),
            ),
        )


def _say_if_already_got(
    request: HttpRequest, entry: Entry, arrived_on: set[int]
) -> None:
    """Tell the owner that a wish list `entry` just joined had it got.

    Never who got it. The link opens the list with a button to put the
    item back on it.
    """
    for collection in already_got_on(entry, arrived_on):
        url = reverse("collections:detail", args=[collection.pk])
        messages.info(
            request,
            format_html(
                '{} <a href="{}?back={}">{}</a>',
                _("Somebody has already got this for “%(name)s”.")
                % {"name": collection.name},
                url,
                entry.pk,
                _("Put it back on the list?"),
            ),
        )


@login_required
def entry_list(request: HttpRequest) -> HttpResponse:
    owner = cast("User", request.user)
    entries = (
        Entry.objects.filter(owner=owner)
        .prefetch_related("tags", "field_values__definition")
        # The image is joined so the page does not ask once per entry,
        # but its blobs are left in the table: the list needs only to
        # know a picture exists, and pulling two pictures per row to
        # render an <img> tag would defeat the point of storing them
        # apart.
        .select_related("image")
        .defer("image__original", "image__display")
    )

    tag = request.GET.get("tag", "").strip()
    in_use = Tag.in_use(owner)
    if tag:
        # A label nothing carries has no page, whether it never existed
        # or is only kept because a collection follows it.
        if not in_use.filter(name__iexact=tag).exists():
            raise Http404
        entries = entries.filter(tags__name__iexact=tag)

    paginator = Paginator(entries, settings.ENTRIES_PER_PAGE)
    # get_page, not page: it copes with a missing, non-numeric or
    # out-of-range number instead of raising.
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "entries/list.html",
        {"page": page, "tag": tag, "tags": in_use},
    )


@login_required
def entry_create(request: HttpRequest) -> HttpResponse:
    owner = cast("User", request.user)
    if request.method != "POST":
        return render(request, "entries/form.html", {"form": EntryForm(owner)})

    form = EntryForm(owner, request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "entries/form.html", {"form": form})

    # A URL already held is an update, not a duplicate.
    _save(request, owner, form)
    return redirect("entries:list")


@login_required
def entry_edit(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    entry = get_object_or_404(Entry, pk=pk, owner=owner)

    if request.method != "POST":
        return render(
            request,
            "entries/form.html",
            {"form": EntryForm(owner, instance=entry), "entry": entry},
        )

    form = EntryForm(owner, request.POST, request.FILES, instance=entry)
    if not form.is_valid():
        return render(request, "entries/form.html", {"form": form, "entry": entry})

    _save(request, owner, form, editing=entry)
    return redirect("entries:list")


@login_required
def entry_delete(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    entry = get_object_or_404(Entry, pk=pk, owner=owner)
    default = reverse("entries:list")

    if request.method != "POST":
        return render(
            request,
            "entries/confirm_delete.html",
            {"entry": entry, "next": safe_next(request, default)},
        )

    carried = _tag_ids([entry])
    entry.delete()
    # Deleting the entry can leave tags with nothing on them.
    Tag.prune_orphans(owner)
    messages.success(request, _("Deleted."))
    _say_if_emptied(request, owner, carried)
    return redirect(still_there(safe_next(request, default), owner))


@login_required
def field_list(request: HttpRequest) -> HttpResponse:
    owner = cast("User", request.user)
    if request.method == "POST":
        form = FieldDefinitionForm(owner, request.POST)
        if form.is_valid():
            definition = form.save(commit=False)
            definition.owner = owner
            definition.save()
            messages.success(request, _("Field added."))
            return redirect("entries:fields")
    else:
        form = FieldDefinitionForm(owner)

    return render(
        request,
        "entries/fields.html",
        {"form": form, "fields": FieldDefinition.objects.filter(owner=owner)},
    )


@login_required
def field_edit(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    definition = get_object_or_404(FieldDefinition, pk=pk, owner=owner)

    if request.method == "POST":
        form = FieldDefinitionForm(owner, request.POST, instance=definition)
        if form.is_valid():
            form.save()
            messages.success(request, _("Field renamed."))
            return redirect("entries:fields")
    else:
        form = FieldDefinitionForm(owner, instance=definition)

    return render(
        request,
        "entries/field_form.html",
        {"form": form, "definition": definition},
    )


@login_required
def field_delete(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    definition = get_object_or_404(FieldDefinition, pk=pk, owner=owner)

    if request.method != "POST":
        return render(
            request,
            "entries/field_confirm_delete.html",
            {
                "definition": definition,
                # The count is what makes the consequence real to
                # somebody about to press the button.
                "value_count": FieldValue.objects.filter(definition=definition).count(),
            },
        )

    definition.delete()
    messages.success(request, _("Field deleted."))
    return redirect("entries:fields")


def _apply_picture(entry: Entry, form: EntryForm) -> None:
    """Attach, replace or remove the entry's picture.

    Saying nothing about the picture leaves it alone, so editing a
    title cannot quietly drop one.
    """
    if form.cleaned_data.get("remove_image"):
        EntryImage.objects.filter(entry=entry).delete()
        return
    if form.picture is not None:
        EntryImage.attach(entry, form.picture, source_url=form.picture_source)


def entry_image(request: HttpRequest, pk: int) -> HttpResponse:
    """The picture for one entry.

    Readable by its owner, and by anybody at all once the entry sits in
    a collection that is shared and shows pictures. That is what
    publishing a picture means: the address works on its own, not only
    inside the page that shows it. Take the sharing away and the next
    request is refused again — the question is asked per request, and
    nothing public is cached in between.

    Served by Django rather than off the web server's disk, because an
    unguessable filename is not access control. Somebody else's private
    entry is a 404, never a 403, which would confirm that it exists.
    """
    image = get_object_or_404(EntryImage, entry__pk=pk)
    public = image.entry.is_publicly_visible()
    if not public:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if image.entry.owner_id != request.user.pk:
            raise Http404

    # AVIF is small but not universal; anything that does not ask for it
    # gets WebP, rendered from the archived original on first request.
    accept = request.headers.get("accept", "")
    fmt = imaging.DISPLAY_FORMAT if "image/avif" in accept else imaging.FALLBACK_FORMAT

    etag = f'"{image.checksum}-{fmt}"'
    if request.headers.get("if-none-match") == etag:
        return HttpResponseNotModified()

    # Sent whole rather than streamed: a display copy is a couple of
    # hundred kilobytes, and a streaming response holds an open file
    # descriptor until somebody consumes it.
    response = HttpResponse(
        image.rendition(fmt),
        content_type=imaging.CONTENT_TYPES[fmt],
    )
    response.headers["ETag"] = etag
    response.headers["Vary"] = "Accept"
    # A private picture must never sit in a shared cache; a public one
    # may, briefly, so a page of them is not re-fetched on every scroll.
    response.headers["Cache-Control"] = (
        "public, max-age=300" if public else "private, max-age=0, must-revalidate"
    )
    return response
