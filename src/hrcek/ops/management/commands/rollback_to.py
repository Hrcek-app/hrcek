from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from hrcek.ops import rollback


class Command(BaseCommand):
    help = "Snapshot, then migrate down to the state an earlier release expects."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("release")

    def handle(self, *args: Any, **options: Any) -> None:
        release = options["release"]
        snapshot = rollback.rollback_to(release)
        self.stdout.write(_("Wrote snapshot %(name)s.") % {"name": snapshot.path.name})
        self.stdout.write(
            _("The database is now as release %(release)s expects it.")
            % {"release": release}
        )
