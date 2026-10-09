# Deployment

Hrček is built for family-scale use: one process, one SQLite file, a
reverse proxy in front. There is no queue, no cache server and no
orchestration, and there should not be.

There are two ways to run it, and they share almost everything:

- **[With Docker](#with-docker)** — a ready-made image, a deploy script
  that handles upgrades and rollbacks, and
  [deploys from GitHub](#deploying-from-github).
- **[Without Docker](#without-docker)** — a checkout, `uv` and a
  service manager such as systemd.

Both keep the same data folder, take the same snapshots and roll back
the same way, because that work is done by Hrček's own management
commands, not by Docker.

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
| `HRCEK_BACKUP_PATH` | no | Snapshot folder, default `backups/` beside the database. |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | no | Error reporting. |

The image sets four more itself. Without Docker, you set them:

| Variable | Value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `hrcek.settings.prod` |
| `HRCEK_DB_PATH` | Where the database lives, e.g. `/srv/hrcek-data/db.sqlite3` |
| `HRCEK_MEDIA_PATH` | The image cache, e.g. `/srv/hrcek-data/media` |
| `HRCEK_RELEASE` | The release being run, e.g. `v1.4.0` |

Production settings refuse to start without the required variables and
turn `/api/docs` off.

## The data folder

Everything that must not be lost sits in one folder: `/data` in the
container, or wherever `HRCEK_DB_PATH` points without it.

```
data/
  db.sqlite3            the database; with -wal and -shm beside it
  releases.json         which release ran, at which migrations
  backups/              snapshots, newest HRCEK_BACKUP_KEEP kept
  media/                rendered image cache; safe to delete
```

**Back up `backups/`**, not `db.sqlite3`: every file in it is a
complete, consistent database. Take a fresh one whenever you like with
`manage.py backup` (each route below shows how to run it).

Copying `db.sqlite3` with `cp` while the app runs can capture a torn
write. Never put the folder on a network filesystem (NFS, SMB):
SQLite's WAL mode needs local locking.

## Releases, snapshots and rollback

Every start of a release goes through the same steps, whichever route
you use:

1. `manage.py check_schema` refuses the database if it has migrations
   this release does not know — a newer release ran here
   (`HRC-OPS-0001`).
2. `manage.py backup --reason pre-release --if-new-release --prune`
   snapshots the database if this release differs from the last one
   recorded, then prunes old snapshots.
3. `manage.py migrate` migrates.
4. `manage.py record_release` records the release in `releases.json`.
5. The app starts: gunicorn, one process, four threads. One process on
   purpose — the token-exchange throttle counts in process memory.

Going back to an earlier release runs `manage.py rollback_to <release>`
with the **newer** code first: only the newer code knows how to reverse
its own migrations. It snapshots the database, migrates down to what
the older release recorded, and records the rollback. If migrating
down fails partway, it puts the snapshot back (`HRC-OPS-0011`) — a
reversal may already have dropped data. Only then does the older code
start.

`manage.py restore <snapshot>` copies a snapshot over the database, with
the app stopped. The snapshot's name says which release's data it
holds: `<time>-<release>-<reason>.sqlite3`. `manage.py releases` lists
the history and the snapshots.

`/healthz` answers `ok` when the database does. It bypasses the HTTPS
redirect and host check, so a probe from the same machine works.

### Migrations must be reversible

A rollback is only as good as the reverse of every migration it
crosses. `tests/test_migrations.py` migrates each app to zero and back
on a fresh database, so a `RunPython` without `reverse_code` fails the
suite. Write the reverse when you write the migration.

## The reverse proxy

`deploy/nginx.conf.example` is a complete site: TLS from certbot,
forwarding headers, and rate limits on sign-in. It suits both routes;
both listen on `127.0.0.1:8000`. Set `HRCEK_PROXY_COUNT=1` when a proxy
is in front, or HTTPS redirects loop and every visitor shares one
rate-limit allowance.

**Hrček does no rate limiting of its own for sign-in, and it must be
provided in front of it.** Sign-in, signup and password reset are all
guessable, and nothing in the application counts attempts. Counting
means writing to a single-writer SQLite database on every failed
login, which contends with real traffic to defend against an attack a
family-scale service is unlikely to face. The proxy does it for
nothing. Caddy has `rate_limit`; with neither, `fail2ban` watching the
access log does the same job.

## Files at the site root

`/robots.txt` is a plain file in `src/hrcek/core/site_root/`. Anything
else that must sit at the root of the site goes in the same folder.
WhiteNoise serves it before the request reaches sessions, the database
or any view, and answers a repeat visit with `304 Not Modified`.
`WHITENOISE_ROOT` and `WHITENOISE_ADD_HEADERS_FUNCTION` in `base.py`
point at the folder and let browsers and proxies keep its files for a
day; WhiteNoise's own default for them is a minute. The proxy needs no
setup of its own for these files.

Only production runs WhiteNoise, so `runserver` answers `/robots.txt`
with a 404.

`robots.txt` keeps crawlers out of everything that is not public: the
admin, accounts, entries, private collections, collections shared by
link (`/c/`), the API, the error previews, the language switch and
`/healthz`. It leaves open only the front page and public collections
(`/u/`).

Blocking `/c/` has a cost. Those pages also send
`X-Robots-Tag: noindex`, which a crawler kept out never reads. A search
engine that finds a `/c/` link elsewhere may still list the bare
address, though not the page's content.

A new top-level address must be added to `robots.txt` or declared
crawlable in `tests/core/test_robots.py`; that test fails until
somebody chooses.

## With Docker

### The image

`ghcr.io/hrcek-app/hrcek`, public, for `linux/amd64` and `linux/arm64`.

| Tag | Points at |
|---|---|
| `vX.Y.Z` | A release. Pin to one of these. |
| `latest` | The newest release. |
| `main` | The newest green commit on `main`. Not a release. |
| `sha-<short>` | One commit on `main`. |

The container serves plain HTTP on port 8000, keeps its state in
`/data`, and runs the start steps above on every start. It runs as uid
10001 unless told otherwise.

```bash
docker run -d --name hrcek -p 127.0.0.1:8000:8000 -v "$PWD/data:/data" \
    --env-file .env ghcr.io/hrcek-app/hrcek:v1.0.0
```

`docker compose run --rm app manage.py <command>` runs a management
command with none of the start steps; inside a running container, use
`docker compose exec app python manage.py <command>`.

### Running it with compose

`deploy/` holds a reference setup: `compose.yaml`, `env.example`,
`deploy.sh` and `nginx.conf.example`. Copy the first three to a folder
on the host (for example `/srv/hrcek`), rename `env.example` to `.env`
and fill it in.

- **Rootless Docker:** uncomment `user: "0:0"` in `compose.yaml`. The
  container's root is your own user, so `data/` belongs to you.
- **Rootful Docker:** leave it out and `chown 10001:10001 data`.

### Deploying, rolling back, restoring

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
migrations than now, is a rollback. The script stops the app, runs
`rollback_to` in the current image, then starts the older release. If
migrating down fails, the current release is restarted. If the older
release fails to become healthy, nothing is undone automatically,
since it may have served writes; `status` lists the `pre-rollback`
snapshot to restore.

A release you rolled back *from* is newer than the code now running,
so naming it again deploys it forward.

**Restore.** Stops the app, copies the snapshot over the database, and
starts the release whose data the snapshot holds. Anything written
after the snapshot is lost. If the name is mistyped, nothing is copied
and the app is started again as it was.

Only one of these runs at a time; a second is refused. The script's
own messages are in English: they are for whoever runs the host, and
shell has no catalogue to translate them from.

## Deploying from GitHub

This builds on the Docker route: GitHub publishes the image, then asks
the host to run `deploy.sh`.

`.github/workflows/ci.yml` is one pipeline:

| Job | Runs on | Does |
|---|---|---|
| `test` | every push and PR | hooks and the test suite |
| `image` | every push and PR | builds, smoke-tests, and on a push publishes |
| `deploy` | `v*` tags; or by hand | SSHes to the host and runs the release |

Pull requests build the image but never publish it or see a secret; no
job uses `pull_request_target`. Actions are pinned to commit SHAs.

### Cutting a release

1. Bump `version` in `pyproject.toml` on `main`.
2. Tag that commit `v` + the version and push the tag. `image` refuses
   a tag that does not match.

The image, Sentry's release and `releases.json` then all use that tag.

### Rolling back from GitHub

Actions → CI → Run workflow, with the tag to go back to. It runs the
same `deploy.sh`, which sees the release ran before and migrates down.

### One-time setup

On the host, as the user that runs Docker:

1. Copy `deploy/compose.yaml`, `deploy/deploy.sh` (as `deploy`) and
   `deploy/env.example` (as `.env`, mode 600) to, say, `/srv/hrcek`,
   and `mkdir data`. Fill in `.env`.
2. Add the nginx site from `deploy/nginx.conf.example`; get its
   certificate with `certbot --nginx`.
3. Make a key for GitHub: `ssh-keygen -t ed25519 -N '' -f hrcek-deploy`.
   Add the public half to `~/.ssh/authorized_keys` locked to the
   script:

   ```
   command="/srv/hrcek/deploy --ssh",restrict ssh-ed25519 AAAA… github-deploy
   ```

   A stolen key can then only deploy one of the published images. It
   cannot open a shell or run anything else.
4. Record the host key: `ssh-keyscan -t ed25519 <host>`, adding
   `-p <port>` if SSH does not listen on 22.
5. Check the lock: start `./deploy vX.Y.Z` in one shell and run it
   again in another; the second must say `Another deploy is running.`

On GitHub:

1. Settings → Environments → New `production`. Deployment branches and
   tags: `main` (for the Run workflow button) and `v*`. Optionally,
   require your review.
2. Add its secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (the
   private half) and `DEPLOY_KNOWN_HOSTS` (the `ssh-keyscan` line),
   plus `DEPLOY_PORT` if SSH does not listen on 22. Delete the private
   key file from the host afterwards.
3. Settings → Rules → New tag ruleset for `v*`, restricting creation to
   maintainers.
4. After the first push to `main`, make the `hrcek` package public
   (Packages → hrcek → Package settings), so the host can pull without
   logging in.
5. Push the first tag. Then create the first account:
   `docker compose exec app python manage.py createsuperuser`.

## Without Docker

### Installing

Check out a release tag and install it:

```bash
git clone https://github.com/Hrcek-app/hrcek.git /srv/hrcek
cd /srv/hrcek
git checkout v1.0.0
uv sync --locked --no-dev
```

Put the configuration in an environment file, e.g. `/srv/hrcek.env`,
mode 600: everything from [Configuration](#configuration), including
the four variables the image would otherwise set. Keep the data folder
outside the checkout, so a `git clean` can never reach it.

`DJANGO_SETTINGS_MODULE` must be in the real environment: `manage.py`
chooses development settings before it reads a `.env` file. For shell
commands, load the file first:

```bash
set -a; . /srv/hrcek.env; set +a
```

Every command below assumes that, and is run from `/srv/hrcek`.

### Starting

The same steps the container runs, then the server. `collectstatic` is
needed because the app serves its own static files.

The compiled translation catalogues (`.mo`) are not in the checkout.
The app builds them as it starts, and again after an upgrade changes a
`.po` file, so `/srv/hrcek/locale` must be writable by the user the
app runs as. If it cannot write there, the app still starts, logs a
warning, and shows its pages in English until somebody runs
`uv run python manage.py compile_translations` with the right
permissions. Building them needs nothing beyond the Python
dependencies; GNU gettext is not required on the server.

```bash
uv run python manage.py collectstatic --no-input
uv run python manage.py check_schema
uv run python manage.py backup --reason pre-release --if-new-release --prune
uv run python manage.py migrate --no-input
uv run python manage.py record_release
uv run gunicorn --config docker/gunicorn.conf.py --bind 127.0.0.1:8000 \
    hrcek.wsgi:application
```

`--bind` overrides the container's `0.0.0.0`, so only the proxy can
reach it. Under systemd, the environment file becomes
`EnvironmentFile=/srv/hrcek.env`, the first five commands become
`ExecStartPre=` lines, and gunicorn is `ExecStart=`.

### Upgrading

Set `HRCEK_RELEASE` in the environment file to the new tag as part of
the upgrade: the snapshot and the history are named after it, and
without a new name no snapshot is taken.

```bash
git fetch --tags && git checkout v1.4.0
uv sync --locked --no-dev
# set HRCEK_RELEASE=v1.4.0 in /srv/hrcek.env, then restart the service
```

Restarting runs the start steps, which snapshot, migrate and record the
release.

### Rolling back

Stop the service. Then, with the **newer** release still checked out
and its environment loaded:

```bash
uv run python manage.py rollback_to v1.3.2
git checkout v1.3.2 && uv sync --locked --no-dev
# set HRCEK_RELEASE=v1.3.2 in /srv/hrcek.env, then start the service
```

If `rollback_to` fails, the database has been put back and the newer
release can simply be started again.

### Restoring

With the service stopped:

```bash
uv run python manage.py restore <snapshot>
```

Then check out the release the snapshot's name gives, set
`HRCEK_RELEASE` to it, and start the service.

## Email

Production sends through SMTP, configured with `HRCEK_SMTP_HOST`,
`HRCEK_SMTP_PORT`, `HRCEK_SMTP_USER`, `HRCEK_SMTP_PASSWORD` and
`HRCEK_SMTP_USE_TLS`, and `HRCEK_FROM_EMAIL` as the sender.

`HRCEK_BASE_URL` must be the address people actually reach, because
every link in every email is built from it. Get it wrong and invitations
and password resets point somewhere useless.

## The first account

```bash
# With Docker
docker compose exec app python manage.py createsuperuser
# Without Docker
uv run python manage.py createsuperuser
```

It asks for an email address and a password and nothing else, and marks
the account confirmed, since nobody could send a confirmation email to
the very first user. Everyone after that arrives by invitation or
through the allowlist.
