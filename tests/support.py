"""Run manage.py in a separate process, against a throwaway database.

The suite's own database is in memory and shared by every test. Some
behaviour — migrating down, copying the database file, restoring it —
only means anything against a real file, and would wreck the shared
database if done in-process. Those tests use this instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings


def run_manage(
    *args: str,
    data_dir: Path,
    env: dict[str, str] | None = None,
    settings_module: str = "hrcek.settings.dev",
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": settings_module,
        "HRCEK_DB_PATH": str(data_dir / "db.sqlite3"),
        "HRCEK_MEDIA_PATH": str(data_dir / "media"),
        "HRCEK_BACKUP_PATH": str(data_dir / "backups"),
        "DEBUGPY_ENABLE": "0",
        "SENTRY_DSN": "",
        **(env or {}),
    }
    manage = Path(settings.BASE_DIR) / "manage.py"
    result = subprocess.run(  # noqa: S603  (fixed argv, no shell)
        [sys.executable, "-W", "error", str(manage), *args],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"manage.py {' '.join(args)} exited {result.returncode}\n"
            f"--- stdout\n{result.stdout}\n--- stderr\n{result.stderr}"
        )
    return result
