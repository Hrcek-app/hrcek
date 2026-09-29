# Development setup

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — manages Python and dependencies
- GNU gettext — `makemessages` (behind `update_translations`) shells
  out to it. Only needed when strings change; the app compiles its
  catalogues without it
  - macOS: `brew install gettext`
  - Debian/Ubuntu: `sudo apt-get install gettext`
- [prek](https://github.com/j178/prek) — runs the git hooks
- [Tailwind CSS standalone CLI](https://tailwindcss.com/blog/standalone-cli)
  — only needed when changing styles; see [styling](styling.md)
  - macOS: `brew install tailwindcss`

## First run

```bash
uv sync
uv tool install prek
prek install
uv run pytest
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

`createsuperuser` asks only for an email address and a password, and the
account it makes is confirmed immediately — nobody could send a
confirmation email to the very first user.

The API is then at `http://127.0.0.1:8000/api/`, with interactive
documentation at `/api/docs` and a health check at `/api/health`.

## Configuration

Settings read the environment, optionally seeded from a `.env` file at
the repository root. Real environment variables always win, so a stray
file cannot surprise a deployment.

| Variable | Default | Meaning |
|---|---|---|
| `HRCEK_SECRET_KEY` | — | Required in production; dev and test use a fixed non-secret |
| `HRCEK_DEBUG` | `false` | Django debug mode |
| `HRCEK_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `HRCEK_DB_PATH` | `db.sqlite3` | SQLite file location |
| `HRCEK_MEDIA_PATH` | `media/` | Where rendered image copies are cached; disposable |
| `HRCEK_DEBUG_SQL` | `false` | Log every query |
| `HRCEK_TOKEN_EXCHANGE_RATE` | `10/h` | Limit on `POST /api/auth/tokens/exchange`, per calling address |
| `HRCEK_TOKEN_EXCHANGE_ACCOUNT_RATE` | `10/h` | The same limit, counted per account named in the request |
| `HRCEK_PROXY_COUNT` | `0` | Reverse proxies in front; 0 ignores forwarding headers. Set to 1 behind nginx or Caddy |
| `HRCEK_API_DOCS` | `true` | Serve `/api/docs`; forced off in production |
| `HRCEK_BASE_URL` | `http://localhost:8000` | Absolute links in email are built from this |
| `HRCEK_FROM_EMAIL` | `hrcek@localhost` | Sender address |
| `HRCEK_INVITATION_EXPIRY_DAYS` | `7` | Invitation lifetime |
| `HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS` | `48` | Confirmation lifetime |
| `HRCEK_SMTP_HOST`, `HRCEK_SMTP_PORT`, `HRCEK_SMTP_USER`, `HRCEK_SMTP_PASSWORD`, `HRCEK_SMTP_USE_TLS` | — | Production mail, via `MAILERS` |
| `SENTRY_DSN` | empty | Empty disables Sentry entirely |
| `SENTRY_ENVIRONMENT` | `development` | Tags reported events |
| `SENTRY_TRACES_SAMPLE_RATE` | `1.0` | Trace sampling |
| `DEBUGPY_ENABLE` | `false` | Start a debugpy listener |
| `DEBUGPY_PORT` | `5678` | Port for that listener |
| `DEBUGPY_WAIT` | `false` | Block until a debugger attaches |

`.env` is gitignored. Never commit real secrets.

## Editor

No editor configuration is committed. Debugging works from any editor:
`DEBUGPY_ENABLE=1` opens a plain debugpy port to attach to. See
[debugging and telemetry](debugging-and-telemetry.md).
