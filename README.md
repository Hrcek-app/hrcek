# Hrček

<p align="center">
  <img src="src/hrcek/core/static/img/hrcek.png" alt="" width="160">
</p>

Hrček — a tool for saving interesting online content.

A small, self-hosted service for storing references to things you find
on the web. Built for family-scale use: SQLite, one process, no moving
parts you have to babysit.

**NOTE: This is intended to be a usable experiment. Its author plans
to use it, but it is also a learning project for tools and processes
with corresponding lack of any guarantees.**

## Status

Early. Accounts work — invitations, gated self-signup, email
confirmation, password reset, and API authentication by session or
bearer token. People can manage their own display name, email address,
password and API tokens, and save entries with tags, their own custom
fields and a picture from the web or the API. Shared collections are
still to come.

## Documentation

- [User manual](docs/manual/index.md)
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

## Run with Docker

```bash
mkdir data && cp deploy/env.example .env   # then fill in .env
docker run -d -p 127.0.0.1:8000:8000 -v "$PWD/data:/data" \
    --env-file .env ghcr.io/samastur/hrcek:latest
```

`data/` must be writable by uid 10001, the user the image runs as. Put
a TLS-terminating proxy in front. Deploying, rollback and backups are
in [docs/dev/deployment.md](docs/dev/deployment.md).

## Licence

See [LICENSE](LICENSE).
