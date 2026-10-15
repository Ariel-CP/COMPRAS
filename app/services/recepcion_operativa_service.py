"""Operaciones de registro de inspecciones de recepción."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.recepcion import RecepcionOperativaCreate


def listar_recepciones_operativas(
    db: Session, *, q: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    filtros = ""
    params: dict[str, Any] = {"limit": limit}
    if q and q.strip():
        filtros = (
            "WHERE rc.numero_recepcion LIKE :q OR p.nombre LIKE :q "
            "OR rc.orden_compra LIKE :q OR rc.remito LIKE :q "
            "OR EXISTS (SELECT 1 FROM recepcion_linea rl "
            "WHERE rl.recepcion_cabecera_id = rc.id "
            "AND (rl.numero_plano LIKE :q OR rl.designacion LIKE :q))"
        )
        params["q"] = f"%{q.strip()}%"

    rows = db.execute(
        text(f"""
            SELECT rc.id, rc.numero_recepcion, rc.orden_compra, rc.remito,
                   rc.fecha_recepcion, rc.fecha_control, rc.estado,
                   p.nombre AS proveedor_nombre,
                   (SELECT COUNT(*) FROM recepcion_linea rl
                    WHERE rl.recepcion_cabecera_id = rc.id) AS cantidad_lineas
            FROM recepcion_cabecera rc
            JOIN proveedor p ON p.id = rc.proveedor_id
            {filtros}
            ORDER BY rc.fecha_recepcion DESC, rc.id DESC
            LIMIT :limit
            """),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def obtener_recepcion_operativa(
    db: Session, recepcion_id: int
) -> dict[str, Any] | None:
    cabecera = (
        db.execute(
            text("""
            SELECT rc.id, rc.numero_recepcion, rc.proveedor_id,
                   rc.orden_compra, rc.remito, rc.fecha_recepcion,
                   rc.fecha_entrega_esperada, rc.fecha_control, rc.estado,
                   rc.notas, rc.terminacion_superficial,
                   rc.control_dimensional, rc.embalaje,
                   p.codigo AS proveedor_codigo, p.nombre AS proveedor_nombre
            FROM recepcion_cabecera rc
            JOIN proveedor p ON p.id = rc.proveedor_id
            WHERE rc.id = :id
            """),
            {"id": recepcion_id},
        )
        .mappings()
        .first()
    )
    if not cabecera:
        return None

    lineas = (
        db.execute(
            text("""
            SELECT rl.id, rl.numero_linea, rl.producto_id,
                   rl.numero_plano, rl.designacion,
                   rl.cantidad_solicitada, rl.cantidad_recibida,
                   rl.cantidad_lote, rl.unidad_medida_id, rl.lote_numero,
                   rl.estado_inspeccion, rl.observaciones,
                   rl.nivel_inspeccion, rl.tamano_muestra,
                   rl.porcentaje_muestreo, rl.material_utilizado,
                   p.codigo AS producto_codigo, p.nombre AS producto_nombre
            FROM recepcion_linea rl
            JOIN producto p ON p.id = rl.producto_id
            WHERE rl.recepcion_cabecera_id = :id
            ORDER BY rl.numero_linea
            """),
            {"id": recepcion_id},
        )
        .mappings()
        .all()
    )

    detalle_lineas = []
    for linea in lineas:
        cotas = (
            db.execute(
                text("""
                SELECT id, criterio_nombre, especificacion, valor_medido,
                       desviacion, resultado, observaciones, inspector_id,
                       fecha_inspeccion
                FROM recepcion_inspeccion
                WHERE recepcion_linea_id = :linea_id
                ORDER BY id
                """),
                {"linea_id": linea["id"]},
            )
            .mappings()
            .all()
        )
        detalle_lineas.append({**dict(linea), "cotas": [dict(cota) for cota in cotas]})

    return {**dict(cabecera), "lineas": detalle_lineas}


def crear_recepcion_operativa(
    db: Session,
    payload: RecepcionOperativaCreate,
    *,
    usuario_id: int,
) -> dict[str, Any]:
    proveedor = db.execute(
        text("SELECT id FROM proveedor WHERE id = :id AND activo = 1"),
        {"id": payload.proveedor_id},
    ).first()
    if not proveedor:
        raise ValueError("El proveedor no existe o está inactivo")

    producto = db.execute(
        text(
            "SELECT id, codigo, unidad_medida_id FROM producto "
            "WHERE id = :id AND activo = 1"
        ),
        {"id": payload.producto_id},
    ).first()
    if not producto:
        raise ValueError("El artículo no existe o está inactivo")
    plano_desde_codigo = re.search(r"(\d{4})$", str(producto.codigo))
    numero_plano = (
        plano_desde_codigo.group(1)
        if plano_desde_codigo
        else payload.numero_plano
    )

    numero_temporal = f"TMP-{uuid4().hex}"
    cabecera_result = db.execute(
        text("""
            INSERT INTO recepcion_cabecera (
                numero_recepcion, proveedor_id, orden_compra, remito,
                fecha_recepcion, fecha_entrega_esperada, fecha_control,
                estado, usuario_creacion_id, usuario_inspeccion_id, notas,
                terminacion_superficial, control_dimensional, embalaje
            ) VALUES (
                :numero_recepcion, :proveedor_id, :orden_compra, :remito,
                :fecha_recepcion, :fecha_entrega_esperada, :fecha_control,
                'PENDIENTE', :usuario_id, :usuario_id, :notas,
                :terminacion_superficial, :control_dimensional, :embalaje
            )
            """),
        {
            "numero_recepcion": numero_temporal,
            "proveedor_id": payload.proveedor_id,
            "orden_compra": payload.orden_compra.strip(),
            "remito": payload.remito,
            "fecha_recepcion": payload.fecha_recepcion,
            "fecha_entrega_esperada": payload.fecha_entrega_esperada,
            "fecha_control": payload.fecha_control,
            "usuario_id": usuario_id,
            "notas": payload.notas,
            "terminacion_superficial": (
                str(payload.terminacion_superficial)
                if payload.terminacion_superficial is not None
                else None
            ),
            "control_dimensional": (
                str(payload.control_dimensional)
                if payload.control_dimensional is not None
                else None
            ),
            "embalaje": str(payload.embalaje) if payload.embalaje is not None else None,
        },
    )
    recepcion_id = cabecera_result.lastrowid  # type: ignore[attr-defined]
    numero_recepcion = f"REC-{int(recepcion_id):06d}"
    db.execute(
        text(
            "UPDATE recepcion_cabecera SET numero_recepcion = :numero "
            "WHERE id = :id"
        ),
        {"numero": numero_recepcion, "id": recepcion_id},
    )

    resultados = [cota.resultado for cota in payload.cotas]
    if "NO_CONFORME" in resultados:
        estado_inspeccion = "RECHAZADO"
    elif resultados and all(
        resultado in {"OK", "NO_APLICA"} for resultado in resultados
    ):
        estado_inspeccion = "APROBADO"
    elif resultados:
        estado_inspeccion = "PENDIENTE"
    else:
        estado_inspeccion = "NO_INSPECCIONADO"

    if not resultados:
        estado_cabecera = "PENDIENTE"
    elif estado_inspeccion == "RECHAZADO":
        estado_cabecera = "RECHAZADA"
    elif estado_inspeccion == "APROBADO":
        estado_cabecera = "COMPLETA"
    else:
        estado_cabecera = "EN_INSPECCIÓN"

    db.execute(
        text(
            "UPDATE recepcion_cabecera SET estado = :estado, cantidad_lineas = 1, "
            "cantidad_aceptadas = :aceptadas, cantidad_rechazadas = :rechazadas "
            "WHERE id = :id"
        ),
        {
            "estado": estado_cabecera,
            "aceptadas": int(estado_inspeccion == "APROBADO"),
            "rechazadas": int(estado_inspeccion == "RECHAZADO"),
            "id": recepcion_id,
        },
    )

    linea_result = db.execute(
        text("""
            INSERT INTO recepcion_linea (
                recepcion_cabecera_id, numero_linea, producto_id,
                numero_plano, designacion, cantidad_solicitada,
                cantidad_recibida, cantidad_lote, unidad_medida_id,
                lote_numero, estado_inspeccion, observaciones,
                nivel_inspeccion, tamano_muestra, porcentaje_muestreo,
                material_utilizado
            ) VALUES (
                :recepcion_id, 1, :producto_id, :numero_plano, :designacion,
                :cantidad_solicitada, :cantidad_recibida, :cantidad_lote,
                :unidad_medida_id, :lote_numero, :estado_inspeccion, :notas,
                :nivel_inspeccion, :tamano_muestra, :porcentaje_muestreo,
                :material_utilizado
            )
            """),
        {
            "recepcion_id": recepcion_id,
            "producto_id": payload.producto_id,
            "numero_plano": numero_plano,
            "designacion": payload.designacion,
            "cantidad_solicitada": str(payload.cantidad_solicitada),
            "cantidad_recibida": str(payload.cantidad_recibida),
            "cantidad_lote": str(payload.cantidad_lote),
            "unidad_medida_id": producto.unidad_medida_id,
            "lote_numero": payload.lote_numero,
            "estado_inspeccion": estado_inspeccion,
            "notas": payload.notas,
            "nivel_inspeccion": payload.nivel_inspeccion,
            "tamano_muestra": payload.tamano_muestra,
            "porcentaje_muestreo": (
                str(payload.porcentaje_muestreo)
                if payload.porcentaje_muestreo is not None
                else None
            ),
            "material_utilizado": payload.material_utilizado,
        },
    )
    linea_id = linea_result.lastrowid  # type: ignore[attr-defined]

    for cota in payload.cotas:
        db.execute(
            text("""
                INSERT INTO recepcion_inspeccion (
                    recepcion_linea_id, criterio_nombre, especificacion,
                    valor_medido, desviacion, resultado, observaciones,
                    inspector_id
                ) VALUES (
                    :linea_id, :criterio_nombre, :especificacion,
                    :valor_medido, :desviacion, :resultado, :observaciones,
                    :usuario_id
                )
                """),
            {
                "linea_id": linea_id,
                "criterio_nombre": cota.criterio_nombre,
                "especificacion": cota.especificacion,
                "valor_medido": cota.valor_medido,
                "desviacion": cota.desviacion,
                "resultado": cota.resultado,
                "observaciones": cota.observaciones,
                "usuario_id": usuario_id,
            },
        )

    return {
        "id": recepcion_id,
        "numero_recepcion": numero_recepcion,
        "estado": estado_cabecera,
    }
