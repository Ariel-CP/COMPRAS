from datetime import datetime
from decimal import Decimal

from scripts.dev.evaluar_proveedores_reunion import puntuar, resolver_maestro, clasificar


def test_certificado_ausente_siempre_cero():
    for aplica in (False, True):
        r = puntuar("Simplificada", datetime(2026, 1, 1), datetime(2026, 1, 20), 21, False, aplica)
        assert r["certificado"] == 0
        assert r["total"] == 90


def test_certificado_solo_suma_si_tiene_y_aplica():
    assert puntuar("Normal", None, datetime(2026, 7, 31), 21, True, True)["certificado"] == 10
    assert puntuar("Normal", None, datetime(2026, 7, 31), 21, True, False)["certificado"] == 0


def test_tolerancia_entrega_21_dias_adicionales():
    emision = datetime(2026, 1, 1)
    assert puntuar("Normal", emision, datetime(2026, 2, 12), 21, False, False)["entrega_base"] == 100
    assert puntuar("Normal", emision, datetime(2026, 2, 13), 21, False, False)["entrega_base"] == 33


def test_faltante_oc_se_considera_en_plazo_y_advierte():
    r = puntuar("Simplificada", None, datetime(2026, 7, 31), 21, False, True)
    assert r["total"] == Decimal("90")
    assert r["entrega"] == Decimal("45")
    assert r["retraso_dias"] is None
    assert r["sin_fecha_oc"]


def test_codigo_cero_no_atribuye_otro_proveedor_a_ypf():
    ypf = {"PROVEEDOR": "YPF GAS SA", "RAZON SOCIAL": "YPF GAS SA", "CODIGO": "0"}
    real = {"PROVEEDOR": "Acero SA", "RAZON SOCIAL": "Acero SA", "CODIGO": "12"}
    m, motivo = resolver_maestro({"Codigo Proveedor": "0", "PROVEEDOR": "Acero SA"}, {"0": [ypf]}, {"acero sa": [real]}, str)
    assert m is real
    assert motivo.startswith("Nombre exacto")


def test_nombre_ambiguo_no_se_asocia_por_primera_coincidencia():
    m, _ = resolver_maestro({"Codigo Proveedor": "0", "PROVEEDOR": "Acero SA"}, {}, {"acero sa": [{}, {}]}, str)
    assert m is None


def test_clasificar_con_precision_completa():
    assert clasificar(Decimal("69.999")) == "CONDICIONAL"
    assert clasificar(Decimal(70)) == "APROBADO"
    assert clasificar(Decimal(55)) == "CONDICIONAL"
    assert clasificar(Decimal("54.999")) == "NO APTO"
