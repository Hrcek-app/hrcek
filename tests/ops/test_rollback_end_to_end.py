import json

from tests.support import run_manage

HAS_SCRATCH = (
    "from django.db import connection; "
    "print('scratch' in connection.introspection.table_names())"
)
MAKE_SCRATCH = (
    "from django.db import connection; "
    "connection.cursor().execute('CREATE TABLE scratch (x)')"
)


def _history(tmp_path):
    return json.loads((tmp_path / "releases.json").read_text(encoding="utf-8"))


def _pretend_an_earlier_release(tmp_path, **leaves):
    """Record v1.0.0 before the current v2.0.0, at the given leaves."""
    [current] = _history(tmp_path)
    earlier = {
        **current,
        "release": "v1.0.0",
        "migrations": {**current["migrations"], **leaves},
    }
    for app, name in list(earlier["migrations"].items()):
        if name is None:
            del earlier["migrations"][app]
    (tmp_path / "releases.json").write_text(
        json.dumps([earlier, current]), encoding="utf-8"
    )


def _deployed(tmp_path):
    run_manage("migrate", "--no-input", data_dir=tmp_path)
    run_manage("record_release", data_dir=tmp_path, env={"HRCEK_RELEASE": "v2.0.0"})


def test_rollback_migrates_down_to_the_recorded_state(tmp_path):
    _deployed(tmp_path)
    _pretend_an_earlier_release(tmp_path, entries="0004_entryimage")

    run_manage(
        "rollback_to", "v1.0.0", data_dir=tmp_path, env={"HRCEK_RELEASE": "v2.0.0"}
    )

    shown = run_manage("showmigrations", "entries", data_dir=tmp_path).stdout
    assert "[X] 0004_entryimage" in shown
    assert "[ ] 0005_retire_price_field" in shown
    names = [path.name for path in (tmp_path / "backups").iterdir()]
    assert any(name.endswith("-v2.0.0-pre-rollback.sqlite3") for name in names)


def test_rollback_records_the_target_so_its_startup_has_nothing_to_do(tmp_path):
    _deployed(tmp_path)
    _pretend_an_earlier_release(tmp_path, entries="0004_entryimage")
    run_manage(
        "rollback_to", "v1.0.0", data_dir=tmp_path, env={"HRCEK_RELEASE": "v2.0.0"}
    )
    last = _history(tmp_path)[-1]
    assert (last["release"], last["kind"]) == ("v1.0.0", "rollback")
    assert last["migrations"]["entries"] == "0004_entryimage"

    # What the older release's entrypoint then runs:
    v1 = {"HRCEK_RELEASE": "v1.0.0"}
    run_manage(
        "backup",
        "--reason",
        "pre-release",
        "--if-new-release",
        data_dir=tmp_path,
        env=v1,
    )
    run_manage("record_release", data_dir=tmp_path, env=v1)

    assert len(_history(tmp_path)) == 3
    assert len(list((tmp_path / "backups").iterdir())) == 1


def test_rollback_unapplies_an_app_the_earlier_release_did_not_have(tmp_path):
    _deployed(tmp_path)
    _pretend_an_earlier_release(tmp_path, collections=None)

    run_manage(
        "rollback_to", "v1.0.0", data_dir=tmp_path, env={"HRCEK_RELEASE": "v2.0.0"}
    )

    shown = run_manage("showmigrations", "collections", data_dir=tmp_path).stdout
    assert "[X]" not in shown


def test_restore_puts_the_snapshot_back_and_records_it(tmp_path):
    _deployed(tmp_path)
    run_manage("backup", data_dir=tmp_path)
    [snapshot] = [path.name for path in (tmp_path / "backups").iterdir()]
    run_manage("shell", "--no-imports", "-c", MAKE_SCRATCH, data_dir=tmp_path)

    run_manage("restore", snapshot, data_dir=tmp_path)

    shown = run_manage(
        "shell", "--no-imports", "-c", HAS_SCRATCH, data_dir=tmp_path
    ).stdout
    assert shown.strip() == "False"
    last = _history(tmp_path)[-1]
    assert (last["release"], last["kind"]) == ("v2.0.0", "restore")


def test_restore_earliest_since_undoes_a_failed_release(tmp_path):
    _deployed(tmp_path)
    run_manage(
        "backup",
        "--reason",
        "pre-release",
        "--if-new-release",
        data_dir=tmp_path,
        env={"HRCEK_RELEASE": "v3.0.0"},
    )
    run_manage("shell", "--no-imports", "-c", MAKE_SCRATCH, data_dir=tmp_path)

    run_manage("restore", "--earliest-since", "20000101T000000Z", data_dir=tmp_path)

    shown = run_manage(
        "shell", "--no-imports", "-c", HAS_SCRATCH, data_dir=tmp_path
    ).stdout
    assert shown.strip() == "False"


def test_restore_earliest_since_with_nothing_newer_changes_nothing(tmp_path):
    _deployed(tmp_path)
    result = run_manage(
        "restore", "--earliest-since", "29991231T000000Z", data_dir=tmp_path
    )
    assert "nothing to restore" in result.stdout
    assert _history(tmp_path)[-1]["kind"] == "deploy"


# Reverse one migration for real, then fail on the next, as a reverse
# AlterField to NOT NULL does when null rows exist.
FAIL_ON_SECOND_REVERSAL = """
from unittest import mock
from django.core.management import call_command
from django.db.migrations.executor import MigrationExecutor
real = MigrationExecutor.unapply_migration
calls = []
def flaky(self, state, migration, fake=False):
    calls.append(migration)
    if len(calls) == 2:
        raise RuntimeError("reverse failed")
    return real(self, state, migration, fake=fake)
with mock.patch.object(MigrationExecutor, "unapply_migration", flaky):
    call_command("rollback_to", "v1.0.0")
"""


def test_a_failed_migrate_down_puts_the_database_back(tmp_path):
    _deployed(tmp_path)
    _pretend_an_earlier_release(tmp_path, entries="0003_seed_default_fields")

    result = run_manage(
        "shell",
        "--no-imports",
        "-c",
        FAIL_ON_SECOND_REVERSAL,
        data_dir=tmp_path,
        env={"HRCEK_RELEASE": "v2.0.0"},
        check=False,
    )

    assert result.returncode != 0
    assert "HRC-OPS-0011" in result.stderr
    shown = run_manage("showmigrations", "entries", data_dir=tmp_path).stdout
    assert "[X] 0005_retire_price_field" in shown
    last = _history(tmp_path)[-1]
    assert (last["release"], last["kind"]) == ("v2.0.0", "restore")
