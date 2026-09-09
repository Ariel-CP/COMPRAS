"""Utilidades compartidas para normalización de costos."""
from __future__ import annotations

from typing import Any


def normalizar_factor_merma(valor: Any) -> float:
    """Normaliza la merma al formato fraccional usado por el ERP.

    Acepta valores en tanto 0.03 como 3 para representar 3%.
    """
    if valor is None:
        return 0.0

    numero = float(valor)
    if numero < 0:
        return 0.0
    if numero > 1.0 and numero <= 100.0:
        numero = numero / 100.0
    return numero
