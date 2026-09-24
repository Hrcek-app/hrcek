from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

from hrcek.ops import history, schema

pytestmark = pytest.mark.django_db

FUTURE = ("entries", "0099_from_the_future")


def test_applied_leaves_names_the_newest_migration_of_every_app():
    loader = MigrationLoader(connection)
    assert schema.applied_leaves() == dict(sorted(loader.graph.leaf_nodes()))


def test_a_fully_migrated_database_has_no_unknown_migrations():
    assert schema.unknown_applied() == []


def test_a_migration_from_a_newer_release_is_reported():
    MigrationRecorder(connection).record_applied(*FUTURE)
    assert schema.unknown_applied() == ["entries.0099_from_the_future"]


def test_check_schema_passes_on_a_normal_database():
    out = StringIO()
    call_command("check_schema", stdout=out)
    assert "known to this release" in out.getvalue()


def test_check_schema_refuses_a_database_from_a_newer_release():
    MigrationRecorder(connection).record_applied(*FUTURE)
    with pytest.raises(CommandError, match="HRC-OPS-0001"):
        call_command("check_schema")


def test_record_release_records_a_first_deploy():
    call_command("record_release", stdout=StringIO())
    current = history.current()
    assert current is not None
    assert (current.release, current.kind) == ("v2.0.0", "deploy")
    assert current.migrations == schema.applied_leaves()


def test_record_release_ignores_a_restart_of_the_same_release():
    call_command("record_release", stdout=StringIO())
    call_command("record_release", stdout=StringIO())
    assert len(history.load()) == 1


def test_record_release_calls_a_return_to_an_earlier_release_a_deploy(settings):
    # Only rollback_to knows a rollback happened, and it records one
    # itself. A release seen before that starts here some other way —
    # a redeploy after rolling back from it — went forward.
    history.append("v1.0.0", "deploy", {})
    history.append("v2.0.0", "deploy", {})
    settings.HRCEK_RELEASE = "v1.0.0"

    call_command("record_release", stdout=StringIO())

    current = history.current()
    assert current is not None
    assert (current.release, current.kind) == ("v1.0.0", "deploy")
