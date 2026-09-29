"""update_translations, translation_status and compile_translations."""

import os
from io import StringIO
from pathlib import Path

import polib
import pytest
from django.core.management import CommandError, call_command

HEADER = {
    "Project-Id-Version": "hrcek",
    "POT-Creation-Date": "2026-01-01 00:00+0000",
    "Content-Type": "text/plain; charset=UTF-8",
}


@pytest.fixture
def project(tmp_path, settings):
    """A tiny project for makemessages to walk: one source string, and a
    Slovenian catalogue that already translates it."""
    settings.BASE_DIR = tmp_path
    settings.LOCALE_PATHS = [tmp_path / "locale"]
    (tmp_path / "app.py").write_text(
        'from django.utils.translation import gettext as _\n\n_("Saved.")\n'
    )
    po = polib.POFile()
    po.metadata = dict(HEADER)
    po.append(
        polib.POEntry(msgid="Saved.", msgstr="Shranjeno.", occurrences=[("app.py", "")])
    )
    path = tmp_path / "locale/sl/LC_MESSAGES/django.po"
    path.parent.mkdir(parents=True)
    po.save(str(path))
    # Settle the catalogue in makemessages' own layout first, so the
    # tests below start from a file it would not change.
    call_command("update_translations", stdout=StringIO())
    return tmp_path


def _po(project: Path) -> Path:
    return project / "locale/sl/LC_MESSAGES/django.po"


def _snapshot(path: Path):
    return path.read_bytes(), path.stat().st_mtime_ns


def _add_string(project: Path) -> None:
    (project / "app.py").write_text(
        "from django.utils.translation import gettext as _\n\n"
        '_("Saved.")\n_("Brand new.")\n'
    )


def test_new_strings_reach_the_catalogue(project):
    _add_string(project)
    call_command("update_translations", stdout=StringIO())
    catalogue = polib.pofile(str(_po(project)))
    assert catalogue.find("Brand new.") is not None
    assert catalogue.find("Saved.").msgstr == "Shranjeno."


def test_the_creation_date_does_not_churn(project):
    """makemessages restamps POT-Creation-Date on every run. Left alone,
    every branch in a stack would conflict on that one line."""
    _add_string(project)
    call_command("update_translations", stdout=StringIO())
    text = _po(project).read_text()
    assert '"POT-Creation-Date: 2026-01-01 00:00+0000\\n"' in text


def test_an_up_to_date_catalogue_is_not_touched(project):
    """Not rewritten, not even restamped: its compiled copy stays fresh."""
    before = _snapshot(_po(project))
    out = StringIO()
    call_command("update_translations", stdout=out)
    assert _snapshot(_po(project)) == before
    assert "up to date" in out.getvalue()


def test_check_reports_a_stale_catalogue_and_changes_nothing(project):
    _add_string(project)
    before = _snapshot(_po(project))
    with pytest.raises(CommandError, match="update_translations"):
        call_command("update_translations", check=True, stdout=StringIO())
    assert _snapshot(_po(project)) == before


def test_check_passes_when_nothing_would_change(project):
    out = StringIO()
    call_command("update_translations", check=True, stdout=out)
    assert "up to date" in out.getvalue()


@pytest.fixture
def catalogues(tmp_path, settings):
    """English (the source) and Slovenian with one of each kind of gap."""
    settings.LOCALE_PATHS = [tmp_path]
    settings.LANGUAGE_CODE = "en"
    for language, entries in {
        "en": [polib.POEntry(msgid="Saved.", msgstr="")],
        "sl": [
            polib.POEntry(msgid="Saved.", msgstr="Shranjeno."),
            polib.POEntry(msgid="Deleted.", msgstr=""),
            polib.POEntry(msgid="Kept.", msgstr="Obdržano.", flags=["fuzzy"]),
        ],
    }.items():
        po = polib.POFile()
        po.metadata = dict(HEADER)
        for entry in entries:
            po.append(entry)
        path = tmp_path / language / "LC_MESSAGES/django.po"
        path.parent.mkdir(parents=True)
        po.save(str(path))
    return tmp_path


def test_status_counts_what_is_missing_and_what_needs_review(catalogues):
    out = StringIO()
    call_command("translation_status", stdout=out)
    text = out.getvalue()
    assert "sl — total: 3, untranslated: 1, to review: 1" in text
    assert "en:" not in text, "the source language has nothing to translate"


def test_status_never_fails(catalogues):
    """Incomplete is a state to see, not a build to break."""
    call_command("translation_status", stdout=StringIO())


def test_status_speaks_github_when_asked(catalogues, tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    out = StringIO()
    call_command("translation_status", github=True, stdout=out)
    assert out.getvalue().startswith("::warning file=")
    assert "| sl | 3 | 1 | 1 |" in summary.read_text()


def test_compile_translations_builds_what_is_stale(catalogues):
    out = StringIO()
    call_command("compile_translations", stdout=out)
    assert (catalogues / "sl/LC_MESSAGES/django.mo").exists()
    assert "2" in out.getvalue()
    out = StringIO()
    call_command("compile_translations", stdout=out)
    assert "up to date" in out.getvalue()


def test_the_projects_catalogues_match_the_source():
    """The same check the commit hook runs, so CI cannot miss it."""
    before = os.getcwd()
    call_command("update_translations", check=True, stdout=StringIO())
    assert os.getcwd() == before, "the command must restore the directory"
