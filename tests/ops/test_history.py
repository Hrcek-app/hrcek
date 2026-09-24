import json

import pytest

from hrcek.ops import history
from hrcek.ops.errors import OpsError


def test_an_absent_history_is_empty():
    assert history.load() == []
    assert history.current() is None


def test_appended_entries_survive_a_reload(settings):
    history.append("v1.0.0", "deploy", {"entries": "0004_entryimage"})
    history.append("v2.0.0", "deploy", {"entries": "0005_retire_price_field"})

    entries = history.load()
    assert [entry.release for entry in entries] == ["v1.0.0", "v2.0.0"]
    assert entries[0].migrations == {"entries": "0004_entryimage"}
    current = history.current()
    assert current is not None
    assert current.release == "v2.0.0"

    raw = json.loads(settings.HRCEK_RELEASES_FILE.read_text(encoding="utf-8"))
    assert raw[1]["kind"] == "deploy"
    assert raw[1]["recorded_at"].endswith("Z")


def test_appending_leaves_no_temporary_files_behind(settings):
    history.append("v1.0.0", "deploy", {})
    folder = settings.HRCEK_RELEASES_FILE.parent
    assert [path.name for path in folder.iterdir()] == ["releases.json"]


def test_find_returns_the_latest_entry_for_a_release():
    history.append("v1.0.0", "deploy", {})
    history.append("v2.0.0", "deploy", {})
    history.append("v1.0.0", "rollback", {})

    found = history.find("v1.0.0")
    assert found is not None
    assert found.kind == "rollback"
    assert history.find("v3.0.0") is None


@pytest.mark.parametrize(
    "content", ["not json", '{"release": "v1.0.0"}', '[{"release": "v1.0.0"}]']
)
def test_an_unreadable_history_is_a_coded_error(settings, content):
    settings.HRCEK_RELEASES_FILE.write_text(content, encoding="utf-8")
    with pytest.raises(OpsError) as excinfo:
        history.load()
    assert excinfo.value.error_code.code == "HRC-OPS-0006"


def test_a_history_that_cannot_be_written_is_a_coded_error(settings):
    folder = settings.HRCEK_RELEASES_FILE.parent / "locked"
    folder.mkdir()
    settings.HRCEK_RELEASES_FILE = folder / "releases.json"
    folder.chmod(0o500)
    try:
        with pytest.raises(OpsError) as excinfo:
            history.append("v1.0.0", "deploy", {})
    finally:
        folder.chmod(0o700)
    assert excinfo.value.error_code.code == "HRC-OPS-0012"
    assert list(folder.iterdir()) == []
