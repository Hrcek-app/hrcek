# Debugging and telemetry

## Logs

Every log record is a single line of JSON with `timestamp`, `level`,
`logger`, `message` and `request_id`, plus `exception` when there is a
traceback. One line per record keeps logs greppable and parseable.

```bash
uv run python manage.py runserver | jq 'select(.level == "ERROR")'
```

That pipe only works if **every** line is JSON, which is why the
`django` logger is named explicitly in `LOGGING`:

```python
"django": {"handlers": ["console"], "level": "INFO", "propagate": False},
```

Django applies its own `DEFAULT_LOGGING` before the project's, and it
gives the `django` logger a plain-text console handler and a
`mail_admins` handler. A config that does not mention the logger keeps
both of those, and — because the logger still propagates — adds the
JSON handler from the root on top. One event was therefore printed
twice, once as text and once as JSON. Naming the logger replaces
Django's handlers with ours; `propagate: False` stops the second copy.

One event can still be reported by two *different* loggers, which is
not duplication: a rejected request has a reason
(`django.security.csrf`, "Origin checking failed …") and an outcome
(`django.request`, "Forbidden: /path"), and they say different things.
Both carry the same `request_id`, so they can be tied together.

## Request IDs

Each request gets an id, taken from an `X-Request-ID` header when the
caller supplies a well-formed one and generated otherwise. It is
returned on the response, attached to every log record, and tagged on
the Sentry scope — so a user's report of "it broke" leads to the exact
log lines and the exact Sentry event.

Supplied ids are accepted only if they match `[A-Za-z0-9._-]{1,64}`. The
value is echoed in a response header, so anything that could smuggle
header syntax is replaced rather than sanitised.

The id lives in a context variable for the life of the request, and is
also stamped on the request object. Both are needed: Django logs a
failing response in `BaseHandler.get_response`, **after** the
middleware chain has unwound, so by then `RequestIDMiddleware` has
reset the context variable. That record carries the request, so
`JSONFormatter` falls back to the id stamped there — which is why the
line reporting a failure, the one most worth correlating, still has an
id. Resetting the variable is kept: an id leaking into the next
request on a reused thread would be worse than none.

## SQL

```bash
HRCEK_DEBUG_SQL=1 uv run python manage.py runserver
```

## Attaching a debugger

```bash
DEBUGPY_ENABLE=1 uv run python manage.py runserver --noreload
```

Then attach your editor's debugger to `127.0.0.1:5678`. Any DAP-capable
client works — the project ships no editor configuration, so use
whatever your editor calls "attach to a running process".

Set `DEBUGPY_WAIT=1` to block startup until the debugger connects, which
is how you catch something that fails during boot. Use `--noreload`, or
the autoreloader will fight for the port.

## Sentry

Sentry is optional and off by default. Set `SENTRY_DSN` to enable it;
leave it empty and the SDK is never initialised, every `sentry_sdk` call
becomes a no-op, and nothing else changes. A test enforces exactly that.

`send_default_pii` is `False`. This project stores what a family reads,
and none of that should leave the machine as a side effect of an error
report.

Unexpected exceptions are reported explicitly from the API's catch-all
handler, because django-ninja handles them before Django's middleware
would see them.

## Error pages

With `DEBUG` off, Django renders `core/templates/404.html` and
`500.html` for pages; the API answers with its JSON errors instead.

- **404** extends `base.html`. It is neutral about why: Hrček answers
  404 for things that exist but are not yours, and the page must not
  hint otherwise.
- **500** stands alone. Django renders it with an empty context — no
  request, no user, no CSRF token — and the fault may be the database
  or a template, so it uses no navigation, forms or URL lookups. The
  language active for the request still applies.

A superuser can preview both at `/errors/404/` and `/errors/500/`;
nothing links there, since only a developer can change the pages. The
preview calls
Django's own `page_not_found` and `server_error` handlers, so it shows
exactly what a visitor gets, with the real status code, whatever
`DEBUG` is. Anyone else gets the ordinary 404.

`tests/core/error_urls.py` adds an address that always raises, which
`tests/core/test_error_pages.py` uses to reach the 500 page the way a
real fault does.
