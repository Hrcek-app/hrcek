"""The state behind the options editor, and saving it."""

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.entries.choice_options import (
    OptionRow,
    StaleOptionsError,
    apply_op,
    plan_options,
    save_options,
    usage,
)
from hrcek.entries.models import FieldDefinition, FieldValue
from hrcek.entries.services import save_entry


def _rows(*texts):
    return [OptionRow(text, text) for text in texts]


def _texts(rows):
    return [row.text for row in rows]


# apply_op needs no database: it works on the rows alone.


def test_up_moves_a_row_up():
    assert _texts(apply_op(_rows("a", "b", "c"), "up:2", "")) == ["a", "c", "b"]


def test_down_moves_a_row_down():
    assert _texts(apply_op(_rows("a", "b", "c"), "down:0", "")) == ["b", "a", "c"]


def test_moving_keeps_the_original_with_its_row():
    rows = apply_op([OptionRow("x", "a"), OptionRow("b", "b")], "down:0", "")
    assert rows == [OptionRow("b", "b"), OptionRow("x", "a")]


@pytest.mark.parametrize("op", ["up:0", "down:2", "remove:3", "up:-1", "up:x", "sing"])
def test_an_impossible_op_changes_nothing(op):
    assert _texts(apply_op(_rows("a", "b", "c"), op, "")) == ["a", "b", "c"]


def test_remove_drops_a_row():
    assert _texts(apply_op(_rows("a", "b", "c"), "remove:1", "")) == ["a", "c"]


def test_add_appends_a_new_row_without_an_original():
    rows = apply_op(_rows("a"), "add", "  b  ")
    assert rows == [OptionRow("a", "a"), OptionRow("b", "")]


def test_a_blank_add_changes_nothing():
    assert apply_op(_rows("a"), "add", "   ") == _rows("a")


# Planning and saving need a field and some entries.


