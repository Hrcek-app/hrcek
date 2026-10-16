"""The pages for editing a choice field's options.

Every button of the editor submits the whole form, so nothing typed is
lost on the way. Only Save writes anything; the other buttons answer
with the edit page drawn again around the changed list. With JavaScript
the same buttons act in place instead (js/options-editor.js) and only
Save reaches the server. See docs/dev/entries.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from hrcek.accounts.models import User
from hrcek.entries.choice_options import (
    OptionRow,
    StaleOptionsError,
    apply_op,
    merge_stale,
    plan_options,
    save_options,
    usage,
)
from hrcek.entries.forms import FieldDefinitionForm
from hrcek.entries.models import FieldDefinition


def editor_context(
    definition: FieldDefinition,
    rows: list[OptionRow] | None = None,
    *,
    known_json: str | None = None,
    new_option: str = "",
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """What the options editor needs, as stored or as last submitted."""
    saved = [OptionRow(option, option) for option in definition.options]
    rows = saved if rows is None else rows
    counts = usage(definition)
    return {
        "rows": [
            {
                "index": index,
                "text": row.text,
                "original": row.original,
                # A row added since the editor opened holds nothing yet.
                "used": counts.get(row.original, 0) if row.original else None,
            }
            for index, row in enumerate(rows)
        ],
        "known_json": (
            json.dumps(definition.options) if known_json is None else known_json
        ),
        "new_option": new_option,
        "option_errors": errors or [],
        # A list that differs from what is stored was typed and not yet
        # saved; unsaved.js asks before it is left behind.
        "dirty": rows != saved or bool(new_option.strip()),
    }


def _edit_page(
    request: HttpRequest,
    definition: FieldDefinition,
    form: FieldDefinitionForm,
    **editor: Any,
) -> HttpResponse:
    return render(
        request,
        "entries/field_form.html",
        {
            "form": form,
            "definition": definition,
            **editor_context(definition, **editor),
        },
    )


@dataclass
class _Submitted:
    """What the editor posted: its rows, the hidden known list, the box."""

    rows: list[OptionRow]
    known_json: str
    new_option: str


def _submitted(request: HttpRequest) -> _Submitted:
    texts = request.POST.getlist("option")
    originals = request.POST.getlist("original")
    # Paired by position. Fewer originals than rows only comes from a
    # hand-made request; the extra rows are then simply new.
    rows = [
        OptionRow(text, originals[index] if index < len(originals) else "")
        for index, text in enumerate(texts)
    ]
    return _Submitted(
        rows, request.POST.get("known", ""), request.POST.get("new_option", "")
    )


def _known(raw: str) -> list[str] | None:
    try:
        known = json.loads(raw)
    except ValueError:
        return None
    if isinstance(known, list) and all(isinstance(each, str) for each in known):
        return known
    return None


@login_required
@require_http_methods(["GET", "POST"])
def field_options(request: HttpRequest, pk: int) -> HttpResponse:
    owner = cast("User", request.user)
    definition = get_object_or_404(
        FieldDefinition, pk=pk, owner=owner, kind=FieldDefinition.CHOICE
    )
    if request.method != "POST":
        return redirect("entries:field_edit", pk=definition.pk)

    # The name is in the same form, so it rides along on every round
    # trip too, and is saved together with the options.
    form = FieldDefinitionForm(owner, request.POST, instance=definition)
    submitted = _submitted(request)
    op = request.POST.get("op", "")
    if op == "save":
        return _save(request, definition, form, submitted)
    rows, new_option = submitted.rows, submitted.new_option
    if op != "back":
        rows = apply_op(rows, op, new_option)
        if op == "add":
            new_option = ""
    return _edit_page(
        request,
        definition,
        form,
        rows=rows,
        known_json=submitted.known_json,
        new_option=new_option,
    )


def _save(
    request: HttpRequest,
    definition: FieldDefinition,
    form: FieldDefinitionForm,
    submitted: _Submitted,
) -> HttpResponse:
    # Text still in the "new option" box is meant to be kept: without
    # JavaScript, Enter in that box saves rather than adds.
    rows = apply_op(submitted.rows, "add", submitted.new_option)
    known_json = submitted.known_json
    known = _known(known_json)
    # Read before the name form is checked: checking it copies the typed
    # name onto the definition.
    current = list(definition.options)
    option_errors: list[str] = []
    plan = None
    try:
        if known is None:
            raise StaleOptionsError
        plan = plan_options(definition, rows, known)
    except StaleOptionsError:
        # Nothing typed is thrown away: the rows are kept on top of the
        # list as it now stands, to look over and save again.
        rows = merge_stale(rows, known, current)
        known_json = json.dumps(current)
        option_errors = [
            _(
                "These options were changed somewhere else, perhaps in another "
                "tab. Your changes are kept and the others added; please check "
                "the list and save again."
            )
        ]
    except ValidationError as error:
        option_errors = error.messages

    if not form.is_valid() or plan is None:
        return _edit_page(
            request,
            definition,
            form,
            rows=rows,
            known_json=known_json,
            errors=option_errors,
        )

    if plan.affected and request.POST.get("confirmed") != "1":
        return render(
            request,
            "entries/field_confirm_options.html",
            {
                "definition": definition,
                "name": form.cleaned_data["name"],
                "affected": plan.affected,
                "total": sum(plan.affected.values()),
                **editor_context(definition, rows, known_json=known_json),
            },
        )

    with transaction.atomic():
        save_options(definition, plan)
        form.save()
    messages.success(request, _("Field saved."))
    return redirect("entries:field_edit", pk=definition.pk)
