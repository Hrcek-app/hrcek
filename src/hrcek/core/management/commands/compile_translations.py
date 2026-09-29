from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from hrcek.core.translations import compile_all_stale


class Command(BaseCommand):
    help = "Build the compiled translation catalogues that are missing or stale."

    def handle(self, *args: Any, **options: Any) -> None:
        built = compile_all_stale()
        if not built:
            self.stdout.write(_("The compiled catalogues are up to date."))
            return
        self.stdout.write(
            ngettext(
                "Compiled %(count)d catalogue.",
                "Compiled %(count)d catalogues.",
                len(built),
            )
            % {"count": len(built)}
        )
