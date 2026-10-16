import sys
from datetime import date
from types import SimpleNamespace

import pytest

from app.services import access_read_service as service
from app.services.access_read_service import (
    AccessReadError,
    inspect_access_schema,
    inspect_access_table,
    listar_controles_access,
    listar_recepciones_recientes_access,
    obtener_control_access,
)


def test_inspect_access_requires_configured_path(monkeypatch):
    monkeypatch.delenv("ACCESS_DB_PATH", raising=False)
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            access_db_path=None, access_table_name="CONTROL DE RECEPCION"
        ),
    )

    with pytest.raises(AccessReadError, match="ACCESS_DB_PATH"):
        inspect_access_table()


def test_inspect_access_rejects_unknown_table(tmp_path):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()

    with pytest.raises(AccessReadError, match="no está permitida"):
        inspect_access_table(path=str(database_path), table_name="OtraTabla")


def test_inspect_access_schema_returns_all_table_keys_and_relationships(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()
    connection_strings = []

    class FakeCursor:
        def tables(self):
            return [
                SimpleNamespace(
                    table_name="CONTROL DE RECEPCION", table_type="SYNONYM"
                ),
                SimpleNamespace(table_name="Detalle Control", table_type="SYNONYM"),
                SimpleNamespace(table_name="MSysObjects", table_type="SYSTEM TABLE"),
            ]

        def columns(self, *, table):
            if table == "CONTROL DE RECEPCION":
                return [
                    SimpleNamespace(
                        column_name="ID_INT",
                        type_name="INTEGER",
                        column_size=4,
                        nullable=0,
                        ordinal_position=1,
                    )
                ]
            return [
                SimpleNamespace(
                    column_name="ID_INT",
                    type_name="INTEGER",
                    column_size=4,
                    nullable=0,
                    ordinal_position=1,
                ),
                SimpleNamespace(
                    column_name="Cota",
                    type_name="VARCHAR",
                    column_size=100,
                    nullable=1,
                    ordinal_position=2,
                ),
            ]

        def primaryKeys(self, *, table):
            column = "ID_INT" if table == "CONTROL DE RECEPCION" else "ID_DETALLE"
            return [
                SimpleNamespace(column_name=column, key_seq=1, pk_name=f"PK_{table}")
            ]

        def foreignKeys(self, *, foreignTable):
            if foreignTable != "Detalle Control":
                return []
            return [
                SimpleNamespace(
                    pktable_name="CONTROL DE RECEPCION",
                    pkcolumn_name="ID_INT",
                    fkcolumn_name="ID_INT",
                    key_seq=1,
                    fk_name="FK_DETALLE_CONTROL",
                )
            ]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    def fake_connect(connection_string):
        connection_strings.append(connection_string)
        return FakeConnection()

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(access_db_path=None),
    )
    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=fake_connect))

    result = inspect_access_schema(path=str(database_path))

    assert result["tablas_visibles"] == ["CONTROL DE RECEPCION", "Detalle Control"]
    assert result["inventario"]["CONTROL DE RECEPCION"]["tipo_objeto"] == "SYNONYM"
    assert (
        result["inventario"]["CONTROL DE RECEPCION"]["clave_primaria"][0]["nombre"]
        == "ID_INT"
    )
    assert result["inventario"]["Detalle Control"]["claves_foraneas"][0] == {
        "tabla_referenciada": "CONTROL DE RECEPCION",
        "columna_referenciada": "ID_INT",
        "columna_local": "ID_INT",
        "orden": 1,
        "restriccion": "FK_DETALLE_CONTROL",
    }
    assert len(result["inventario"]["Detalle Control"]["columnas"]) == 2
    assert "ReadOnly=1;" in connection_strings[0]


