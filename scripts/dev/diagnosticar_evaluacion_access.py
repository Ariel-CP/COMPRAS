"""Inventario y cobertura para evaluación de proveedores, sin escrituras en Access."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.core.config import get_settings
from app.services.access_read_service import (
    _access_connection_lock,
    _access_read_connection,
)
from app.services.evaluacion_access_import_service import RUTA_ACCDB


def diagnosticar(path: str, objetivo: str) -> dict:
    with _access_connection_lock:
        connection = _access_read_connection(path)
        try:
            cursor = connection.cursor()
            tablas = sorted(
                {r.table_name for r in cursor.tables() if r.table_type in {"TABLE", "VIEW"}}
            )
            resultado = {"tablas": tablas, "objetivo": objetivo}
            tabla_real = next((t for t in tablas if t.casefold() == objetivo.casefold()), None)
            if tabla_real is None:
                resultado["disponible"] = False
                return resultado
            # Los objetivos son constantes del script, no entrada del usuario.
            cursor.execute(f"SELECT * FROM [{tabla_real}]")
            columnas = [c[0] for c in cursor.description]
            completos = Counter()
            valores = {c: Counter() for c in columnas}
            fechas = []
            total = 0
            anios = Counter()
            futuras = 0
            diferencias_total = 0
            claves = Counter()
            for row in cursor:
                total += 1
                fila = dict(zip(columnas, row))
                fecha = fila.get("Fecha", fila.get("Fecha Control"))
                if isinstance(fecha, datetime):
                    anios[str(fecha.year)] += 1
                    futuras += fecha.date() > date(2026, 11, 17)
                if objetivo.casefold() == "evaprov":
                    claves[(str(fila.get("Codigo")), str(fila.get("PERIODO")))] += 1
                    partes = [fila.get(c) for c in ("P_CAL", "P_SER", "P_EMB", "Calif_Total")]
                    if all(p is not None for p in partes):
                        numeros = [Decimal(str(p)) for p in partes]
                        diferencias_total += abs(sum(numeros[:3]) - numeros[3]) > Decimal("0.02")
                for col, valor in zip(columnas, row):
                    if valor is not None and str(valor).strip():
                        completos[col] += 1
                        # Solo distribuciones de criterios/estados; excluye texto libre.
                        if col.lower().startswith(("cal_", "ser_", "emb_", "p_", "pv_", "po_", "pp_")) or col in {
                            "CALIFICACION", "PERIODO", "Tipo_Eva", "Estado", "TieneCertificado"
                        }:
                            valores[col][str(valor)] += 1
                        if col in {"Fecha", "Fecha Control"}:
                            fechas.append(str(valor))
            resultado.update(
                disponible=True,
                filas=total,
                columnas=columnas,
                campos_con_datos={c: completos[c] for c in columnas},
                distribuciones={c: dict(v.most_common(30)) for c, v in valores.items() if v},
                fecha_min=min(fechas, default=None),
                fecha_max=max(fechas, default=None),
                filas_por_anio=dict(sorted(anios.items())),
                fechas_posteriores_2026_11_17=futuras,
                diferencias_suma_total_mayores_002=diferencias_total,
                grupos_codigo_periodo_repetidos=sum(n > 1 for n in claves.values()),
            )
            return resultado
        finally:
            connection.close()


def main() -> None:
    settings = get_settings()
    resultados = {}
    for nombre, path, tabla in (
        ("evaluaciones", RUTA_ACCDB, "Evaprov"),
        ("recepcion", settings.access_db_path, "CONTROL DE RECEPCION"),
    ):
        try:
            resultados[nombre] = diagnosticar(path, tabla)
        except Exception as exc:
            resultados[nombre] = {"error": str(exc)}
    destino = Path("outputs/evaluacion_proveedores/diagnostico_access.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(destino)


if __name__ == "__main__":
    main()
