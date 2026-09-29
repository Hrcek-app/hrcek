# Contributing

## Before you start

Read [CLAUDE.md](../../CLAUDE.md). It is the working agreement, and it
is short.

## The definition of done

A change is finished when all of these hold:

- A failing test came first, and it now passes.
- `uv run pytest` passes **with no warnings**.
- `prek run --all-files` passes.
- Every new user-facing string is translatable, extracted, and
  translated into Slovenian — or knowingly left for later, which
  `translation_status` will keep pointing out.
- Every new error has a registered code and a row in
  [error-codes.md](error-codes.md).
- The affected pages in `docs/manual/` and `docs/dev/` are updated in
  the same change.
- If the diff exceeds 100 lines, `REVIEW_GUIDE.md` exists at the
  repository root, giving a reading order and pointing at what deserves
  scrutiny. It is gitignored and never committed.

## Commits

History is curated, not a work log. Build the change, verify it, then
make one meaningful commit. No `Co-Authored-By` or other attribution
trailers.

## Style

ruff formats and lints; it is not a matter of taste. Documentation wraps
at 80 characters, exceeded only where a break is impossible.
