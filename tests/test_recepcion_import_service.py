from app.services import recepcion_access_import_service as service


class FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class FakeSession:
    def __init__(self):
        self.executed = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        sql = str(statement)
        if "SELECT id FROM recepcion_staging" in sql:
            return FakeResult(None)
        return FakeResult()

    def commit(self):
        return None


def test_import_recepcion_desde_access_uses_sqlalchemy_session(monkeypatch):
    fake_db = FakeSession()
    monkeypatch.setattr(service, "get_db", lambda: iter([fake_db]))
    monkeypatch.setattr(
        service,
        "leer_tabla_access",
        lambda ruta_accdb, tabla_nombre="CONTROL DE RECEPCION": [
            {
                "ID_INT": 1001,
                "PROVEEDOR": "Proveedor Test",
                "Material": "Producto Test",
                "CANTIDAD OC": "10.50",
                "Fecha Control": "2026-09-17",
                "Estado": "ACEPTADO",
                "Lote": "2000",
                "Codigo Proveedor": 42,
                "NOTA": "Importado desde prueba",
                "Controlo": "Juan",
                "TieneCertificado": True,
            }
        ],
    )

    result = service.importar_recepcion_desde_access(
        ruta_accdb="C:/tmp/test.accdb",
        usuario_id=42,
        tabla_nombre="CONTROL DE RECEPCION",
    )

    assert result["exitoso"] is True
    assert result["nuevas_insertadas"] == 1
    assert result["duplicadas"] == 0
    assert result["errores"] == 0
    assert result["errores_detalle"] == []


def test_mapear_campos_access_a_staging_uses_real_access_column_names():
    fila = {
        "ID_INT": 1001,
        "PROVEEDOR": "Proveedor Test",
        "Codigo Proveedor": 42,
        "Material": "CHAPA TERNIUM 2.5x1000x2000",
        "CANTIDAD OC": "10.50",
        "Fecha Control": "2026-09-17",
        "Estado": "ACEPTADO",
        "Lote": "2000",
        "Controlo": "Juan",
        "NOTA": "Corte 2.5 x 1000 x 2000 - hoja de chapa",
        "TieneCertificado": True,
        "PLANO": "2188",
    }

    mapped = service.mapear_campos_access_a_staging(fila)

    assert mapped["id_recepcion_original"] == 1001
    assert mapped["proveedor_codigo"] == 42
    assert mapped["proveedor_nombre"] == "Proveedor Test"
    assert mapped["producto_nombre"] == "CHAPA TERNIUM"
    assert mapped["producto_codigo"] == "10NIP2188"
    assert mapped["cantidad_solicitada"] == service.Decimal("10.50")
    assert mapped["fecha_recepcion_original"] == service.date(2026, 9, 17)
    assert mapped["estado_inspeccion_original"] == "ACEPTADO"
    assert mapped["lote_numero"] == "2000"
    assert mapped["inspector_nombre"] == "Juan"
    assert "2.5 x 1000 x 2000" in mapped["notas_adicionales"]
