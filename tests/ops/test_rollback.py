from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from hrcek.ops import history, rollback, schema

pytestmark = pytest.mark.django_db


def _record(release, **overrides):
    history.append(release, "deploy", {**schema.applied_leaves(), **overrides})


def test_the_running_release_is_current():
    _record("v2.0.0")
    assert rollback.direction("v2.0.0") == "current"


def test_a_release_never_seen_lies_forward():
    _record("v2.0.0")
    assert rollback.direction("v3.0.0") == "forward"


def test_an_earlier_release_with_fewer_migrations_is_a_rollback():
    _record("v1.0.0", entries="0004_entryimage")
    _record("v2.0.0")
    assert rollback.direction("v1.0.0") == "rollback"


def test_an_earlier_release_with_the_same_migrations_just_starts():
    _record("v1.0.0")
    _record("v2.0.0")
    assert rollback.direction("v1.0.0") == "forward"


def test_a_release_rolled_back_from_lies_forward_again():
    # v3 ran, was rolled back from, and is asked for again. Its
    # migrations are unknown to this code, so it is newer: forward.
    _record("v2.0.0")
    _record("v3.0.0", entries="0099_from_the_future")
    _record("v2.0.0")
    assert rollback.direction("v3.0.0") == "forward"


def test_release_plan_prints_only_the_direction():
    _record("v2.0.0")
    out = StringIO()
    call_command("release_plan", "v3.0.0", stdout=out)
    assert out.getvalue() == "forward\n"


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("v1.0.0", "HRC-OPS-0002"),
        ("v2.0.0", "HRC-OPS-0003"),
        ("v3.0.0", "HRC-OPS-0009"),
    ],
)
def test_rollback_to_refuses_before_touching_anything(settings, target, code):
    _record("v3.0.0", entries="0099_from_the_future")
    _record("v2.0.0")
    with pytest.raises(CommandError, match=code):
        call_command("rollback_to", target, stdout=StringIO())
    assert not settings.HRCEK_BACKUP_PATH.exists()
