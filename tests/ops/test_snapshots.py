import sqlite3
from datetime import UTC, datetime

import pytest

from hrcek.ops import snapshots
from hrcek.ops.errors import OpsError

WHEN = datetime(2026, 9, 24, 10, 0, 0, tzinfo=UTC)


def _touch(folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"")
    return path


def test_a_snapshot_name_carries_time_release_and_reason():
    snapshot = snapshots.allocate(WHEN, "sha-abc1234", "pre-release")
    assert snapshot.path.name == (
        "20260924T100000.000000Z-sha-abc1234-pre-release.sqlite3"
    )
    assert snapshots.parse(snapshot.path) == snapshot


def test_allocate_never_reuses_a_name(settings):
    first = snapshots.allocate(WHEN, "v1.0.0", "manual")
    _touch(settings.HRCEK_BACKUP_PATH, first.path.name)

    second = snapshots.allocate(WHEN, "v1.0.0", "manual")

    assert second.path != first.path
    assert second.taken > first.taken


def test_files_not_named_like_snapshots_are_ignored(settings):
    _touch(settings.HRCEK_BACKUP_PATH, "notes.sqlite3")
    _touch(settings.HRCEK_BACKUP_PATH, "20260924T100000.000000Z-v1.0.0-manual.sqlite3")
    assert [snapshot.release for snapshot in snapshots.listing()] == ["v1.0.0"]


def test_prune_removes_the_oldest(settings):
    names = [
        f"2026092{day}T100000.000000Z-v1.0.0-manual.sqlite3" for day in range(1, 6)
    ]
    for name in names:
        _touch(settings.HRCEK_BACKUP_PATH, name)

    removed = snapshots.prune(2)

    assert [snapshot.path.name for snapshot in removed] == names[:3]
    remaining = sorted(path.name for path in settings.HRCEK_BACKUP_PATH.iterdir())
    assert remaining == names[3:]


def test_write_copy_produces_a_sound_copy(tmp_path):
    source = sqlite3.connect(tmp_path / "source.sqlite3")
    source.execute("CREATE TABLE t (x)")
    source.execute("INSERT INTO t VALUES (42)")
    source.commit()
    target = tmp_path / "copies" / "copy.sqlite3"

    snapshots.write_copy(source, target)
    source.close()

    copy = sqlite3.connect(target)
    assert copy.execute("SELECT x FROM t").fetchall() == [(42,)]
    copy.close()


def test_write_copy_into_an_unwritable_place_is_a_coded_error(tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")
    source = sqlite3.connect(":memory:")
    try:
        with pytest.raises(OpsError) as excinfo:
            snapshots.write_copy(source, blocker / "copy.sqlite3")
    finally:
        source.close()
    assert excinfo.value.error_code.code == "HRC-OPS-0004"


def test_resolve_refuses_a_file_not_named_like_a_snapshot():
    with pytest.raises(OpsError) as excinfo:
        snapshots.resolve("notes.sqlite3")
    assert excinfo.value.error_code.code == "HRC-OPS-0007"


def test_resolve_refuses_a_missing_snapshot():
    with pytest.raises(OpsError) as excinfo:
        snapshots.resolve("20260924T100000.000000Z-v1.0.0-manual.sqlite3")
    assert excinfo.value.error_code.code == "HRC-OPS-0005"


def test_earliest_since_picks_the_newest_pre_release_snapshot_after_it(settings):
    folder = settings.HRCEK_BACKUP_PATH
    _touch(folder, "20260924T095959.000000Z-v1.0.0-pre-release.sqlite3")
    _touch(folder, "20260924T100001.000000Z-v1.0.0-pre-release.sqlite3")
    _touch(folder, "20260924T100002.000000Z-v1.0.0-manual.sqlite3")

    found = snapshots.earliest_since(WHEN)

    assert found is not None
    assert found.path.name == "20260924T100001.000000Z-v1.0.0-pre-release.sqlite3"
    assert snapshots.earliest_since(datetime(2026, 9, 25, tzinfo=UTC)) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20260924T100000Z", WHEN),
        ("20260924T100000.500000Z", WHEN.replace(microsecond=500000)),
    ],
)
def test_parse_time_accepts_the_deploy_script_format(raw, expected):
    assert snapshots.parse_time(raw) == expected


def test_parse_time_refuses_anything_else():
    with pytest.raises(OpsError) as excinfo:
        snapshots.parse_time("yesterday")
    assert excinfo.value.error_code.code == "HRC-OPS-0010"


def test_a_snapshot_of_a_wal_database_opens_read_only_without_side_files(tmp_path):
    # A snapshot keeping WAL mode needs -shm/-wal files to be read, which
    # a read-only open leaves behind in the backups folder (and older
    # SQLite refuses outright). Snapshots are plain rollback-journal files.
    source = sqlite3.connect(tmp_path / "live.sqlite3")
    source.execute("PRAGMA journal_mode=WAL")
    source.execute("CREATE TABLE t (x)")
    source.commit()
    folder = tmp_path / "copies"
    target = folder / "copy.sqlite3"

    snapshots.write_copy(source, target)
    source.close()
    reader = sqlite3.connect(f"{target.as_uri()}?mode=ro", uri=True)
    assert reader.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    reader.close()

    assert [path.name for path in folder.iterdir()] == ["copy.sqlite3"]


def test_earliest_since_picks_the_first_pre_release_snapshot_after_it(settings):
    # A failed release restarting in a loop snapshots its half-migrated
    # database again; the one to go back to is the first.
    folder = settings.HRCEK_BACKUP_PATH
    _touch(folder, "20260924T095959.000000Z-v1.0.0-pre-release.sqlite3")
    _touch(folder, "20260924T100001.000000Z-v1.0.0-pre-release.sqlite3")
    _touch(folder, "20260924T100005.000000Z-v1.0.0-pre-release.sqlite3")

    found = snapshots.earliest_since(WHEN)

    assert found is not None
    assert found.path.name == "20260924T100001.000000Z-v1.0.0-pre-release.sqlite3"
    assert snapshots.earliest_since(datetime(2026, 9, 25, tzinfo=UTC)) is None


def test_prune_that_cannot_delete_is_a_coded_error(settings):
    folder = settings.HRCEK_BACKUP_PATH
    for day in (1, 2):
        _touch(folder, f"2026092{day}T100000.000000Z-v1.0.0-manual.sqlite3")
    folder.chmod(0o500)
    try:
        with pytest.raises(OpsError) as excinfo:
            snapshots.prune(1)
    finally:
        folder.chmod(0o700)
    assert excinfo.value.error_code.code == "HRC-OPS-0004"
