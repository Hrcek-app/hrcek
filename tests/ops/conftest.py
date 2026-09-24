import pytest


@pytest.fixture(autouse=True)
def _ops_paths(settings, tmp_path):
    """Give every test its own history file and snapshot folder."""
    settings.HRCEK_RELEASES_FILE = tmp_path / "releases.json"
    settings.HRCEK_BACKUP_PATH = tmp_path / "backups"
    settings.HRCEK_RELEASE = "v2.0.0"
