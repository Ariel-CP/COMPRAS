from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import recepcion_recomendacion_service as service


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row

    def mappings(self):
        return FakeRows(self.row.staging_rows)


class FakeDb:
    def __init__(self, rows):
        self.provider = SimpleNamespace(
            codigo="0559", nombre="DEMAPOL SRL", staging_rows=rows
        )
        self.statements = []

    def execute(self, query, params):
        self.statements.append(str(query))
        if "SELECT codigo, nombre FROM proveedor" in str(query):
            assert params == {"id": 17}
            return FakeResult(self.provider)
        return FakeResult(self.provider)


def _row(code, control_date, lot, state, name="DEMAPOL SRL"):
    return {
        "id_recepcion_original": "1",
        "proveedor_codigo": code,
        "proveedor_nombre": name,
        "fecha_recepcion_original": control_date,
        "lote_numero": lot,
        "estado_inspeccion_original": state,
    }


@pytest.mark.parametrize(
    ("rejected_count", "total_count", "expected_level"),
    [
        (0, 20, "Simplificada"),
        (1, 20, "Normal"),
        (6, 100, "Estricta"),
    ],
)
def test_recomendar_nivel_aplica_umbral_anual_por_entregas(
    rejected_count, total_count, expected_level
):
    rows = [
        _row("0559", date(2026, 2, 26), "100", "RECHAZADO")
        for _ in range(rejected_count)
    ]
    rows.extend(
        _row("559", datetime(2026, 2, 25), "100", "ACEPTADO")
        for _ in range(total_count - rejected_count)
    )
    rows.extend(
        [
            _row("0559", date(2026, 3, 1), "900", "ANULADO"),
            _row("0559", date(2025, 9, 1), "500", "RECHAZADO"),
        ]
    )
    db = FakeDb(rows)

    result = service.recomendar_nivel_inspeccion(
        db, 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["nivel_recomendado"] == expected_level
    assert result["aceptados"] == total_count - rejected_count
    assert result["rechazados"] == rejected_count
    assert result["total_entregas"] == total_count
    assert result["registros_evaluados"] == total_count
    assert result["desde"] == date(2026, 1, 1)
    assert result["hasta"] == date(2026, 10, 19)
    assert "pg-4.10.01 v17" in result["origen"].casefold()
    assert "FROM recepcion_staging" in db.statements[1]
    assert result["porcentaje_entregas_rechazadas"] == (
        Decimal(rejected_count) / Decimal(total_count) * Decimal("100")
    )


def test_recomendar_nivel_sin_historial_importado():
    result = service.recomendar_nivel_inspeccion(
        FakeDb([]), 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["estado"] == "SIN_HISTORIAL"
    assert result["nivel_recomendado"] is None


def test_recomendar_nivel_bloquea_registros_importados_incompletos():
    db = FakeDb(
        [
            _row(None, None, "120", "ACEPTADO"),
            _row("0559", date(2026, 2, 25), "100", "ACEPTADO"),
        ]
    )

    result = service.recomendar_nivel_inspeccion(
        db, 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["estado"] == "HISTORIAL_INCOMPLETO"
    assert result["registros_incompletos"] == 1
    assert result["nivel_recomendado"] is None
    assert "reimportá el historial" in str(result["mensaje"]).casefold()


def test_recomendar_nivel_bloquea_legacy_sin_id_dentro_del_periodo():
    row = _row("0559", date(2026, 2, 25), "100", "ACEPTADO")
    row["id_recepcion_original"] = None

    result = service.recomendar_nivel_inspeccion(
        FakeDb([row]), 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["estado"] == "HISTORIAL_INCOMPLETO"
    assert result["registros_legacy_sin_identidad_en_periodo"] == 1
    assert result["nivel_recomendado"] is None


def test_recomendar_nivel_excluye_legacy_sin_id_ni_fecha_y_advierte():
    legacy = _row("0559", None, "120", "ACEPTADO")
    legacy["id_recepcion_original"] = None
    db = FakeDb(
        [
            legacy,
            *[
                _row("0559", date(2026, 2, 25), "100", "ACEPTADO")
                for _ in range(19)
            ],
            _row("0559", date(2026, 2, 26), "5", "RECHAZADO"),
        ]
    )

    result = service.recomendar_nivel_inspeccion(
        db, 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["estado"] == "CALCULADO"
    assert result["registros_legacy_sin_identidad"] == 1
    assert result["registros_legacy_sin_fecha"] == 1
    assert result["registros_legacy_sin_identidad_en_periodo"] == 0
    assert result["registros_evaluados"] == 20
    assert result["nivel_recomendado"] == "Normal"
    assert "se excluyeron 1 registros antiguos" in result["mensaje"].casefold()


def test_recomendar_nivel_ignora_legacy_identificado_fuera_del_periodo():
    legacy = _row("0559", date(2024, 2, 25), "120", "ACEPTADO")
    legacy["id_recepcion_original"] = None

    result = service.recomendar_nivel_inspeccion(
        FakeDb(
            [
                legacy,
                _row("0559", date(2026, 2, 25), "100", "ACEPTADO"),
            ]
        ),
        17,
        fecha_referencia=date(2026, 10, 19),
    )

    assert result["estado"] == "CALCULADO"
    assert result["registros_legacy_sin_identidad_en_periodo"] == 0
    assert result["registros_evaluados"] == 1
    assert result["nivel_recomendado"] == "Simplificada"


def test_recomendar_nivel_incluye_codigo_cero_por_nombre_exactamente_igual():
    db = FakeDb(
        [
            _row("0559", date(2026, 2, 25), "22873", "ACEPTADO"),
            _row("0", date(2026, 10, 5), "7090", "RECHAZADO"),
            _row("0", date(2026, 10, 7), "4103", "RECHAZADO"),
        ]
    )

    result = service.recomendar_nivel_inspeccion(
        db, 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["aceptados"] == 1
    assert result["rechazados"] == 2
    assert result["nivel_recomendado"] == "Estricta"


def test_codigo_cero_de_otro_proveedor_no_se_incluye():
    db = FakeDb(
        [
            _row("0559", date(2026, 2, 25), "100", "ACEPTADO"),
            _row("0", date(2026, 10, 5), "100", "RECHAZADO", name="OTRO SRL"),
        ]
    )

    result = service.recomendar_nivel_inspeccion(
        db, 17, fecha_referencia=date(2026, 10, 19)
    )

    assert result["rechazados"] == 0
    assert result["nivel_recomendado"] == "Simplificada"


def test_recomendar_nivel_no_depende_del_tamano_del_lote():
    result = service.recomendar_nivel_inspeccion(
        FakeDb([_row("0559", date(2026, 2, 25), "lote-42", "ACEPTADO")]),
        17,
        fecha_referencia=date(2026, 10, 19),
    )

    assert result["estado"] == "CALCULADO"
    assert result["nivel_recomendado"] == "Simplificada"


def test_recomendar_nivel_proveedor_inactivo_o_sin_codigo():
    db = FakeDb([])
    db.execute = lambda _query, _params: FakeResult(None)

    with pytest.raises(ValueError, match="no existe"):
        service.recomendar_nivel_inspeccion(db, 17)
