from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from hrcek.ops import snapshots


class Command(BaseCommand):
    help = "Replace the database with a snapshot. Stop the app first."

    def add_arguments(self, parser: Any) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("snapshot", nargs="?")
        group.add_argument("--earliest-since", metavar="TIME")

    def handle(self, *args: Any, **options: Any) -> None:
        since = options["earliest_since"]
        if since is not None:
            found = snapshots.earliest_since(snapshots.parse_time(since))
            if found is None:
                self.stdout.write(
                    _("No snapshot was taken since %(time)s; nothing to restore.")
                    % {"time": since}
                )
                return
            snapshot = found
        else:
            snapshot = snapshots.resolve(options["snapshot"])
        snapshots.restore(snapshot)
        self.stdout.write(
            _("Restored %(name)s; the database now holds release %(release)s.")
            % {"name": snapshot.path.name, "release": snapshot.release}
        )
