"""Adding and removing an entry's labels from the list itself.

One view per action answers both a plain form post (redirect back, with
a message) and htmx (just this entry's labels, plus a status line). See
docs/dev/javascript.md.
"""

from __future__ import annotations

from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from hrcek.accounts.models import User
from hrcek.collections.services import label_wish_lists_holding
from hrcek.core.htmx import htmx_redirect, is_htmx, vary_on_htmx
from hrcek.core.navigation import safe_next
from hrcek.entries.models import Entry, Tag
from hrcek.entries.navigation import still_there
from hrcek.entries.views import (
    _say_if_already_got,
    _say_if_emptied,
    _tag_from,
    _tag_ids,
)


class LabelForm(forms.Form):
    """One label, or several separated by commas, as the edit form takes them."""

    name = forms.CharField(
        strip=True,
        required=False,
        # Several labels may be typed at once, so the limit is checked
        # per label in clean_name rather than on the whole input.
    )

    def clean_name(self) -> list[str]:
        names = Tag.parse_names(self.cleaned_data["name"])
        if not names:
            raise forms.ValidationError(_("Type a label to add."), code="required")
        for name in names:
            if len(name) > Tag.NAME_MAX_LENGTH:
                raise forms.ValidationError(
                    _(
                        "A label can be at most %(limit)d characters long; "
                        "that one has %(length)d."
                    ),
                    code="max_length",
                    params={"limit": Tag.NAME_MAX_LENGTH, "length": len(name)},
                )
        return names


@login_required
def label_add(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    entry = get_object_or_404(Entry, pk=pk, owner=request.user)
    form = LabelForm(request.POST)
    if not form.is_valid():
        error = str(form.errors["name"][0])
        return _answer(
            request,
            entry,
            status=error,
            code=422,
            # Open, with the error beside the input and the text as
            # typed, to be corrected.
            fragment={
                "label_error": error,
                "label_value": request.POST.get("name", ""),
                "label_open": True,
            },
        )

    on_wish_lists = label_wish_lists_holding(entry)
    before = {t.pk for t in entry.tags.all()}
    before_in_use = _in_use_ids(entry.owner)
    current = [t.name for t in entry.tags.all()]
    typed = {n.lower() for n in form.cleaned_data["name"]}
    # parse_names keeps the first spelling it sees, so a label the entry
    # already has, typed in other capitals, changes nothing.
    names = Tag.parse_names(", ".join([*current, *form.cleaned_data["name"]]))
    Tag.set_for(entry, names)
    _say_if_already_got(request, entry, label_wish_lists_holding(entry) - on_wish_lists)
    # Still open, focus in the emptied input, so the next label can be
    # typed straight away.
    return _answer(
        request,
        entry,
        status=_added(
            [t.name for t in entry.tags.all() if t.pk not in before],
            already=[n for n in current if n.lower() in typed],
        ),
        fragment={
            "label_open": True,
            **_sidebar_refresh(request, entry.owner, before_in_use),
        },
    )


@login_required
def label_remove(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    entry = get_object_or_404(Entry, pk=pk, owner=request.user)
    owner = cast("User", request.user)
    name = request.POST.get("name", "").strip()
    carried = _tag_ids([entry])
    before_in_use = _in_use_ids(owner)
    current = [t.name for t in entry.tags.all()]
    # Named as the entry showed it, whatever capitals were posted.
    shown = next((n for n in current if n.lower() == name.lower()), name)
    Tag.set_for(entry, [n for n in current if n.lower() != name.lower()])
    _say_if_emptied(request, owner, carried)
    # The chip and its button are gone; focus goes to the entry's own
    # "+ Label" rather than falling to the top of the page.
    return _answer(
        request,
        entry,
        status=_("Label “%(name)s” removed.") % {"name": shown},
        fragment={
            "label_removed": True,
            **_sidebar_refresh(request, owner, before_in_use),
        },
    )


def _added(added: list[str], *, already: list[str]) -> str:
    """What adding did, naming the labels.

    Named so that one result read out after another is not the same
    sentence twice, and so the message means something on its own.
    """
    if added:
        return ngettext(
            "Label %(names)s added.", "Labels %(names)s added.", len(added)
        ) % {"names": _quoted(added)}
    return ngettext(
        "This entry already has the label %(names)s.",
        "This entry already has the labels %(names)s.",
        len(already),
    ) % {"names": _quoted(already)}


def _quoted(names: list[str]) -> str:
    return ", ".join(_("“%(name)s”") % {"name": name} for name in names)


def _in_use_ids(owner: User) -> set[int]:
    return set(Tag.in_use(owner).values_list("pk", flat=True))


def _sidebar_refresh(
    request: HttpRequest, owner: User, before: set[int]
) -> dict[str, object]:
    """Extra `_answer` fragment context when this change altered what
    the "Labels" sidebar offers.

    Adding a label nobody had yet, or removing the last one holding a
    label, changes `Tag.in_use(owner)` — compared before and after the
    change, same question `entry_delete` asks of a pruned label.
    Without this, the sidebar rendered on page load would go on
    showing a label that is now gone, or not yet show one just typed,
    until the next full page load.
    """
    after = _in_use_ids(owner)
    if after == before:
        return {}
    return {
        "refresh_tags": True,
        "tags": Tag.in_use(owner),
        "tag": _tag_from(safe_next(request, reverse("entries:list"))),
    }


def _answer(
    request: HttpRequest,
    entry: Entry,
    *,
    status: str,
    fragment: dict[str, object],
    code: int = 200,
) -> HttpResponse:
    """Redirect back with `status` as a message, or answer htmx with
    this entry's labels and `status` in the status region.

    When `next` names the filtered list this change pruned the label
    out from under — removing the only entry it carried, say — there
    is no sensible fragment to answer with: the page the owner is
    looking at has nothing left to be about. Answered with
    `htmx_redirect`, a real navigation to `still_there`'s plain-list
    answer, with `status` queued as a message for the page it lands on,
    exactly as `entry_delete` does for the same situation
    (`views.py`); only `label_remove` can cause this (adding never
    prunes anything), but the check costs nothing to run for both.
    """
    default = reverse("entries:list")
    target = safe_next(request, default)
    back = still_there(target, entry.owner)
    if not is_htmx(request):
        (messages.error if "label_error" in fragment else messages.success)(
            request, status
        )
        return redirect(back)

    if back != target:
        # The navigation replaces the page `status` would have been
        # written to; the page it lands on shows it as a message.
        messages.success(request, status)
        return vary_on_htmx(htmx_redirect(back))

    response = render(
        request,
        "entries/_entry_labels.html",
        {"entry": entry, "status": status, "next": back, **fragment},
        status=code,
    )
    return vary_on_htmx(response)
