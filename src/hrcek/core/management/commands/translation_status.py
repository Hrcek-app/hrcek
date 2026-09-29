from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import polib
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from hrcek.core.translations import catalogues, language_of


class Command(BaseCommand):
    help = "Say how complete each translation is. Never fails."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--github",
            action="store_true",
            help="Also write GitHub Actions warnings and a job summary.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        source = settings.LANGUAGE_CODE.split("-")[0]
        rows = []
        for root in settings.LOCALE_PATHS:
            for po in catalogues(Path(root)):
                language = language_of(po)
                if language == source:
                    # The source language translates to itself.
                    continue
                catalogue = polib.pofile(str(po))
                total = sum(1 for entry in catalogue if not entry.obsolete)
                rows.append(
                    (
                        po,
                        language,
                        total,
                        len(catalogue.untranslated_entries()),
                        len(catalogue.fuzzy_entries()),
                    )
                )

        if options["github"]:
            self._github(rows)
        for _po, language, total, untranslated, fuzzy in rows:
            self.stdout.write(
                _(
                    "%(language)s — total: %(total)d, untranslated: "
                    "%(untranslated)d, to review: %(fuzzy)d"
                )
                % {
                    "language": language,
                    "total": total,
                    "untranslated": untranslated,
                    "fuzzy": fuzzy,
                }
            )

    def _github(self, rows: list[tuple[Path, str, int, int, int]]) -> None:
        """Warnings annotate the run without failing it; the summary is
        the table on the run's page."""
        for po, language, _total, untranslated, fuzzy in rows:
            if untranslated or fuzzy:
                try:
                    where = po.relative_to(settings.BASE_DIR)
                except ValueError:
                    where = po
                self.stdout.write(
                    f"::warning file={where}::"
                    + _(
                        "%(language)s has %(untranslated)d untranslated "
                        "strings and %(fuzzy)d to review."
                    )
                    % {
                        "language": language,
                        "untranslated": untranslated,
                        "fuzzy": fuzzy,
                    }
                )
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary:
            return
        lines = [
            "| "
            + " | ".join(
                (_("Language"), _("Strings"), _("Untranslated"), _("To review"))
            )
            + " |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| {language} | {total} | {untranslated} | {fuzzy} |"
            for _po, language, total, untranslated, fuzzy in rows
        ]
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
