"""Vista previa del registro B con evidencia histórica Access, sin persistencia."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.access_read_service import (
    AccessReadError,
    _access_connection_lock,
    _access_read_connection,
)
from app.services.evaluacion_access_import_service import (
    CRITERIOS_CALIDAD,
    CRITERIOS_EMBALAJE,
    CRITERIOS_SERVICIO,
    RUTA_ACCDB,
)
from app.services.evaluacion_service import clasificar_resultado

logger = logging.getLogger(__name__)

VALORES_PV = (
    "PV_Cumplimiento de specificaciones",
    "PV_Certificado de Calidad",
    "PV_Innovacion",
    "PV_Tiempo de entrega",
    "PV_Disponibilidad ante reclamo",
    "PV_Relacion Precio Mercado",
    "PV_Asistencia Pos Venta",
    "PV_Servicio de entrega",
    "PV_Condiciones de Pago",
    "PV_Stock de producto terminado",
    "PV_Comunicacion con el proveedor",
    "PV_Presentacion del producto",
    "PV_Identificacion",
    "PV_Tipo de embalaje",
    "PV_Durabilidad del embalaje",
)


def _numero(valor: Any) -> Decimal | None:
    try:
        numero = Decimal(str(valor))
        return numero if numero.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def conciliar_fila(fila: dict, *, hoy: date | None = None) -> dict:
    """Compara subtotales y total sin reemplazar el resultado de origen."""
    hoy = hoy or date.today()
    partes = [_numero(fila.get(c)) for c in ("P_CAL", "P_SER", "P_EMB")]
    total = _numero(fila.get("Calif_Total"))
    suma = sum(partes, Decimal(0)) if all(p is not None for p in partes) else None
    diferencia = suma - total if suma is not None and total is not None else None
    advertencias = []
    if diferencia is None:
        advertencias.append("Faltan puntajes numéricos para conciliar el total.")
    elif abs(diferencia) > Decimal("0.02"):
        advertencias.append(
            "La suma de subtotales difiere del total registrado en Access."
        )
    if total is not None and not Decimal(0) <= total <= Decimal(100):
        advertencias.append("El total de origen está fuera de la escala 0–100.")
    fecha = fila.get("Fecha")
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    if not isinstance(fecha, date):
        advertencias.append("Fecha de evaluación ausente o no reconocida.")
        fecha = None
    elif fecha > hoy:
        advertencias.append("La evaluación tiene una fecha futura.")
    criterios = []
    grupos = (
        [("Calidad histórica", c) for c in CRITERIOS_CALIDAD]
        + [("Servicio histórico", c) for c in CRITERIOS_SERVICIO]
        + [("Embalaje histórico", c) for c in CRITERIOS_EMBALAJE]
    )
    for (grupo, (columna, codigo, nombre)), pv in zip(grupos, VALORES_PV):
        criterios.append(
            {
                "codigo": codigo,
                "grupo": grupo,
                "nombre": nombre,
                "respuesta": fila.get(columna),
                "valor": _numero(fila.get(pv)),
                "campo_origen": columna,
                "campo_valor": pv,
            }
        )
    return {
        "id": fila["Id"],
        "codigo": str(fila.get("Codigo") or ""),
        "proveedor": str(fila.get("Razon_Social") or ""),
        "periodo": str(fila.get("PERIODO") or ""),
        "fecha": fecha,
        "tipo": fila.get("Tipo_Eva"),
        "evaluador": fila.get("EVALUADOR"),
        "sector": fila.get("SECTOR AFECTADO"),
        "observaciones": fila.get("COMENTARIOS"),
        "subtotales": dict(zip(("Calidad", "Servicio", "Embalaje"), partes)),
        "total_origen": total,
        "total_calculado": suma,
        "diferencia": diferencia,
        "resultado_origen": fila.get("CALIFICACION"),
        "resultado_por_suma": clasificar_resultado(suma),
        "conciliado": diferencia is not None and abs(diferencia) <= Decimal("0.02"),
        "advertencias": advertencias,
        "criterios": criterios,
        "ponderaciones_origen": {
            c: _numero(v) for c, v in fila.items() if c.startswith(("PO_", "PP_"))
        },
    }


def leer_evaluaciones_preview() -> list[dict]:
    """Lee EVAPROV con el lock compartido y ReadOnly=1; no ejecuta importadores."""
    with _access_connection_lock:
        connection = _access_read_connection(RUTA_ACCDB)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM [EVAPROV] ORDER BY [Id] DESC")
            columnas = [c[0] for c in cursor.description]
            return [dict(zip(columnas, row)) for row in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Error leyendo evaluaciones para vista previa")
            raise AccessReadError(
                "No se pudieron leer las evaluaciones de Access"
            ) from exc
        finally:
            connection.close()


def obtener_vista_previa(*, q: str = "", access_id: int | None = None) -> dict:
    filas = leer_evaluaciones_preview()
    termino = q.strip().casefold()
    coincidencias = [
        f
        for f in filas
        if not termino
        or termino in str(f.get("Codigo", "")).casefold()
        or termino in str(f.get("Razon_Social", "")).casefold()
    ]
    seleccionada = next((f for f in filas if f["Id"] == access_id), None)
    pilotos = []
    for resultado in ("APROBADO", "APROB. CONDICIONAL", "NO APTO"):
        for fila in filas:
            if str(fila.get("CALIFICACION", "")).strip().upper() != resultado:
                continue
            caso = conciliar_fila(fila)
            if caso["conciliado"] and not caso["advertencias"]:
                pilotos.append(caso)
                break
    return {
        "origen": "Access · EVAPROV",
        "total": len(filas),
        "coincidencias": len(coincidencias),
        "opciones": [
            {
                "id": f["Id"],
                "codigo": str(f.get("Codigo") or ""),
                "proveedor": f.get("Razon_Social"),
                "periodo": f.get("PERIODO"),
            }
            for f in coincidencias[:100]
        ],
        "pilotos": pilotos,
        "seleccionada": conciliar_fila(seleccionada) if seleccionada else None,
        "no_encontrada": access_id is not None and seleccionada is None,
    }