@pytest.fixture
def nina(db):
    return User.objects.create_user(
        email="nina@example.com",
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def size(nina):
    return FieldDefinition.objects.create(
        owner=nina, name="Size", kind=FieldDefinition.CHOICE, options=["s", "m", "l"]
    )


def _entry_with(owner, definition, value, n=[0]):  # noqa: B006
    n[0] += 1
    entry, _ = save_entry(owner, url=f"https://example.com/{n[0]}", title="T")
    FieldValue.objects.create(entry=entry, definition=definition, value_text=value)
    return entry


def _values(definition):
    return sorted(
        FieldValue.objects.filter(definition=definition).values_list(
            "value_text", flat=True
        )
    )


def test_usage_counts_entries_per_option(nina, size):
    _entry_with(nina, size, "s")
    _entry_with(nina, size, "s")
    _entry_with(nina, size, "l")
    assert usage(size) == {"s": 2, "l": 1}


def test_a_plan_keeps_order_and_finds_nothing_to_confirm(size):
    plan = plan_options(size, _rows("l", "m", "s"), ["s", "m", "l"])
    assert plan.options == ["l", "m", "s"]
    assert plan.renames == {}
    assert plan.removed == []
    assert plan.affected == {}


def test_blank_rows_are_dropped(size):
    rows = [*_rows("s", "m", "l"), OptionRow("  ", "")]
    assert plan_options(size, rows, ["s", "m", "l"]).options == ["s", "m", "l"]


def test_text_is_stripped(size):
    rows = [OptionRow(" s ", "s"), *_rows("m", "l")]
    assert plan_options(size, rows, ["s", "m", "l"]).options == ["s", "m", "l"]


def test_changed_text_is_a_rename(size):
    rows = [OptionRow("small", "s"), *_rows("m", "l")]
    assert plan_options(size, rows, ["s", "m", "l"]).renames == {"s": "small"}


def test_a_missing_original_is_a_removal(nina, size):
    _entry_with(nina, size, "l")
    plan = plan_options(size, _rows("s", "m"), ["s", "m", "l"])
    assert plan.removed == ["l"]
    assert plan.affected == {"l": 1}


def test_an_unused_removal_needs_no_confirmation(size):
    plan = plan_options(size, _rows("s", "m"), ["s", "m", "l"])
    assert plan.removed == ["l"]
    assert plan.affected == {}


def test_blanked_row_is_a_removal(nina, size):
    _entry_with(nina, size, "m")
    rows = [OptionRow("s", "s"), OptionRow("", "m"), OptionRow("l", "l")]
    plan = plan_options(size, rows, ["s", "m", "l"])
    assert plan.removed == ["m"]
    assert plan.affected == {"m": 1}


def test_duplicates_are_refused_in_any_casing(size):
    rows = [*_rows("s", "m", "l"), OptionRow("M", "")]
    with pytest.raises(ValidationError) as caught:
        plan_options(size, rows, ["s", "m", "l"])
    assert caught.value.code == "duplicate"


def test_long_text_is_refused(size):
    rows = [*_rows("s", "m", "l"), OptionRow("x" * 101, "")]
    with pytest.raises(ValidationError) as caught:
        plan_options(size, rows, ["s", "m", "l"])
    assert caught.value.code == "too_long"


def test_a_hundred_characters_is_fine(size):
    rows = [*_rows("s", "m", "l"), OptionRow("x" * 100, "")]
    assert len(plan_options(size, rows, ["s", "m", "l"]).options) == 4


def test_no_options_is_refused(size):
    with pytest.raises(ValidationError) as caught:
        plan_options(size, [OptionRow(" ", "s")], ["s", "m", "l"])
    assert caught.value.code == "empty"


def test_stale_form_is_refused(size):
    size.options = ["s", "m", "l", "xl"]
    size.save()
    with pytest.raises(StaleOptionsError):
        plan_options(size, _rows("s", "m", "l"), ["s", "m", "l"])


def test_saving_stores_the_new_order(size):
    save_options(size, plan_options(size, _rows("l", "s", "m"), ["s", "m", "l"]))
    size.refresh_from_db()
    assert size.options == ["l", "s", "m"]


def test_a_rename_carries_the_values(nina, size):
    _entry_with(nina, size, "s")
    rows = [OptionRow("small", "s"), *_rows("m", "l")]
    save_options(size, plan_options(size, rows, ["s", "m", "l"]))
    assert _values(size) == ["small"]


def test_a_swap_does_not_collide(nina, size):
    _entry_with(nina, size, "s")
    _entry_with(nina, size, "l")
    _entry_with(nina, size, "l")
    rows = [OptionRow("l", "s"), OptionRow("m", "m"), OptionRow("s", "l")]
    save_options(size, plan_options(size, rows, ["s", "m", "l"]))
    assert _values(size) == ["l", "s", "s"]


def test_a_removal_deletes_the_values(nina, size):
    _entry_with(nina, size, "l")
    _entry_with(nina, size, "s")
    save_options(size, plan_options(size, _rows("s", "m"), ["s", "m", "l"]))
    assert _values(size) == ["s"]


def test_rename_onto_a_removed_name(nina, size):
    _entry_with(nina, size, "l")
    _entry_with(nina, size, "m")
    rows = [OptionRow("s", "s"), OptionRow("l", "m")]
    save_options(size, plan_options(size, rows, ["s", "m", "l"]))
    # The entry that had l lost it; the one that had m now has l.
    assert _values(size) == ["l"]


def test_other_fields_are_left_alone(nina, size):
    other = FieldDefinition.objects.create(
        owner=nina, name="Fit", kind=FieldDefinition.CHOICE, options=["s", "l"]
    )
    _entry_with(nina, other, "s")
    _entry_with(nina, other, "l")
    rows = [OptionRow("small", "s"), *_rows("m")]
    save_options(size, plan_options(size, rows, ["s", "m", "l"]))
    assert _values(other) == ["l", "s"]
