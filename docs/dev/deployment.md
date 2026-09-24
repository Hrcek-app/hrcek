# Deployment

Hrček is built for family-scale use: one container, one SQLite file, a
reverse proxy in front. There is no queue, no cache server and no
orchestration, and there should not be.

## The image

`ghcr.io/samastur/hrcek`, public, for `linux/amd64` and `linux/arm64`.

| Tag | Points at |
|---|---|
| `vX.Y.Z` | A release. Pin to one of these. |
| `latest` | The newest release. |
| `main` | The newest green commit on `main`. Not a release. |
| `sha-<short>` | One commit on `main`. |

The container serves plain HTTP on port 8000 and keeps everything it
must not lose in `/data`. It runs as uid 10001 unless told otherwise.

```bash
docker run -d --name hrcek -p 127.0.0.1:8000:8000 -v "$PWD/data:/data" \
    --env-file .env ghcr.io/samastur/hrcek:v1.0.0
```

## Configuration

Everything comes from the environment; `deploy/env.example` lists it.

| Variable | Required | Meaning |
|---|---|---|
| `HRCEK_SECRET_KEY` | yes | Django's secret key. Long and random. |
| `HRCEK_ALLOWED_HOSTS` | yes | Comma-separated host names it answers to. |
| `HRCEK_BASE_URL` | yes | The address people reach; every email link uses it. |
| `HRCEK_SMTP_HOST` | yes | Outgoing mail server. |
| `HRCEK_SMTP_PORT`, `_USER`, `_PASSWORD`, `_USE_TLS` | no | SMTP details. |
| `HRCEK_FROM_EMAIL` | no | Sender address. |
| `HRCEK_PROXY_COUNT` | behind a proxy | How many proxies to believe. `1` behind nginx. |
| `HRCEK_BACKUP_KEEP` | no | Snapshots kept, default 10. |
| `HRCEK_BACKUP_PATH` | no | Snapshot folder, default `/data/backups`. |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | no | Error reporting. |

`HRCEK_RELEASE` is set by the image to its tag; do not override it.
The image also sets `DJANGO_SETTINGS_MODULE=hrcek.settings.prod`, which
refuses to start without the required variables and turns `/api/docs`
off.

## The data folder

```
data/
  db.sqlite3            the database; with -wal and -shm beside it
  releases.json         which release ran, at which migrations
  backups/              snapshots, newest HRCEK_BACKUP_KEEP kept
  media/                rendered image cache; safe to delete
```

**Back up `data/backups/`**, not `db.sqlite3`: every file in it is a
complete, consistent database. Take a fresh one whenever you like:

```bash
docker compose exec app python manage.py backup
```

Copying `db.sqlite3` with `cp` while the app runs can capture a torn
write. Never put `data/` on a network filesystem (NFS, SMB): SQLite's
WAL mode needs local locking.

## What happens at start

With no command, the container:

1. Refuses to start if the database has migrations it does not know —
   a newer release ran here (`HRC-OPS-0001`).
2. Snapshots the database, if this release differs from the last one
   recorded and the database is not empty, then prunes old snapshots.
3. Migrates.
4. Records the release in `releases.json`.
5. Starts gunicorn: one process, four threads. One process on
   purpose — the token-exchange throttle counts in process memory.

`docker compose run --rm app manage.py <command>` runs a management
command with none of those steps. The ops commands are `backup`,
`check_schema`, `record_release`, `release_plan`, `rollback_to`,
`restore` and `releases`.

`/healthz` answers `ok` when the database does. The image's health
check uses it; it bypasses the HTTPS redirect and host check so that a
probe from inside the container works.

## Running it with compose

`deploy/` holds a reference setup: `compose.yaml`, `env.example`,
`deploy.sh` and `nginx.conf.example`. Copy the first three to a folder
on the host (for example `/srv/hrcek`), rename `env.example` to `.env`
and fill it in.

- **Rootless Docker:** uncomment `user: "0:0"` in `compose.yaml`. The
  container's root is your own user, so `data/` belongs to you.
