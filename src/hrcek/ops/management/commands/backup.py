from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from hrcek.ops import history, snapshots


class Command(BaseCommand):
    help = "Take a consistent snapshot of the database, and prune old ones."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--reason", choices=["manual", "pre-release"], default="manual"
        )
        parser.add_argument(
            "--if-new-release",
            action="store_true",
            help="Skip unless this release differs from the last one recorded.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Afterwards keep only the newest HRCEK_BACKUP_KEEP snapshots.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if self._wanted(only_if_new_release=options["if_new_release"]):
            snapshot = snapshots.take(options["reason"])
            self.stdout.write(
                _("Wrote snapshot %(name)s.") % {"name": snapshot.path.name}
            )
        if options["prune"]:
            for removed in snapshots.prune(settings.HRCEK_BACKUP_KEEP):
                self.stdout.write(
                    _("Removed old snapshot %(name)s.") % {"name": removed.path.name}
                )

    def _wanted(self, *, only_if_new_release: bool) -> bool:
        if snapshots.database_is_empty():
            self.stdout.write(_("The database is empty; there is nothing to snapshot."))
            return False
        current = history.current()
        if (
            only_if_new_release
            and current is not None
            and current.release == settings.HRCEK_RELEASE
        ):
            self.stdout.write(
                _("Release %(release)s is already recorded; no snapshot needed.")
                % {"release": settings.HRCEK_RELEASE}
            )
            return False
        if only_if_new_release:
            earlier = snapshots.taken_since_last_release()
            if earlier is not None:
                self.stdout.write(
                    _(
                        "This release already has its snapshot, %(name)s; "
                        "not taking another."
                    )
                    % {"name": earlier.path.name}
                )
                return False
        return True
