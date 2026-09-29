# Hrček — working agreement

Hrček stores references to interesting content found on the web.
It is built for family-scale use: tens of users, not thousands. Prefer
the simple option; do not build for scale that will never arrive.

## Stack

Django 6.1, django-ninja, SQLite, Python 3.13. `uv` owns the virtual
environment; `pytest` runs the tests; `prek` runs the pre-commit hooks.

## Commands

| Purpose | Command |
|---|---|
| Install / sync deps | `uv sync` |
| Run the tests | `uv run pytest` |
| Run one test | `uv run pytest tests/path/test_x.py::test_y -v` |
| Django management | `uv run python manage.py <command>` |
| Lint and format | `uv run ruff format . && uv run ruff check --fix .` |
| Type check | `uv run ty check` |
| All hooks | `prek run --all-files` |
| Update translation catalogues | `uv run python manage.py update_translations` |
| Translation completeness | `uv run python manage.py translation_status` |

Never invoke `python`, `pip` or `pytest` directly — always through `uv`.

## How we work

**Test-driven.** Write the failing test first. Run it and confirm it
fails for the reason you expect. Then write the minimum code to pass.
A test that has never failed has not been shown to test anything.

**Commits are curated.** Do not commit after every step. Build the
change, verify it, then make one meaningful commit. Never add
`Co-Authored-By` or other attribution trailers to a commit message.

**Warnings are errors.** The suite runs with `filterwarnings = ["error"]`.
Fix the cause of a warning. **Never** silence one — no `filterwarnings`
entries, no `-W ignore`, no `warnings.simplefilter`. If a warning cannot
be fixed, stop and ask; do not decide alone.

## Non-negotiable rules

**Every user-facing string is translatable.** `gettext_lazy as _` at
module level, `gettext as _` inside functions. This covers error
messages, API text, validation messages and management command output.
A bare user-facing literal is a bug.

**Every error has a unique code.** Register it in the owning app's
`errors.py` with `register()`, in the form `HRC-<DOMAIN>-<NNNN>`. The
description is a lazy translatable string. Errors reach clients only as
`{"error": {"code", "message", "details"}}`. Never raise an ad-hoc
message to a client, and never let an exception escape untranslated.

**Documentation lines wrap at 80 characters.** Exceed only where a break
is impossible — long URLs, wide table rows.

**A task is not done until the docs are.** Update the affected pages in
`docs/manual/` (users) and `docs/dev/` (developers) in the same change.
New or changed error codes must be reflected in
`docs/dev/error-codes.md`; a test enforces this.

**Changes over 100 lines need a review guide.** Write `REVIEW_GUIDE.md`
at the repository root: the order to read the change in, and what
deserves a close look. It is gitignored and never committed.

## Layout

```
manage.py              Django entry point
src/hrcek/settings/    base, dev, test, prod, plus env helpers
src/hrcek/api.py       root NinjaAPI and exception handlers
src/hrcek/core/        cross-cutting app: errors, logging, telemetry
locale/                translations; .po is committed, .mo is built
tests/                 mirrors src/hrcek
docs/manual/           user manual
docs/dev/              developer documentation
```

`docs/superpowers/` holds working specs and plans and is gitignored.

## Translations

After changing any translatable string:

```bash
uv run python manage.py update_translations
# translate the new entries in locale/sl/LC_MESSAGES/django.po
```

Commit the `.po`. The `.mo` is never committed; the app builds it. A
commit hook runs `update_translations` and stops the commit if the
catalogues lagged the source. A translation you are not sure of gets
the `#, fuzzy` flag: it then shows in English until reviewed.
