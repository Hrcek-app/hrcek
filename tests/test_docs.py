import hashlib
import re
from pathlib import Path

import pytest
from django.conf import settings

from hrcek.core import errors

CODE_RE = re.compile(r"HRC-[A-Z]{3,6}-\d{4}")
# Reserved by tests/core/test_errors.py; never shipped, never documented.
TEST_PREFIX = "HRC-TEST-"


def _reference() -> str:
    path = Path(settings.BASE_DIR) / "docs" / "dev" / "error-codes.md"
    return path.read_text(encoding="utf-8")


def _registered_codes_table() -> str:
    """Only the reference table counts.

    Prose elsewhere in the page uses illustrative codes that are not
    registered on purpose, so matching the whole file would be wrong.
    """
    text = _reference()
    heading = "## Registered codes"
    assert heading in text, f"{heading!r} section is missing"
    after = text.split(heading, 1)[1]
    return after.split("\n## ", 1)[0]


def test_every_registered_code_is_documented():
    table = _registered_codes_table()
    missing = sorted(
        code
        for code in errors.registry()
        if not code.startswith(TEST_PREFIX) and code not in table
    )
    assert missing == [], (
        f"Undocumented error codes: {missing}. "
        "Add them to the table in docs/dev/error-codes.md."
    )


def test_no_documented_code_has_been_removed():
    documented = set(CODE_RE.findall(_registered_codes_table()))
    stale = sorted(documented - set(errors.registry()))
    assert stale == [], (
        f"Documented codes that no longer exist: {stale}. "
        "Remove them from the table in docs/dev/error-codes.md."
    )


# The user manual: English is authoritative; every other language is a
# translation that has to keep up with it. See docs/dev/contributing.md.

MANUAL = Path(settings.BASE_DIR) / "docs" / "manual"
SOURCE_LANGUAGE = "en"
TRANSLATIONS = ["sl"]
SOURCE_RE = re.compile(r"<!-- translated from en/(\S+) at ([0-9a-f]{12}) -->")
FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def _pages(language: str) -> set[str]:
    return {p.name for p in (MANUAL / language).glob("*.md")}


def _outline(text: str) -> list[int]:
    """Heading levels in order, outside code blocks."""
    prose = FENCE_RE.sub("", text)
    return [len(m.group(1)) for m in re.finditer(r"^(#+) ", prose, re.M)]


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def test_the_manual_lives_in_language_folders():
    loose = sorted(p.name for p in MANUAL.iterdir() if p.is_file())
    assert loose == [], f"Move {loose} into docs/manual/<language>/."
    assert _pages(SOURCE_LANGUAGE), "docs/manual/en/ has no pages"


@pytest.mark.parametrize("language", TRANSLATIONS)
def test_every_translation_has_every_page(language):
    assert _pages(language) == _pages(SOURCE_LANGUAGE)


@pytest.mark.parametrize("language", TRANSLATIONS)
@pytest.mark.parametrize("page", sorted(_pages(SOURCE_LANGUAGE)))
def test_every_translated_page_is_of_the_current_english(language, page):
    source = (MANUAL / SOURCE_LANGUAGE / page).read_text(encoding="utf-8")
    translated = (MANUAL / language / page).read_text(encoding="utf-8")
    match = SOURCE_RE.search(translated)
    assert match, (
        f"{language}/{page} does not say which English it translates. "
        f"Add <!-- translated from en/{page} at "
        f"{_fingerprint(source)} --> on its first line."
    )
    assert match.group(1) == page
    assert match.group(2) == _fingerprint(source), (
        f"en/{page} has changed since {language}/{page} was translated. "
        f"Bring the translation up to date, then set its fingerprint to "
        f"{_fingerprint(source)}."
    )
    assert _outline(translated) == _outline(source), (
        f"{language}/{page} has a different set of headings from en/{page}"
    )
    assert sorted(CODE_RE.findall(translated)) == sorted(CODE_RE.findall(source)), (
        f"{language}/{page} names different error codes from en/{page}"
    )


@pytest.mark.parametrize("language", [SOURCE_LANGUAGE, *TRANSLATIONS])
def test_every_link_in_the_manual_leads_somewhere(language):
    broken = [
        f"{page.name}: {target}"
        for page in sorted((MANUAL / language).glob("*.md"))
        for target in LINK_RE.findall(page.read_text(encoding="utf-8"))
        if "://" not in target and not (page.parent / target).exists()
    ]
    assert broken == []
