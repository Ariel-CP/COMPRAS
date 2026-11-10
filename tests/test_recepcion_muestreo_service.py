import pytest

from app.services.recepcion_muestreo_service import calcular_plan_muestreo


@pytest.mark.parametrize(
    ("nivel", "lote", "letra", "muestra"),
    [
        ("Simplificada", "2", "A", 2),
        ("Simplificada", "16", "B", 2),
        ("Simplificada", "26", "C", 2),
        ("Simplificada", "3201", "J", 32),
        ("Normal", "2", "A", 2),
        ("Normal", "16", "C", 5),
        ("Normal", "3201", "L", 200),
        ("Estricta", "2", "B", 3),
        ("Estricta", "16", "D", 8),
        ("Estricta", "500001", "R", 2000),
    ],
)
def test_calcular_plan_muestreo_por_anexo_f_a_i(nivel, lote, letra, muestra):
    result = calcular_plan_muestreo(nivel, lote)

    assert result["letra_codigo"] == letra
    assert result["tamano_muestra"] == muestra
    assert result["cantidad_lote"] == int(lote)
    assert result["porcentaje_muestreo"] == round(muestra / int(lote) * 100, 3)


@pytest.mark.parametrize(
    ("nivel", "lote"),
    [
        ("Normal", "abc"),
        ("Normal", "2.5"),
        ("Normal", "1"),
        ("No definido", "100"),
        ("Estricta", "0"),
    ],
)
def test_calcular_plan_muestreo_rechaza_entradas_invalidas(nivel, lote):
    with pytest.raises(ValueError):
        calcular_plan_muestreo(nivel, lote)
