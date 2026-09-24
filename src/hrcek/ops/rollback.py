"""Which way a release lies, and migrating down to one.

Only the *newer* code knows how to reverse its own migrations, so a
rollback runs in the current release before the older one starts.
"""

from __future__ import annotations

from typing import Literal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from hrcek.ops import history, schema, snapshots
from hrcek.ops.errors import (
    RELEASE_IS_CURRENT,
    RELEASE_IS_NEWER,
    RELEASE_NOT_RECORDED,
    ROLLBACK_FAILED,
    OpsError,
)

Direction = Literal["current", "forward", "rollback"]
Target = tuple[str, str | None]


def _targets(
    entry: history.Release, executor: MigrationExecutor
) -> list[Target] | None:
    """Per-app targets for *entry*, or None when it is newer than this code.

    An app the entry has no migrations for goes to zero (None).
    """
    graph = executor.loader.graph
    targets: list[Target] = []
    for app in sorted(executor.loader.migrated_apps):
        name = entry.migrations.get(app)
        if name is not None and (app, name) not in graph.nodes:
            return None
        targets.append((app, name))
    return targets


def direction(release: str) -> Direction:
    current = history.current()
    if current is not None and current.release == release:
        return "current"
    entry = history.find(release)
    if entry is None:
        return "forward"
    executor = MigrationExecutor(connection)
    targets = _targets(entry, executor)
    if targets is None:
        return "forward"
    plan = executor.migration_plan(targets)
    if any(backwards for _migration, backwards in plan):
        return "rollback"
    return "forward"


def rollback_to(release: str) -> snapshots.Snapshot:
    current = history.current()
    if current is not None and current.release == release:
        raise OpsError(RELEASE_IS_CURRENT, release=release)
    entry = history.find(release)
    if entry is None:
        raise OpsError(RELEASE_NOT_RECORDED, release=release)
    executor = MigrationExecutor(connection)
    targets = _targets(entry, executor)
    if targets is None:
        raise OpsError(RELEASE_IS_NEWER, release=release)

    snapshot = snapshots.take("pre-rollback")
    executor.loader.check_consistent_history(connection)
    # One call with every target, as `migrate` itself does: the recorded
    # state is consistent, so Django orders cross-app dependencies.
    try:
        executor.migrate(targets, plan=executor.migration_plan(targets))
    except Exception as exc:
        # Each reversal commits on its own, so a failure partway leaves
        # some reversed, and a reversal may have dropped data that
        # migrating forward again would not bring back. Put it all back.
        snapshots.restore(snapshot)
        raise OpsError(
            ROLLBACK_FAILED, release=release, snapshot=snapshot.path.name
        ) from exc
    # Recorded here, not when the older release starts: from now on the
    # data is that release's, so its startup must neither snapshot it
    # under the newer release's name nor record it a second time.
    history.append(release, "rollback", schema.applied_leaves())
    return snapshot
