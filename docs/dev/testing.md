# Testing

```bash
uv run pytest                          # everything
uv run pytest tests/core -v            # one directory
uv run pytest tests/test_api.py::test_health_endpoint_reports_ok
uv run pytest --cov=hrcek --cov-report=term-missing
```

## Test-driven development

Write the failing test first. Run it and confirm it fails for the reason
you expect — a test that has never failed has not been shown to test
anything. Then write the smallest code that makes it pass.

## Warnings are errors

The suite runs with `filterwarnings = ["error"]`. A `DeprecationWarning`
fails the run, which is the point: deprecations get fixed while they are
cheap.

**Never silence a warning.** No entries in `filterwarnings`, no
`-W ignore`, no `warnings.simplefilter`. If a warning cannot be fixed —
because it comes from a dependency with no upgrade available — stop and
ask the project owner. That decision is not a developer's to make alone.

## Browser tests

Tests that need a real browser — a script's behaviour, keyboard focus,
the same page with JavaScript off — live in `tests/browser/` and use
[pytest-playwright](https://playwright.dev/python/docs/test-runners).
Every module there carries `pytestmark = pytest.mark.browser`, and
`addopts` deselects that marker, so `uv run pytest` skips them and
stays fast. Run them on their own:

```bash
uv run playwright install chromium firefox webkit   # once, and after
                                                    # upgrading Playwright
uv run pytest -m browser                            # Chromium only
uv run pytest -m browser --browser chromium --browser firefox --browser webkit
uv run pytest -m browser --browser webkit --headed --slowmo 300
```

A later `-m` replaces the one in `addopts`, which is why `-m browser`
selects them.

**Fixtures** (`tests/browser/conftest.py`):

| Fixture | Gives you |
|---|---|
| `live_server` | pytest-django's: the app, served on a random port |
| `person` | a verified user, `nina@example.com` |
| `signed_in_page` | Playwright's `page`, signed in as `person` |
| `signed_in_page_without_js` | the same, in a context with JavaScript off |

Requesting `live_server` makes a test transactional, so data the test
creates is committed and the server sees it. The test database stays
the in-memory SQLite of the rest of the suite: pytest-django hands the
server thread the test's own connection, so no file database is needed.

Two details of the conftest are load-bearing:

- Playwright's sync API keeps an asyncio event loop running on the
  test's thread, and Django's ORM refuses to run under one.
  `DJANGO_ALLOW_ASYNC_UNSAFE` is set for the `tests/browser` package
  only, by a package-scoped fixture, never at import: a conftest is
  imported even when its tests are deselected, and setting it there
  would switch the check off for the whole suite.
- A session-scoped autouse fixture asks for `django_db_setup`, so the
  test database is created before Playwright starts its loop, and
  destroyed after it stops.

Sign a browser in with `client.force_login` and copy the session cookie
(see `_sign_in`) rather than typing into the sign-in form: it is
faster, and the sign-in form has tests of its own.

Prefer locators by role and accessible name (`get_by_role("button",
name="Keep it")`) to CSS selectors: they fail when the page stops
being accessible, not just when a class is renamed. Use `expect(…)`,
which waits, rather than asserting on a value read once.

In CI the **Browser tests** job runs after the main one, installs the
three browsers with their system libraries (`playwright install
--with-deps`) and runs all three. The image is only built once both
jobs pass.

## Coverage

Coverage is reported, not gated. A percentage target tends to produce
tests written for the number rather than for the risk.

## What the scaffolding tests guarantee

- Error codes are unique, well-formed, and carry translatable messages.
- Every failure path renders the same JSON shape, and the catch-all
  leaks neither exception text nor traceback.
- Slovenian actually resolves — the gettext pipeline is proven, not just
  configured.
- No model change is missing a migration.
- The application runs, and serves requests, with Sentry unconfigured.
- Every registered error code is documented.
- Deleting an entry works from the list's dialog, and from the
  confirmation page with JavaScript off, in Chromium, Firefox and
  WebKit.
