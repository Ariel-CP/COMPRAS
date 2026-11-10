"""Nivel de inspección según el desempeño anual indicado en PG-4.10.01."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def recomendar_nivel_inspeccion(
    db: Session,
    proveedor_id: int,
    *,
    fecha_referencia: date | None = None,
) -> dict[str, Any]:
    """Clasifica al proveedor por porcentaje de entregas rechazadas del año."""
    proveedor = db.execute(
        text("SELECT codigo, nombre FROM proveedor WHERE id = :id AND activo = 1"),
        {"id": proveedor_id},
    ).first()
    if not proveedor or not proveedor.codigo:
        raise ValueError("El proveedor no existe, está inactivo o no tiene código")

    hasta = fecha_referencia or date.today()
    desde = date(hasta.year, 1, 1)
    filas = (
        db.execute(
            text("""
                SELECT id_recepcion_original, proveedor_codigo, proveedor_nombre,
                       fecha_recepcion_original,
                       estado_inspeccion_original
                FROM recepcion_staging
                WHERE proveedor_codigo IN (:codigo, :codigo_sin_ceros)
                   OR LOWER(TRIM(proveedor_nombre)) = LOWER(TRIM(:nombre))
                """),
            {
                "codigo": str(proveedor.codigo),
                "codigo_sin_ceros": str(proveedor.codigo).lstrip("0") or "0",
                "nombre": proveedor.nombre,
            },
        )
        .mappings()
        .all()
    )

    codigo_proveedor = str(proveedor.codigo).strip()
    codigo_normalizado = codigo_proveedor.lstrip("0") or "0"
    aceptados = 0
    rechazados = 0
    registros = 0
    registros_incompletos = 0
    registros_legacy_sin_identidad = 0
    registros_legacy_sin_fecha = 0
    registros_legacy_sin_identidad_en_periodo = 0
    for fila in filas:
        codigo_fila = str(fila["proveedor_codigo"] or "").strip()
        codigo_fila_normalizado = codigo_fila.lstrip("0") or "0"
        nombre_coincide = (
            str(fila["proveedor_nombre"] or "").strip().casefold()
            == str(proveedor.nombre or "").strip().casefold()
        )
        codigo_ausente = codigo_fila in {"", "0"}
        if not (
            codigo_fila == codigo_proveedor
            or codigo_fila_normalizado == codigo_normalizado
            or (codigo_ausente and nombre_coincide)
        ):
            continue

        estado = str(fila["estado_inspeccion_original"] or "").strip().casefold()
        if estado == "anulado":
            continue

        fecha_control = fila["fecha_recepcion_original"]
        if isinstance(fecha_control, datetime):
            fecha_control = fecha_control.date()
        if not fila["id_recepcion_original"]:
            registros_legacy_sin_identidad += 1
            if not fecha_control:
                registros_legacy_sin_fecha += 1
                continue
            if not desde <= fecha_control <= hasta:
                continue
            registros_legacy_sin_identidad_en_periodo += 1
            continue

        if not fecha_control:
            registros_incompletos += 1
            continue
        if not desde <= fecha_control <= hasta:
            continue
        if estado not in {"aceptado", "rechazado"}:
            registros_incompletos += 1
            continue
        registros += 1
        if estado == "aceptado":
            aceptados += 1
        else:
            rechazados += 1

    respuesta: dict[str, Any] = {
        "proveedor_id": proveedor_id,
        "proveedor_codigo": str(proveedor.codigo),
        "desde": desde,
        "hasta": hasta,
        "aceptados": aceptados,
        "rechazados": rechazados,
        "registros_evaluados": registros,
        "registros_incompletos": registros_incompletos,
        "registros_legacy_sin_identidad": registros_legacy_sin_identidad,
        "registros_legacy_sin_fecha": registros_legacy_sin_fecha,
        "registros_legacy_sin_identidad_en_periodo": (
            registros_legacy_sin_identidad_en_periodo
        ),
        "formula": "entregas_rechazadas / total_entregas * 100",
        "campo_fecha": "Fecha Control",
        "campo_unidad": "Cantidad de entregas con control registrado",
        "origen": "PG-4.10.01 v17; historial de controles importado en COMPRAS",
        "nivel_recomendado": None,
        "porcentaje_entregas_rechazadas": None,
        "total_entregas": aceptados + rechazados,
        "estado": None,
        "mensaje": None,
    }
    if registros_legacy_sin_identidad_en_periodo:
        respuesta.update(
            estado="HISTORIAL_INCOMPLETO",
            mensaje=(
                f"Hay {registros_legacy_sin_identidad_en_periodo} registros sin "
                "ID_INT de Access, pero con fecha dentro del período evaluado. "
                "Revisá su identidad antes de calcular el nivel."
            ),
        )
        return respuesta
    if registros_incompletos:
        respuesta.update(
            estado="HISTORIAL_INCOMPLETO",
            mensaje=(
                f"Hay {registros_incompletos} registros importados del proveedor sin "
                "fecha de control o estado de inspección válido. Reimportá el historial "
                "de Access para completar esos campos; no se asignó nivel."
            ),
        )
        return respuesta
    if registros == 0:
        respuesta.update(
            estado="SIN_HISTORIAL",
            mensaje=f"No hay entregas aceptadas o rechazadas registradas en {hasta.year}.",
        )
        return respuesta
    porcentaje = Decimal(rechazados) / Decimal(registros) * Decimal("100")
    nivel = (
        "Simplificada"
        if rechazados == 0
        else "Estricta" if porcentaje > Decimal("5") else "Normal"
    )
    respuesta.update(
        estado="CALCULADO",
        nivel_recomendado=nivel,
        porcentaje_entregas_rechazadas=porcentaje,
        mensaje=(
            f"Nivel determinado por el porcentaje de entregas rechazadas de {hasta.year}."
            + (
                f" Se excluyeron {registros_legacy_sin_fecha} registros antiguos "
                "sin ID_INT ni fecha de control."
                if registros_legacy_sin_fecha
                else ""
            )
        ),
    )
    return respuesta
