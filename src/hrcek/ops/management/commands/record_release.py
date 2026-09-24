from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from hrcek.ops import history, schema


class Command(BaseCommand):
    help = "Record the running release and its migrations in the history."

    def handle(self, *args: Any, **options: Any) -> None:
        release = settings.HRCEK_RELEASE
        current = history.current()
        if current is not None and current.release == release:
            self.stdout.write(
                _("Release %(release)s is already recorded.") % {"release": release}
            )
            return
        # A rollback is recorded by rollback_to, which knows it happened.
        # A release reaching this point went forward.
        history.append(release, "deploy", schema.applied_leaves())
        self.stdout.write(_("Recorded release %(release)s.") % {"release": release})
