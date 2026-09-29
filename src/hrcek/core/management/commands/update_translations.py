from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from hrcek.core.translations import catalogues

# The one way the catalogues are extracted. --add-location=file keeps
# the source file but not the line, so moving code inside a file does
# not churn every catalogue; the ignores keep makemessages out of the
# virtualenv, the docs and the tests.
MAKEMESSAGES_OPTIONS: dict[str, Any] = {
    "all": True,
    "no_obsolete": True,
    "add_location": "file",
    "ignore_patterns": [".venv", "docs", "tests"],
    "verbosity": 0,
}

CREATION_DATE = re.compile(rb'^"POT-Creation-Date: [^"\n]*"$', re.MULTILINE)


def _keep_creation_date(new: bytes, old: bytes) -> bytes:
    """makemessages restamps POT-Creation-Date on every run. The stamp
    means nothing, and on stacked branches it is the line every one of
    them changes, so the old one is put back."""
    previous = CREATION_DATE.search(old)
    if previous is None:
        return new
    return CREATION_DATE.sub(lambda _match: previous.group(0), new, count=1)


class Command(BaseCommand):
    help = "Bring the translation catalogues in line with the source."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help="Report stale catalogues instead of updating them.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        before = {
            po: (po.read_bytes(), po.stat())
            for root in settings.LOCALE_PATHS
            for po in catalogues(Path(root))
        }

        # makemessages walks the current directory, so run it from the
        # project root wherever this was called from.
        cwd = os.getcwd()
        os.chdir(settings.BASE_DIR)
        try:
            call_command("makemessages", **MAKEMESSAGES_OPTIONS)
        finally:
            os.chdir(cwd)

        changed = []
        for po, (old, stat) in before.items():
            new = _keep_creation_date(po.read_bytes(), old)
            if new != old:
                changed.append(po)
            if new == old or options["check"]:
                # Unchanged, or only being checked: put the file back
                # exactly, time included, so its compiled copy stays
                # fresh.
                po.write_bytes(old)
                os.utime(po, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            else:
                po.write_bytes(new)

        if not changed:
            self.stdout.write(_("The translation catalogues are up to date."))
            return

        names = ", ".join(str(po) for po in changed)
        if options["check"]:
            raise CommandError(
                _(
                    "The translation catalogues are out of date: %(files)s. "
                    "Run: uv run python manage.py update_translations"
                )
                % {"files": names}
            )
        self.stdout.write(
            _(
                "Updated %(files)s. Translate the new entries, then add the "
                "files to your commit."
            )
            % {"files": names}
        )
