"""Error codes owned by the ops app.

These are reported by management commands on the host, never over
HTTP. The status is registered only because every code carries one.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import CommandError
from django.utils.translation import gettext_lazy as _

from hrcek.core.errors import ErrorCode, register

UNKNOWN_MIGRATIONS = register(
    "HRC-OPS-0001",
    500,
    _(
        "The database has migrations applied that this release does not "
        "know. A newer release ran here; roll back using that release, or "
        "restore a snapshot."
    ),
)
RELEASE_NOT_RECORDED = register(
    "HRC-OPS-0002",
    500,
    _(
        "That release has never run against this database, so there is "
        "nothing to roll back to."
    ),
)
RELEASE_IS_CURRENT = register(
    "HRC-OPS-0003", 500, _("That release is already the current one.")
)
SNAPSHOT_FAILED = register(
    "HRC-OPS-0004",
    500,
    _("The snapshot could not be written or read, or failed its integrity check."),
)
SNAPSHOT_NOT_FOUND = register("HRC-OPS-0005", 500, _("That snapshot does not exist."))
HISTORY_UNREADABLE = register(
    "HRC-OPS-0006", 500, _("The release history file cannot be read.")
)
SNAPSHOT_NAME_INVALID = register(
    "HRC-OPS-0007",
    500,
    _("That file is not named like a snapshot, so the release it holds is unknown."),
)
NO_RELEASE_RECORDED = register(
    "HRC-OPS-0008", 500, _("No release has been recorded yet.")
)
RELEASE_IS_NEWER = register(
    "HRC-OPS-0009",
    500,
    _("That release is newer than this one. Deploy it instead."),
)
INVALID_TIME = register(
    "HRC-OPS-0010",
    500,
    _("That time is not in the form 20260924T100000Z."),
)

ROLLBACK_FAILED = register(
    "HRC-OPS-0011",
    500,
    _(
        "Migrating down failed, so the database was put back as it was "
        "before the rollback began."
    ),
)
HISTORY_UNWRITABLE = register(
    "HRC-OPS-0012", 500, _("The release history file cannot be written.")
)


class OpsError(CommandError):
    """A registered failure, reported by a management command."""

    def __init__(self, error_code: ErrorCode, **details: Any) -> None:
        self.error_code = error_code
        self.details = details
        text = f"{error_code.code}: {error_code.message}"
        if details:
            pairs = ", ".join(
                f"{key}={value}" for key, value in sorted(details.items())
            )
            text = f"{text} ({pairs})"
        super().__init__(text)
