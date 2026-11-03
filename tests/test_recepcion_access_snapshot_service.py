import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import recepcion_access_snapshot_service as service


def test_preparar_version_conserva_identidad_relacion_y_datos_originales():
    version = service.preparar_version_origen(
        "CRD",
        {
            "Id": 701,
            "ID_CDR": 1001,
            "COTA": "Diámetro",
            "Medicion": Decimal("12.50"),
            "Fecha": date(2026, 10, 16),
        },
    )

    raw = json.loads(version["datos_originales"])
    assert version["id_origen"] == "701"
    assert version["id_padre_origen"] == "1001"
    assert raw["Medicion"] == "12.50"
    assert raw["Fecha"] == "2026-10-16"
    assert len(version["contenido_hash"]) == 64


def test_preparar_version_rechaza_tabla_o_identidad_no_confirmada():
    with pytest.raises(ValueError, match="no está habilitada"):
        service.preparar_version_origen("Detalle Control", {"N_INT": 1001})
    with pytest.raises(ValueError, match="ID_INT es requerido"):
        service.preparar_version_origen("CONTROL DE RECEPCION", {"PLANO": 476})


def test_lector_access_usa_conexion_readonly(monkeypatch, tmp_path):
    access_file = tmp_path / "recepciones.accdb"
    access_file.touch()
    connection_strings = []
    queries = []

    class FakeCursor:
        description = [("ID_INT",), ("Estado",)]

        def __init__(self):
            self.returned = False

        def execute(self, query):
            queries.append(query)

        def fetchmany(self, _size):
            if self.returned:
                return []
            self.returned = True
            return [(10, "ACEPTADO")]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    def fake_import_module(name):
        assert name == "pyodbc"

        def connect(connection_string):
            connection_strings.append(connection_string)
            return FakeConnection()

        return SimpleNamespace(connect=connect)

    monkeypatch.setattr(service, "import_module", fake_import_module)
    rows = list(
        service.leer_filas_access(access_file, "CONTROL DE RECEPCION", fetch_size=50)
    )

    assert rows == [{"ID_INT": 10, "Estado": "ACEPTADO"}]
    assert "ReadOnly=1;" in connection_strings[0]
    assert queries == ["SELECT * FROM [CONTROL DE RECEPCION]"]


class FakeResult:
    def __init__(self, lastrowid=None):
        self.lastrowid = lastrowid


class FakeSession:
    def __init__(self):
        self.next_run_id = 1
        self.versions = {}
        self.runs = {}
        self.commits = 0

    def execute(self, statement, params=None):
        sql = str(statement)
        if "INSERT INTO recepcion_access_import_run" in sql:
            run_id = self.next_run_id
            self.next_run_id += 1
            self.runs[run_id] = {"estado": "EN_PROCESO"}
            return FakeResult(lastrowid=run_id)
        if "INSERT INTO recepcion_access_source_version" in sql:
            for row in params:
                identity = (
                    row["fuente"],
                    row["tabla_origen"],
                    row["id_origen"],
                    row["contenido_hash"],
                )
                if identity not in self.versions:
                    self.versions[identity] = dict(row)
                else:
                    self.versions[identity]["corrida_id"] = row["corrida_id"]
            return FakeResult()
        if "UPDATE recepcion_access_import_run" in sql:
            self.runs[params["id"]] = dict(params)
            return FakeResult()
        raise AssertionError(f"SQL inesperado: {sql}")

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None


def test_import_snapshot_es_idempotente_y_conserva_version_editada(
    monkeypatch, tmp_path
):
    access_file = tmp_path / "recepciones.accdb"
    access_file.touch()
    rows = {
        "CONTROL DE RECEPCION": [{"ID_INT": 1001, "PLANO": 476, "Estado": "ACEPTADO"}],
        "CRD": [{"Id": 701, "ID_CDR": 1001, "COTA": "Diámetro", "ACEPTADO": True}],
        "CRD-ORI": [],
    }
    monkeypatch.setattr(
        service,
        "leer_filas_access",
        lambda _path, table, *, fetch_size: iter(rows[table]),
    )
    db = FakeSession()

    first = service.importar_snapshot_access(
        db,
        path=str(access_file),
        usuario_id=9,
        tablas=("CONTROL DE RECEPCION", "CRD"),
        batch_size=1,
    )
    second = service.importar_snapshot_access(
        db,
        path=str(access_file),
        usuario_id=9,
        tablas=("CONTROL DE RECEPCION", "CRD"),
        batch_size=1,
    )

    rows["CONTROL DE RECEPCION"][0]["Estado"] = "RECHAZADO"
    third = service.importar_snapshot_access(
        db,
        path=str(access_file),
        usuario_id=9,
        tablas=("CONTROL DE RECEPCION", "CRD"),
        batch_size=1,
    )

    assert first["registros_leidos"] == 2
    assert second["estado"] == "COMPLETADA"
    assert len(db.versions) == 3
    control_versions = [
        version
        for identity, version in db.versions.items()
        if identity[1] == "CONTROL DE RECEPCION"
    ]
    assert len(control_versions) == 2
    assert {
        json.loads(version["datos_originales"])["Estado"]
        for version in control_versions
    } == {
        "ACEPTADO",
        "RECHAZADO",
    }
    assert db.runs[first["corrida_id"]]["estado"] == "COMPLETADA"
    assert db.runs[second["corrida_id"]]["estado"] == "COMPLETADA"
    assert db.runs[third["corrida_id"]]["estado"] == "COMPLETADA"


def test_snapshot_sin_clave_marca_corrida_fallida(monkeypatch, tmp_path):
    access_file = tmp_path / "recepciones.accdb"
    access_file.touch()
    monkeypatch.setattr(
        service,
        "leer_filas_access",
        lambda *_args, **_kwargs: iter([{"PLANO": 476}]),
    )
    db = FakeSession()

    with pytest.raises(ValueError, match="ID_INT es requerido"):
        service.importar_snapshot_access(
            db,
            path=str(access_file),
            usuario_id=9,
            tablas=("CONTROL DE RECEPCION",),
        )

    assert db.runs[1]["estado"] == "FALLIDA"
    assert not db.versions
