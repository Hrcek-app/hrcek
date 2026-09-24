from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from hrcek.ops import history


def test_releases_lists_the_history_and_the_snapshots(settings):
    history.append("v1.0.0", "deploy", {})
    settings.HRCEK_BACKUP_PATH.mkdir()
    name = "20260924T100000.000000Z-v1.0.0-manual.sqlite3"
    (settings.HRCEK_BACKUP_PATH / name).write_bytes(b"")

    out = StringIO()
    call_command("releases", stdout=out)

    assert "v1.0.0" in out.getvalue()
    assert name in out.getvalue()


def test_releases_current_prints_only_the_release():
    history.append("v1.0.0", "deploy", {})
    out = StringIO()
    call_command("releases", "--current", stdout=out)
    assert out.getvalue() == "v1.0.0\n"


def test_releases_current_without_a_history_is_a_coded_error():
    with pytest.raises(CommandError, match="HRC-OPS-0008"):
        call_command("releases", "--current")
