from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from hrcek.ops import schema
from hrcek.ops.errors import UNKNOWN_MIGRATIONS, OpsError


class Command(BaseCommand):
    help = "Refuse a database that a newer release has migrated."

    def handle(self, *args: Any, **options: Any) -> None:
        unknown = schema.unknown_applied()
        if unknown:
            raise OpsError(UNKNOWN_MIGRATIONS, migrations=", ".join(unknown))
        self.stdout.write(_("Every applied migration is known to this release."))
