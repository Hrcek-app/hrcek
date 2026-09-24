"""Consistent copies of the database, and putting one back.

Copies use SQLite's backup API: safe while the app is running, correct
with WAL, and needing no sqlite3 binary in the image.
"""

from __future__ import annotations

import contextlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection

from hrcek.ops import history, schema
from hrcek.ops.errors import (
    INVALID_TIME,
    SNAPSHOT_FAILED,
    SNAPSHOT_NAME_INVALID,
    SNAPSHOT_NOT_FOUND,
    OpsError,
)

REASONS = ("pre-release", "pre-rollback", "manual")
TIME_FORMAT = "%Y%m%dT%H%M%S.%fZ"
# The deploy script's `date -u +%Y%m%dT%H%M%SZ`, without the fraction.
SHORT_TIME_FORMAT = "%Y%m%dT%H%M%SZ"
_NAME = re.compile(
    r"^(?P<taken>\d{8}T\d{6}\.\d{6}Z)-(?P<release>.+)-"
    r"(?P<reason>pre-release|pre-rollback|manual)\.sqlite3$"
)


@dataclass(frozen=True, slots=True)
class Snapshot:
    path: Path
    taken: datetime
    release: str  # the release whose data this holds
    reason: str


def folder() -> Path:
    return Path(settings.HRCEK_BACKUP_PATH)


def parse(path: Path) -> Snapshot | None:
    match = _NAME.match(path.name)
    if match is None:
        return None
    taken = datetime.strptime(match["taken"], TIME_FORMAT).replace(tzinfo=UTC)
    return Snapshot(path, taken, match["release"], match["reason"])


def listing() -> list[Snapshot]:
    if not folder().is_dir():
        return []
    found = [
        snapshot
        for path in folder().glob("*.sqlite3")
        if (snapshot := parse(path)) is not None
    ]
    return sorted(found, key=lambda snapshot: snapshot.taken)


def allocate(when: datetime, release: str, reason: str) -> Snapshot:
    """A snapshot slot that does not overwrite an existing file."""
    while True:
        path = folder() / f"{when.strftime(TIME_FORMAT)}-{release}-{reason}.sqlite3"
        if not path.exists():
            return Snapshot(path, when, release, reason)
        when += timedelta(microseconds=1)


def _discard(path: Path) -> None:
    """Remove a failed copy, if one was written at all."""
    with contextlib.suppress(OSError):
        path.unlink()


def write_copy(source: sqlite3.Connection, path: Path) -> None:
    """Copy *source* to *path*, and prove the copy is sound."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(path)
        try:
            source.backup(target)
            # The copy inherits the live database's WAL mode, and a WAL
            # file cannot be read without -wal and -shm beside it. A
            # plain journal file opens read-only and leaves nothing.
            target.execute("PRAGMA journal_mode=DELETE")
            (verdict,) = target.execute("PRAGMA integrity_check").fetchone()
        finally:
            target.close()
    except (OSError, sqlite3.Error) as exc:
        _discard(path)
        raise OpsError(SNAPSHOT_FAILED, snapshot=path.name) from exc
    if verdict != "ok":
        _discard(path)
        raise OpsError(SNAPSHOT_FAILED, snapshot=path.name)


def database_is_empty() -> bool:
    return not connection.introspection.table_names()


def take(reason: str) -> Snapshot:
    current = history.current()
    release = current.release if current is not None else "none"
    try:
        snapshot = allocate(datetime.now(UTC), release, reason)
    except OSError as exc:
        raise OpsError(SNAPSHOT_FAILED, snapshot=str(folder())) from exc
    connection.ensure_connection()
    write_copy(connection.connection, snapshot.path)
    return snapshot


def prune(keep: int) -> list[Snapshot]:
    existing = listing()
    doomed = existing[: max(len(existing) - keep, 0)]
    for snapshot in doomed:
        try:
            snapshot.path.unlink(missing_ok=True)
        except OSError as exc:
            raise OpsError(SNAPSHOT_FAILED, snapshot=snapshot.path.name) from exc
    return doomed


def resolve(name: str) -> Snapshot:
    path = Path(name)
    if not path.is_absolute():
        path = folder() / path
    snapshot = parse(path)
    if snapshot is None:
        raise OpsError(SNAPSHOT_NAME_INVALID, snapshot=path.name)
    if not path.is_file():
        raise OpsError(SNAPSHOT_NOT_FOUND, snapshot=path.name)
    return snapshot


def earliest_since(since: datetime, reason: str = "pre-release") -> Snapshot | None:
    """The first snapshot taken at or after *since*.

    The first, not the newest: a release that failed partway through
    migrating and restarted may have snapshotted its own half-migrated
    database after it.
    """
    matches = [s for s in listing() if s.reason == reason and s.taken >= since]
    return matches[0] if matches else None


def taken_since_last_release(reason: str = "pre-release") -> Snapshot | None:
    """A snapshot taken after the last history entry, if there is one.

    Such a snapshot belongs to a release that started and has not yet
    been recorded; it is the one that holds the database from before.
    """
    current = history.current()
    if current is None:
        since = datetime.min.replace(tzinfo=UTC)
    else:
        since = datetime.strptime(current.recorded_at, "%Y-%m-%dT%H:%M:%SZ")
        since = since.replace(tzinfo=UTC)
    return earliest_since(since, reason)


def parse_time(raw: str) -> datetime:
    for layout in (SHORT_TIME_FORMAT, TIME_FORMAT):
        try:
            return datetime.strptime(raw, layout).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise OpsError(INVALID_TIME, time=raw)


def restore(snapshot: Snapshot) -> None:
    """Replace the database's contents with *snapshot*.

    The app must be stopped: anything it writes meanwhile is lost, and
    it would be running against a schema it may not expect.
    """
    connection.ensure_connection()
    try:
        source = sqlite3.connect(
            f"{snapshot.path.resolve().as_uri()}?mode=ro", uri=True
        )
        try:
            source.backup(connection.connection)
        finally:
            source.close()
    except sqlite3.Error as exc:
        raise OpsError(SNAPSHOT_FAILED, snapshot=snapshot.path.name) from exc
    history.append(snapshot.release, "restore", schema.applied_leaves())