- **Rootful Docker:** leave it out and `chown 10001:10001 data`.

## The reverse proxy

`deploy/nginx.conf.example` is a complete site: TLS from certbot,
forwarding headers, and rate limits on sign-in. Set
`HRCEK_PROXY_COUNT=1` when a proxy is in front, or HTTPS redirects loop
and every visitor shares one rate-limit allowance.

**Hrček does no rate limiting of its own for sign-in, and it must be
provided in front of it.** Sign-in, signup and password reset are all
guessable, and nothing in the application counts attempts. Counting
means writing to a single-writer SQLite database on every failed
login, which contends with real traffic to defend against an attack a
family-scale service is unlikely to face. The proxy does it for
nothing. Caddy has `rate_limit`; with neither, `fail2ban` watching the
access log does the same job.

## Deploying, rolling back, restoring

`deploy.sh` drives compose. It keeps the tag in `.env` as `HRCEK_TAG`.

```bash
./deploy.sh v1.4.0                 # deploy, or roll back (see below)
./deploy.sh status                 # history and snapshots
./deploy.sh restore <snapshot>     # put a snapshot back
```

**Forward.** Pull, switch the tag, start, wait up to
`HRCEK_HEALTH_TIMEOUT` seconds (default 90) for `/healthz`. If the new
release never becomes healthy, the script stops it, restores the
snapshot it took before migrating, starts the previous release again,
and exits non-zero. That is safe because the failed release served
nobody. A release that keeps failing and restarting takes that
snapshot once, on its first start, so the restore always goes back to
the database from before.

**Rollback.** Naming a release that already ran here, at fewer
migrations than now, is a rollback. The script stops the app, and the
*current* image — the only one that knows how to reverse its own
migrations — snapshots the database, migrates down to what the older
release recorded, and records the rollback. Then the older release
starts. If migrating down fails partway, the snapshot is put back
(`HRC-OPS-0011`) — a reversal may already have dropped data — and the
current release is restarted. If the older release fails to become
healthy, nothing is undone automatically, since it may have served
writes; `status` lists the `pre-rollback` snapshot to restore.

A release you rolled back *from* is newer than the code now running,
so naming it again deploys it forward.

**Restore.** Stops the app, copies the snapshot over the database, and
starts the release whose data the snapshot holds (it is in the name:
`<time>-<release>-<reason>.sqlite3`). Anything written after the
snapshot is lost. If the name is mistyped, nothing is copied and the
app is started again as it was.

Only one of these runs at a time; a second is refused. The script's
own messages are in English: they are for whoever runs the host, and
shell has no catalogue to translate them from.

## Migrations must be reversible

A rollback is only as good as the reverse of every migration it
crosses. `tests/test_migrations.py` migrates each app to zero and back
on a fresh database, so a `RunPython` without `reverse_code` fails the
suite. Write the reverse when you write the migration.

## Email

Production sends through SMTP, configured with `HRCEK_SMTP_HOST`,
`HRCEK_SMTP_PORT`, `HRCEK_SMTP_USER`, `HRCEK_SMTP_PASSWORD` and
`HRCEK_SMTP_USE_TLS`, and `HRCEK_FROM_EMAIL` as the sender.

`HRCEK_BASE_URL` must be the address people actually reach, because
every link in every email is built from it. Get it wrong and invitations
and password resets point somewhere useless.

## The first account

```bash
docker compose exec app python manage.py createsuperuser
```

It asks for an email address and a password and nothing else, and marks
the account confirmed, since nobody could send a confirmation email to
the very first user. Everyone after that arrives by invitation or
through the allowlist.

## Without Docker

The image is a convenience, not a requirement. On a bare host:

```bash
uv sync --locked --no-dev
DJANGO_SETTINGS_MODULE=hrcek.settings.prod uv run python manage.py migrate
uv run gunicorn --config docker/gunicorn.conf.py hrcek.wsgi:application
```

The ops commands work the same way through `uv run python manage.py`.
