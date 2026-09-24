from tests.support import run_manage


def _snapshots(tmp_path):
    return sorted(path.name for path in (tmp_path / "backups").glob("*.sqlite3"))


def _migrated(tmp_path, release="v1.0.0"):
    run_manage("migrate", "--no-input", data_dir=tmp_path)
    run_manage("record_release", data_dir=tmp_path, env={"HRCEK_RELEASE": release})


def test_an_empty_database_is_not_snapshotted(tmp_path):
    result = run_manage(
        "backup", "--reason", "pre-release", "--if-new-release", data_dir=tmp_path
    )
    assert "empty" in result.stdout
    assert _snapshots(tmp_path) == []


def test_a_new_release_is_snapshotted_under_the_release_it_replaces(tmp_path):
    _migrated(tmp_path)
    run_manage(
        "backup",
        "--reason",
        "pre-release",
        "--if-new-release",
        data_dir=tmp_path,
        env={"HRCEK_RELEASE": "v2.0.0"},
    )
    [name] = _snapshots(tmp_path)
    assert name.endswith("-v1.0.0-pre-release.sqlite3")


def test_a_restart_of_the_same_release_is_not_snapshotted(tmp_path):
    _migrated(tmp_path)
    run_manage(
        "backup",
        "--reason",
        "pre-release",
        "--if-new-release",
        data_dir=tmp_path,
        env={"HRCEK_RELEASE": "v1.0.0"},
    )
    assert _snapshots(tmp_path) == []


def test_prune_keeps_backup_keep_snapshots(tmp_path):
    _migrated(tmp_path)
    for _ in range(3):
        run_manage("backup", data_dir=tmp_path)
    run_manage("backup", "--prune", data_dir=tmp_path, env={"HRCEK_BACKUP_KEEP": "2"})
    assert len(_snapshots(tmp_path)) == 2


def test_an_unwritable_backup_folder_fails_with_a_code(tmp_path):
    _migrated(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")

    result = run_manage(
        "backup",
        data_dir=tmp_path,
        env={"HRCEK_BACKUP_PATH": str(blocker)},
        check=False,
    )

    assert result.returncode != 0
    assert "HRC-OPS-0004" in result.stderr
    assert "Traceback" not in result.stderr


def test_a_backup_folder_that_cannot_be_entered_fails_with_a_code(tmp_path):
    # Rootful Docker with data/backups owned by someone else.
    _migrated(tmp_path)
    locked = tmp_path / "backups"
    locked.mkdir()
    locked.chmod(0)
    try:
        result = run_manage("backup", data_dir=tmp_path, check=False)
    finally:
        locked.chmod(0o700)

    assert result.returncode != 0
    assert "HRC-OPS-0004" in result.stderr
    assert "Traceback" not in result.stderr


def test_a_release_restarting_in_a_loop_keeps_its_first_snapshot(tmp_path):
    # A release whose start fails partway restarts again and again. Only
    # the first snapshot holds the database as it was before; the later
    # ones would hold it half-migrated, and pruning would push the first
    # one out.
    _migrated(tmp_path)
    v2 = {"HRCEK_RELEASE": "v2.0.0"}
    for _ in range(3):
        run_manage(
            "backup",
            "--reason",
            "pre-release",
            "--if-new-release",
            data_dir=tmp_path,
            env=v2,
        )
    assert len(_snapshots(tmp_path)) == 1
