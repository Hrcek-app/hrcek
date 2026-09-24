"""The release history: which release ran here, at which migrations.

It lives in a file beside the database rather than in a table, because
rolling back migrates tables away and the history must survive that.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings

from hrcek.ops.errors import HISTORY_UNREADABLE, HISTORY_UNWRITABLE, OpsError


@dataclass(frozen=True, slots=True)
class Release:
    release: str
    recorded_at: str
    kind: str  # "deploy", "rollback" or "restore"
    migrations: dict[str, str]


def _path() -> Path:
    return Path(settings.HRCEK_RELEASES_FILE)


def load() -> list[Release]:
    path = _path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Release(**item) for item in raw]
    except (OSError, ValueError, TypeError) as exc:
        raise OpsError(HISTORY_UNREADABLE, path=str(path)) from exc


def current() -> Release | None:
    entries = load()
    return entries[-1] if entries else None


def find(release: str) -> Release | None:
    for entry in reversed(load()):
        if entry.release == release:
            return entry
    return None


def append(release: str, kind: str, migrations: Mapping[str, str]) -> Release:
    entry = Release(
        release=release,
        recorded_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        kind=kind,
        migrations=dict(migrations),
    )
    entries = [*load(), entry]
    path = _path()
    temporary: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target, then rename over it: a crash mid-write
        # leaves the old history intact rather than half a file.
        handle, temporary = tempfile.mkstemp(
            dir=path.parent, prefix=".releases-", suffix=".json"
        )
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump([asdict(item) for item in entries], stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporary)
        raise OpsError(HISTORY_UNWRITABLE, path=str(path)) from exc
    return entry
