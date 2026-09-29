"""Compiled translation catalogues, built from the .po files.

The .po files are the source and are committed; the .mo files gettext
reads are derived from them, so they are built rather than committed:
by the Docker image build, and by the app itself as it starts, for a
deployment without the image. See docs/dev/i18n.md.

A catalogue is rebuilt only when its .mo is missing or does not match
its .po. Matching is by modification time, and the .mo is stamped with
exactly the .po's time when it is built, so any difference at all means
"rebuild" — not only a newer .po. That matters for copies that keep
each file's own time (rsync -a, tar): a changed .po can arrive looking
older than the .mo built from its predecessor.

Compiling is done here with polib rather than Django's compilemessages,
so a server needs no GNU gettext tools, only the Python dependencies.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

import polib
from django.conf import settings
from django.utils.translation.reloader import translation_file_changed

logger = logging.getLogger(__name__)

FUZZY = "fuzzy"


def catalogues(locale_root: Path) -> list[Path]:
    """Every .po under a locale directory, in a stable order."""
    return sorted(Path(locale_root).glob("*/LC_MESSAGES/*.po"))


def language_of(po: Path) -> str:
    """The language code a catalogue belongs to: locale/<code>/LC_MESSAGES."""
    return po.parent.parent.name


def is_fresh(po: Path) -> bool:
    """Whether the .mo beside ``po`` was built from it as it is now."""
    mo = po.with_suffix(".mo")
    return mo.exists() and mo.stat().st_mtime_ns == po.stat().st_mtime_ns


def compile_catalogue(po: Path, *, show_unreviewed: bool = False) -> None:
    """Build the .mo beside ``po``.

    Unreviewed ("fuzzy") entries are left out unless ``show_unreviewed``,
    so the page shows the English original rather than a guess. The file
    is written under a temporary name and moved into place, so a worker
    reading it, or another worker building it at the same moment, never
    sees half a catalogue.
    """
    catalogue = polib.pofile(str(po))
    if show_unreviewed:
        for entry in catalogue.fuzzy_entries():
            entry.flags.remove(FUZZY)

    mo = po.with_suffix(".mo")
    handle, temporary = tempfile.mkstemp(dir=mo.parent, prefix=".", suffix=".mo")
    os.close(handle)
    try:
        catalogue.save_as_mofile(temporary)
        source = po.stat()
        # A temporary file is owner-only. The image builds as root and
        # runs as another user, so the .mo takes its source's mode.
        os.chmod(temporary, source.st_mode & 0o777)
        os.utime(temporary, ns=(source.st_atime_ns, source.st_mtime_ns))
        os.replace(temporary, mo)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def compile_stale(locale_root: Path, show_unreviewed: Iterable[str] = ()) -> list[Path]:
    """Build every catalogue that is not fresh; return the ones built."""
    showing = set(show_unreviewed)
    built = []
    for po in catalogues(locale_root):
        if is_fresh(po):
            continue
        compile_catalogue(po, show_unreviewed=language_of(po) in showing)
        built.append(po)
    return built


def compile_all_stale() -> list[Path]:
    """Build every stale catalogue under the project's locale paths."""
    built = []
    for root in settings.LOCALE_PATHS:
        built += compile_stale(Path(root), settings.TRANSLATIONS_SHOWING_UNREVIEWED)
    return built


def compile_at_startup() -> None:
    """Build stale catalogues as the app starts, and never stop it.

    A server that cannot write its locale directory still starts; its
    pages are in English until the catalogues are built, and the log
    says so.
    """
    try:
        built = compile_all_stale()
    except OSError as exc:
        logger.warning(
            "Translation catalogues could not be compiled (%s); pages "
            "fall back to English. Run: python manage.py compile_translations",
            exc,
        )
        return
    if built:
        # Django loads the default language while it imports models,
        # before any app is ready, so a catalogue built just now may
        # already be cached as missing. The autoreloader's own hook for
        # a changed .mo clears those caches.
        translation_file_changed(sender=None, file_path=built[0].with_suffix(".mo"))
