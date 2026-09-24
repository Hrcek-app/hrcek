from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from hrcek.ops import rollback


class Command(BaseCommand):
    help = "Print current, forward or rollback for a release."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("release")

    def handle(self, *args: Any, **options: Any) -> None:
        # One fixed word, read by deploy/deploy.sh; deliberately not
        # translated.
        self.stdout.write(rollback.direction(options["release"]))
