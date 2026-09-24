"""What the database has applied, compared with what this code knows."""

from __future__ import annotations

from django.db import connection
from django.db.migrations.loader import MigrationLoader


def _loader() -> MigrationLoader:
    return MigrationLoader(connection, ignore_no_migrations=True)


def applied_leaves() -> dict[str, str]:
    """The newest applied migration of each app.

    "Newest" is by the graph, not by name: an applied migration none of
    whose same-app children is applied.
    """
    loader = _loader()
    applied = set(loader.applied_migrations or {})
    leaves: dict[str, str] = {}
    for key in applied:
        node = loader.graph.node_map.get(key)
        if node is None:
            continue
        if not any(
            child.key in applied and child.key[0] == key[0] for child in node.children
        ):
            leaves[key[0]] = key[1]
    return dict(sorted(leaves.items()))


def unknown_applied() -> list[str]:
    """Applied migrations with no file on disk: a newer release ran here.

    Compared with the files, not the graph, so a squashed migration's
    replaced originals still count as known.
    """
    loader = _loader()
    return sorted(
        f"{app}.{name}"
        for app, name in (loader.applied_migrations or {})
        if (app, name) not in loader.disk_migrations
    )
