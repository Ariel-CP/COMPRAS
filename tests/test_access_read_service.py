import pytest

from app.services.access_read_service import AccessReadError, inspect_access_table


def test_inspect_access_requires_configured_path(monkeypatch):
    monkeypatch.delenv("ACCESS_DB_PATH", raising=False)

    with pytest.raises(AccessReadError, match="ACCESS_DB_PATH"):
        inspect_access_table()


def test_inspect_access_rejects_unknown_table(tmp_path):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()

    with pytest.raises(AccessReadError, match="no está permitida"):
        inspect_access_table(path=str(database_path), table_name="OtraTabla")