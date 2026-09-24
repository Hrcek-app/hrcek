# Architecture

## Layout

| Path | Responsibility |
|---|---|
| `manage.py` | Django entry point; starts the debugger when asked |
| `src/hrcek/settings/` | `base`, `dev`, `test`, `prod`, and `env` helpers |
| `src/hrcek/api.py` | Root `NinjaAPI`; turns failures into responses |
| `src/hrcek/urls.py` | Mounts the API at `/api/` |
| `src/hrcek/core/` | Cross-cutting app: errors, logging, telemetry |
| `src/hrcek/accounts/` | Identity: users, sign-in, invitations, email, account pages |
| `src/hrcek/entries/` | What Hrček stores: entries, tags and fields |
| `src/hrcek/collections/` | Named sets of entries, private or shared |
| `src/hrcek/ops/` | Release bookkeeping: snapshots, history, rollback. See [deployment](deployment.md) |
| `locale/` | Translation catalogues; `.po` and `.mo` are committed |
| `tests/` | Mirrors `src/hrcek/` |

Django apps are direct children of `hrcek`, so `INSTALLED_APPS` reads
`hrcek.core`. The `src/` layout means the package is installed in
editable mode by `uv sync`, which keeps imports unambiguous.

## Request path

1. `RequestIDMiddleware` assigns or accepts an id and puts it on the
   logging context and the Sentry scope.
2. `LocaleMiddleware` negotiates the language from `Accept-Language`.
3. Authentication runs: bearer token first, then session. See
   [accounts](accounts.md) for why that order is not arbitrary.
4. django-ninja routes to an operation.
5. Anything raised is caught by a handler in `hrcek/api.py` and rendered
   as a registered error code, translated into the negotiated language.

## Why these choices

**SQLite with WAL.** One small writer and a handful of readers. WAL lets
reads proceed during a write; `IMMEDIATE` takes the write lock up front
rather than failing partway through a transaction.

**A central error registry.** Codes must be unique and messages must be
translatable. Enforcing both at the point of registration — and again in
the test suite — makes the guarantee structural rather than cultural.

**Sentry, optional.** The application must run unchanged with no DSN.
Reporting is an enhancement, and the tests hold it to that.

**One exception handler.** django-ninja catches exceptions before
Django's middleware sees them, so every failure is shaped in one place
in `hrcek/api.py` rather than scattered across views.