def test_inspect_access_schema_preserves_columns_when_driver_lacks_key_metadata(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()

    class FakeCursor:
        def tables(self):
            return [
                SimpleNamespace(table_name="CONTROL DE RECEPCION", table_type="SYNONYM")
            ]

        def columns(self, **_kwargs):
            return [
                SimpleNamespace(
                    column_name="ID_INT",
                    type_name="INTEGER",
                    column_size=4,
                    nullable=0,
                    ordinal_position=1,
                )
            ]

        def primaryKeys(self, *, table):
            raise RuntimeError("SQLPrimaryKeys not supported")

        def foreignKeys(self, *, foreignTable):
            raise RuntimeError("SQLForeignKeys not supported")

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(access_db_path=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(
            connect=lambda _connection_string: FakeConnection(),
            Error=RuntimeError,
        ),
    )

    result = inspect_access_schema(path=str(database_path))
    table = result["inventario"]["CONTROL DE RECEPCION"]

    assert [column["nombre"] for column in table["columnas"]] == ["ID_INT"]
    assert table["clave_primaria"] == []
    assert table["claves_foraneas"] == []
    assert table["metadatos_no_disponibles"] == [
        "clave_primaria",
        "claves_foraneas",
    ]
    assert len(result["advertencias"]) == 2


def test_listar_controles_access_parametriza_busqueda_y_cursor(monkeypatch, tmp_path):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()
    calls = []

    class FakeCursor:
        description = [("ID_INT",), ("Material",)]

        def execute(self, query, params):
            calls.append((query, params))

        def fetchall(self):
            return [(900, "Material")]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(access_db_path=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(connect=lambda _connection_string: FakeConnection()),
    )

    rows = listar_controles_access(
        q="%' OR 1=1 --", before_id=1000, limit=20, path=str(database_path)
    )

    query, parameters = calls[0]
    assert rows == [{"ID_INT": 900, "Material": "Material"}]
    assert "SELECT TOP 20" in query
    assert "[ID_INT] < ?" in query
    assert "[Material] LIKE ?" in query
    assert parameters[0] == 1000
    assert parameters[1] == "%\u0025' OR 1=1 --%"
    assert "SELECT TOP 20" in query


def test_obtener_control_access_consulta_cotas_por_fk_confirmada(monkeypatch, tmp_path):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()
    calls = []

    class FakeCursor:
        description = [("ID_INT",), ("Estado",)]
        query_index = 0

        def execute(self, query, params):
            calls.append((query, params))
            self.query_index += 1
            if self.query_index == 2:
                self.description = [("Id",), ("ID_CDR",), ("COTA",)]

        def fetchone(self):
            return (1001, "ACEPTADO")

        def fetchall(self):
            return [(701, 1001, "Diámetro")]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(access_db_path=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(connect=lambda _connection_string: FakeConnection()),
    )

    result = obtener_control_access(1001, path=str(database_path))

    assert result["ID_INT"] == 1001
    assert result["controles"] == [{"Id": 701, "ID_CDR": 1001, "COTA": "Diámetro"}]
    assert calls[1][1] == [1001]
    assert "[ID_CDR] = ?" in calls[1][0]


def test_listar_controles_access_filtra_desde_hasta_inclusivo(monkeypatch, tmp_path):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()
    calls = []

    class FakeCursor:
        description = [("ID_INT",)]

        def execute(self, query, params):
            calls.append((query, params))

        def fetchall(self):
            return []

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(access_db_path=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(connect=lambda _connection_string: FakeConnection()),
    )

    listar_controles_access(
        desde=date(2026, 10, 1),
        hasta=date(2026, 10, 31),
        path=str(database_path),
    )

    query, params = calls[0]
    assert "[Fecha Control] >= ?" in query
    assert "[Fecha Control] < ?" in query
    assert params == [date(2026, 10, 1), date(2026, 11, 1)]


def test_listar_controles_access_rechaza_rango_invertido():
    with pytest.raises(ValueError, match="Desde no puede ser posterior"):
        listar_controles_access(
            desde=date(2026, 11, 1),
            hasta=date(2026, 10, 1),
        )


def test_listar_recepciones_recientes_access_usa_proveedor_de_control(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "recepciones.accdb"
    database_path.touch()
    calls = []

    class FakeCursor:
        description = [("ID_INT",), ("PROVEEDOR",)]

        def execute(self, query, params):
            calls.append((query, params))

        def fetchall(self):
            return [(1001, "Proveedor Access")]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(access_db_path=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(connect=lambda _connection_string: FakeConnection()),
    )

    rows = listar_recepciones_recientes_access(
        q="Proveedor Access",
        proveedor_codigo="P-100",
        limit=20,
        path=str(database_path),
    )

    query, parameters = calls[0]
    assert rows == [{"ID_INT": 1001, "PROVEEDOR": "Proveedor Access"}]
    assert "[Codigo Proveedor] = ?" in query
    assert "[PROVEEDOR] LIKE ?" in query
    assert parameters == [
        "P-100",
        "%Proveedor Access%",
        "%Proveedor Access%",
        "%Proveedor Access%",
        "%Proveedor Access%",
        "%Proveedor Access%",
        "%Proveedor Access%",
        "%Proveedor Access%",
        "%Proveedor Access%",
    ]
