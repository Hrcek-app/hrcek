from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from hrcek.ops import history, snapshots
from hrcek.ops.errors import NO_RELEASE_RECORDED, OpsError

KINDS = {
    "deploy": gettext_lazy("deploy"),
    "rollback": gettext_lazy("rollback"),
    "restore": gettext_lazy("restore"),
}


class Command(BaseCommand):
    help = "Show the release history and the snapshots."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--current",
            action="store_true",
            help="Print only the current release, for scripts.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["current"]:
            current = history.current()
            if current is None:
                raise OpsError(NO_RELEASE_RECORDED)
            self.stdout.write(current.release)
            return

        self.stdout.write(_("Releases, oldest first:"))
        entries = history.load()
        if not entries:
            self.stdout.write("  " + _("none recorded"))
        for entry in entries:
            kind = str(KINDS.get(entry.kind, entry.kind))
            self.stdout.write(f"  {entry.recorded_at}  {kind:<10}  {entry.release}")

        self.stdout.write(_("Snapshots, oldest first:"))
        found = snapshots.listing()
        if not found:
            self.stdout.write("  " + _("none"))
        for snapshot in found:
            self.stdout.write(f"  {snapshot.path.name}")
