"""Editing the options of a choice field.

The editor's state is a list of rows. Each row holds the text as it now
stands and the text it had when the editor was opened, its *original*,
empty for a row added since. Values are stored as the option's text, so
the original is what lets a changed row be a rename that carries its
values along, rather than a removal and an unrelated addition.

Nothing here touches the database until `save_options`. See
docs/dev/entries.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Count, F, TextField, Value, When
from django.utils.translation import gettext_lazy as _

from hrcek.entries.models import FieldDefinition, FieldValue

MAX_LENGTH = 100


@dataclass(frozen=True)
class OptionRow:
    text: str
    original: str = ""


@dataclass(frozen=True)
class OptionsPlan:
    options: list[str]
    renames: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    # Only the removed options some entry still holds, with how many.
    affected: dict[str, int] = field(default_factory=dict)


class StaleOptionsError(Exception):
    """The options changed somewhere else since the editor was opened."""


def apply_op(rows: list[OptionRow], op: str, new_text: str) -> list[OptionRow]:
    """Apply one of the editor's command buttons to *rows*.

    An op that makes no sense — an index out of range, the first row
    moved up — returns the rows unchanged rather than failing: it can
    only come from a stale or hand-made request.
    """
    rows = list(rows)
    if op == "add":
        text = new_text.strip()
        return [*rows, OptionRow(text)] if text else rows

    action, _sep, position = op.partition(":")
    try:
        index = int(position)
    except ValueError:
        return rows
    if not 0 <= index < len(rows):
        return rows

    if action == "remove":
        del rows[index]
    elif action == "up" and index > 0:
        rows[index - 1], rows[index] = rows[index], rows[index - 1]
    elif action == "down" and index < len(rows) - 1:
        rows[index], rows[index + 1] = rows[index + 1], rows[index]
    return rows


def merge_stale(
    rows: list[OptionRow], known: list[str] | None, current: list[str]
) -> list[OptionRow]:
    """Keep what was typed, on top of options changed somewhere else.

    A row whose original has gone elsewhere becomes a new row, so its
    text is kept but carries no values along. An option that arrived
    elsewhere (not among *known*, and not on any row) is brought in at
    the end. One this editor removed stays removed.
    """
    present = set(current)
    kept = [
        row if not row.original or row.original in present else OptionRow(row.text)
        for row in rows
    ]
    on_rows = {row.original for row in kept if row.original}
    seen = set(known or [])
    arrived = [
        OptionRow(option, option)
        for option in current
        if option not in on_rows and option not in seen
    ]
    return kept + arrived


def usage(definition: FieldDefinition) -> dict[str, int]:
    """How many entries hold each stored value of *definition*."""
    counted = (
        FieldValue.objects.filter(definition=definition)
        .values("value_text")
        .annotate(n=Count("id"))
    )
    return {row["value_text"]: row["n"] for row in counted}


def plan_options(
    definition: FieldDefinition, rows: list[OptionRow], known: list[str]
) -> OptionsPlan:
    """Check *rows* and work out what saving them would change.

    *known* is the list of options the editor was opened with. If the
    field no longer has exactly those, somebody changed it elsewhere,
    and saving would undo their change without either of them knowing.
    """
    if list(definition.options) != list(known):
        raise StaleOptionsError

    kept = [OptionRow(row.text.strip(), row.original) for row in rows]
    kept = [row for row in kept if row.text]

    seen: set[str] = set()
    for row in kept:
        if len(row.text) > MAX_LENGTH:
            raise ValidationError(
                _("“%(option)s” is longer than %(limit)d characters."),
                code="too_long",
                params={"option": row.text[:20] + "…", "limit": MAX_LENGTH},
            )
        if row.text.casefold() in seen:
            raise ValidationError(
                _("“%(option)s” is in the list twice."),
                code="duplicate",
                params={"option": row.text},
            )
        seen.add(row.text.casefold())
    if not kept:
        raise ValidationError(
            _("A choice field needs at least one option."), code="empty"
        )

    current = set(definition.options)
    originals = {row.original for row in kept if row.original in current}
    removed = [option for option in definition.options if option not in originals]
    counts = usage(definition)
    return OptionsPlan(
        options=[row.text for row in kept],
        renames={
            row.original: row.text
            for row in kept
            if row.original in current and row.text != row.original
        },
        removed=removed,
        affected={option: counts[option] for option in removed if counts.get(option)},
    )


@transaction.atomic
def save_options(definition: FieldDefinition, plan: OptionsPlan) -> None:
    """Store *plan*: drop removed values, carry renamed ones, save the list."""
    values = FieldValue.objects.filter(definition=definition)
    # Removals first: a rename may take over a removed option's text, and
    # the entries that held the removed one must not end up holding it.
    if plan.removed:
        values.filter(value_text__in=plan.removed).delete()
    if plan.renames:
        # One statement for every rename, so swapping two names cannot
        # turn both into the same one halfway through.
        values.filter(value_text__in=list(plan.renames)).update(
            value_text=Case(
                *(
                    When(value_text=old, then=Value(new))
                    for old, new in plan.renames.items()
                ),
                default=F("value_text"),
                output_field=TextField(),
            )
        )
    definition.options = plan.options
    definition.save(update_fields=["options"])
