# Hrček

<p align="center">
  <img src="src/hrcek/core/static/img/hrcek.png" alt="" width="160">
</p>

Hrček — a simple bookmark manager with wish lists.

A small, self-hosted service for saving links to things you find on the
web. Gather them into collections, share those by link or publicly, and
turn any of them into a wish list your family can mark gifts off
without spoiling the surprise. Built for family-scale use: SQLite, one
process, no moving parts you have to babysit.

**NOTE: This is intended to be a usable experiment. Its author plans
to use it, but it is also a learning project for tools and processes
with corresponding lack of any guarantees.**

## Status

Early, but usable. Accounts work — invitations, gated self-signup,
email confirmation, password reset, and API authentication by session
or bearer token. People save entries with labels, their own custom
fields and a picture, from the web, the API, the
[browser extension](https://github.com/Hrcek-app/hrcek-extension) or
the [iOS app](https://github.com/Hrcek-app/hrcek-ios). They gather
entries into collections — by hand or by label — and keep each one
private, share it by link or make it public, with a feed. Any of them
can become a wish list. The interface is in English and
Slovenian.

## Documentation

- User manual: [English](docs/manual/en/index.md),
  [slovenščina](docs/manual/sl/index.md)
- [Developer documentation](docs/dev/index.md)
- [API guide](docs/dev/api.md) — for building a client
- [Working agreement](CLAUDE.md)

## Quick start

```bash
uv sync
uv run pytest
uv run python manage.py runserver
```

Requires [uv](https://docs.astral.sh/uv/) and GNU gettext. See
[development setup](docs/dev/development-setup.md).

## Running it

With Docker:

```bash
mkdir data && cp deploy/env.example .env   # then fill in .env
docker run -d -p 127.0.0.1:8000:8000 -v "$PWD/data:/data" \
    --env-file .env ghcr.io/hrcek-app/hrcek:latest
```

`data/` must be writable by uid 10001, the user the image runs as. Put
a TLS-terminating proxy in front.

It runs just as well without Docker, from a checkout with `uv` under
systemd. Both routes — and upgrades, rollback and backups — are in
[docs/dev/deployment.md](docs/dev/deployment.md).

## Licence

See [LICENSE](LICENSE).
