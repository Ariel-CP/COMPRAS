"""Cálculo del tamaño de muestra de PG-4.10.01 v17, anexos F a I."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


_NIVELES: dict[str, tuple[tuple[int, int | None, str], ...]] = {
    "Simplificada": (
        (2, 15, "A"),
        (16, 25, "B"),
        (26, 90, "C"),
        (91, 150, "D"),
        (151, 280, "E"),
        (281, 500, "F"),
        (501, 1200, "G"),
        (1201, 3200, "H"),
        (3201, 10000, "J"),
        (10001, 35000, "K"),
        (35001, 150000, "L"),
        (150001, 500000, "M"),
        (500001, None, "N"),
    ),
    "Normal": (
        (2, 8, "A"),
        (9, 15, "B"),
        (16, 25, "C"),
        (26, 50, "D"),
        (51, 90, "E"),
        (91, 150, "F"),
        (151, 280, "G"),
        (281, 500, "H"),
        (501, 1200, "J"),
        (1201, 3200, "K"),
        (3201, 10000, "L"),
        (10001, 35000, "M"),
        (35001, 150000, "N"),
        (150001, 500000, "P"),
        (500001, None, "Q"),
    ),
    "Estricta": (
        (2, 8, "B"),
        (9, 15, "C"),
        (16, 25, "D"),
        (26, 50, "E"),
        (51, 90, "F"),
        (91, 150, "G"),
        (151, 280, "H"),
        (281, 500, "J"),
        (501, 1200, "K"),
        (1201, 3200, "L"),
        (3201, 10000, "M"),
        (10001, 35000, "N"),
        (35001, 150000, "P"),
        (150001, 500000, "Q"),
        (500001, None, "R"),
    ),
}

_TAMANOS_MUESTRA = {
    "Simplificada": {
        "A": 2,
        "B": 2,
        "C": 2,
        "D": 3,
        "E": 5,
        "F": 8,
        "G": 13,
        "H": 20,
        "J": 32,
        "K": 50,
        "L": 80,
        "M": 125,
        "N": 200,
    },
    "Normal": {
        "A": 2,
        "B": 3,
        "C": 5,
        "D": 8,
        "E": 13,
        "F": 20,
        "G": 32,
        "H": 50,
        "J": 80,
        "K": 125,
        "L": 200,
        "M": 315,
        "N": 500,
        "P": 800,
        "Q": 1250,
    },
    "Estricta": {
        "B": 3,
        "C": 5,
        "D": 8,
        "E": 13,
        "F": 20,
        "G": 32,
        "H": 50,
        "J": 80,
        "K": 125,
        "L": 200,
        "M": 315,
        "N": 500,
        "P": 800,
        "Q": 1250,
        "R": 2000,
    },
}


def calcular_plan_muestreo(nivel: str, lote: Any) -> dict[str, Any]:
    """Devuelve letra y tamaño de muestra para un lote entero positivo."""
    if nivel not in _NIVELES:
        raise ValueError("Seleccioná un nivel de inspección válido.")

    try:
        cantidad = Decimal(str(lote).strip().replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("El tamaño del LOTE debe ser un número entero positivo.") from exc
    if not cantidad.is_finite() or cantidad <= 0 or cantidad != cantidad.to_integral_value():
        raise ValueError("El tamaño del LOTE debe ser un número entero positivo.")

    cantidad_lote = int(cantidad)
    if cantidad_lote < 2:
        raise ValueError("El plan de muestreo del procedimiento comienza en lotes de 2 unidades.")

    for minimo, maximo, letra in _NIVELES[nivel]:
        if cantidad_lote >= minimo and (maximo is None or cantidad_lote <= maximo):
            return {
                "nivel_inspeccion": nivel,
                "cantidad_lote": cantidad_lote,
                "letra_codigo": letra,
                "tamano_muestra": _TAMANOS_MUESTRA[nivel][letra],
                "porcentaje_muestreo": round(
                    _TAMANOS_MUESTRA[nivel][letra] / cantidad_lote * 100, 3
                ),
                "referencia": "PG-4.10.01 v17, anexos F y G/H/I",
            }

    raise ValueError("No se encontró una fila aplicable en el plan de muestreo.")
