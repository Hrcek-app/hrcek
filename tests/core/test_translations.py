"""Compiled catalogues are built from the .po files, never committed."""

import gettext
import logging
import os
from pathlib import Path

import polib
import pytest
from django.conf import settings
from django.utils import translation

from hrcek.core import translations

HEADER = {
    "Content-Type": "text/plain; charset=UTF-8",
    "Plural-Forms": (
        "nplurals=4; plural=(n%100==1 ? 0 : n%100==2 ? 1 : "
        "n%100==3 || n%100==4 ? 2 : 3);"
    ),
}


def _catalogue(root: Path, language: str = "sl", *entries: polib.POEntry) -> Path:
    po = polib.POFile()
    po.metadata = HEADER
    for entry in entries or (polib.POEntry(msgid="Saved.", msgstr="Shranjeno."),):
        po.append(entry)
    path = root / language / "LC_MESSAGES" / "django.po"
    path.parent.mkdir(parents=True)
    po.save(str(path))
    return path


def _load(mo: Path) -> gettext.GNUTranslations:
    with mo.open("rb") as handle:
        return gettext.GNUTranslations(handle)


def test_a_catalogue_is_compiled_next_to_its_source(tmp_path):
    po = _catalogue(tmp_path)
    assert translations.compile_stale(tmp_path) == [po]
    assert _load(po.with_suffix(".mo")).gettext("Saved.") == "Shranjeno."


def test_plural_forms_survive_compiling(tmp_path):
    """Slovenian has four plural forms; the header carries the rule."""
    entry = polib.POEntry(
        msgid="%d entry",
        msgid_plural="%d entries",
        msgstr_plural={0: "%d vnos", 1: "%d vnosa", 2: "%d vnosi", 3: "%d vnosov"},
    )
    po = _catalogue(tmp_path, "sl", entry)
    translations.compile_stale(tmp_path)
    catalogue = _load(po.with_suffix(".mo"))
    assert [catalogue.ngettext("%d entry", "%d entries", n) for n in (1, 2, 3, 5)] == [
        "%d vnos",
        "%d vnosa",
        "%d vnosi",
        "%d vnosov",
    ]


def test_a_fresh_catalogue_is_left_alone(tmp_path):
    po = _catalogue(tmp_path)
    translations.compile_stale(tmp_path)
    mo = po.with_suffix(".mo")
    # Anything compiling again would overwrite this marker.
    stamp = mo.stat()
    mo.write_bytes(b"marker")
    os.utime(mo, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    assert translations.compile_stale(tmp_path) == []
    assert mo.read_bytes() == b"marker"


def test_an_edited_catalogue_is_compiled_again(tmp_path):
    po = _catalogue(tmp_path)
    translations.compile_stale(tmp_path)
    catalogue = polib.pofile(str(po))
    catalogue[0].msgstr = "Shranjeno!"
    catalogue.save()
    stamp = po.stat()
    os.utime(po, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))

    assert translations.compile_stale(tmp_path) == [po]
    assert _load(po.with_suffix(".mo")).gettext("Saved.") == "Shranjeno!"


def test_a_source_older_than_its_compiled_copy_still_counts_as_changed(tmp_path):
    """A deploy by rsync -a keeps each file's own time, so a newer .po
    can arrive looking older than the .mo built from its predecessor.
    Any difference means rebuild, not only "newer"."""
    po = _catalogue(tmp_path)
    translations.compile_stale(tmp_path)
    stamp = po.stat()
    os.utime(po, ns=(stamp.st_atime_ns, stamp.st_mtime_ns - 3_600_000_000_000))

    assert translations.compile_stale(tmp_path) == [po]


def test_unreviewed_translations_fall_back_to_english(tmp_path):
    entry = polib.POEntry(msgid="Saved.", msgstr="Shranjeno.", flags=["fuzzy"])
    po = _catalogue(tmp_path, "sl", entry)
    translations.compile_stale(tmp_path)
    assert _load(po.with_suffix(".mo")).gettext("Saved.") == "Saved."


def test_a_language_can_choose_to_show_unreviewed_translations(tmp_path):
    """For a language nobody here can review, a machine translation
    beats English until somebody who speaks it comes along."""
    entry = polib.POEntry(msgid="Saved.", msgstr="Gespeichert.", flags=["fuzzy"])
    po = _catalogue(tmp_path, "de", entry)
    translations.compile_stale(tmp_path, show_unreviewed=["de"])
    assert _load(po.with_suffix(".mo")).gettext("Saved.") == "Gespeichert."


def test_compiling_leaves_no_temporary_files(tmp_path):
    po = _catalogue(tmp_path)
    translations.compile_stale(tmp_path)
    assert sorted(p.name for p in po.parent.iterdir()) == ["django.mo", "django.po"]


def test_startup_compiles_what_is_missing(tmp_path, settings):
    settings.LOCALE_PATHS = [tmp_path]
    po = _catalogue(tmp_path)
    translations.compile_at_startup()
    assert po.with_suffix(".mo").exists()


def test_startup_carries_on_when_it_cannot_write(tmp_path, settings, caplog):
    """A read-only install still starts; its pages are in English until
    somebody runs compile_translations, and the log says why."""
    settings.LOCALE_PATHS = [tmp_path]
    po = _catalogue(tmp_path)
    po.parent.chmod(0o555)
    try:
        with caplog.at_level(logging.WARNING, logger="hrcek.core.translations"):
            translations.compile_at_startup()
    finally:
        po.parent.chmod(0o755)
    assert not po.with_suffix(".mo").exists()
    assert "compile_translations" in caplog.text


@pytest.mark.django_db
def test_the_projects_catalogues_are_compiled_and_fresh():
    """The app compiles its catalogues as it starts, so by the time any
    test runs, every one of them is built and current."""
    locale_root = Path(settings.LOCALE_PATHS[0])
    stale = [
        str(po)
        for po in translations.catalogues(locale_root)
        if not translations.is_fresh(po)
    ]
    assert translations.catalogues(locale_root)
    assert stale == []


def test_a_compiled_catalogue_is_as_readable_as_its_source(tmp_path):
    """Built as root in the image, read as the app's own user: the .mo
    must not inherit a temporary file's owner-only mode."""
    po = _catalogue(tmp_path)
    po.chmod(0o644)
    translations.compile_stale(tmp_path)
    assert po.with_suffix(".mo").stat().st_mode & 0o777 == 0o644


def test_a_catalogue_loaded_before_it_was_built_is_reloaded(tmp_path, settings):
    """Django loads the default language while it imports models,
    before any app is ready; without a reload, a first start would
    keep that empty catalogue for the life of the process."""
    settings.LOCALE_PATHS = [tmp_path]
    _catalogue(tmp_path)
    with translation.override("sl"):
        assert translation.gettext("Saved.") == "Saved."
    translations.compile_at_startup()
    with translation.override("sl"):
        assert translation.gettext("Saved.") == "Shranjeno."
