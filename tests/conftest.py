import pytest


@pytest.fixture(autouse=True)
def _own_files(tmp_path, monkeypatch):
    """Tests never read or write the real settings file or the real Projects folder."""
    monkeypatch.setenv("RUNSPRITERUN_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("RUNSPRITERUN_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
