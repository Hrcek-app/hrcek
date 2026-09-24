from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import call_command

from tests.support import run_manage

PROJECT_APPS = sorted(
    config.label
    for config in apps.get_app_configs()
    if config.name.startswith("hrcek.") and (Path(config.path) / "migrations").is_dir()
)


# makemigrations checks migration history against the database, so this
# needs database access even though it never touches a model.
@pytest.mark.django_db
def test_no_missing_migrations():
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out, verbosity=1)
    except SystemExit:
        # Not pytest.fail(): ty cannot see through the decorator pytest
        # wraps it in, and reports a false positive on the call.
        raise AssertionError(
            "Model changes are not reflected in migrations. Run:\n"
            "  uv run python manage.py makemigrations\n\n"
            f"{out.getvalue()}"
        ) from None


# A migration without a reverse makes every rollback past it
# impossible, and nobody finds out until the day they need one.
@pytest.mark.parametrize("app", PROJECT_APPS)
def test_every_migration_can_be_reversed(tmp_path, app):
    run_manage("migrate", "--no-input", data_dir=tmp_path)
    run_manage("migrate", app, "zero", "--no-input", data_dir=tmp_path)
    run_manage("migrate", "--no-input", data_dir=tmp_path)
