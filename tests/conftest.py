import pytest


@pytest.fixture(autouse=True)
def db_temporal(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "PANEL_TOKEN", "secreto")
