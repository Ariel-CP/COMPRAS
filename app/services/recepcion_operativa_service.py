"""Operaciones de registro de inspecciones de recepción."""

from __future__ import annotations

import re
from decimal import InvalidOperation, ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.recepcion import (
    RecepcionCalidadCreate,
    RecepcionIntentoInspeccionCreate,
    RecepcionOperativaCreate,
)


def _calcular_porcentaje_muestreo(
    tamano_muestra: int | None,
    cantidad_lote: Decimal,
    porcentaje_informado: Decimal | None,
) -> Decimal | None:
    if tamano_muestra is None:
        return porcentaje_informado
    porcentaje = Decimal(tamano_muestra) / cantidad_lote * Decimal("100")
    return min(porcentaje, Decimal("100")).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )


def _resolver_cantidad_lote(
    lote_numero: str | None,
    cantidad_lote_legacy: Decimal | None,
    cantidad_recibida: Decimal | None = None,
) -> Decimal:
    if cantidad_recibida is not None and cantidad_recibida > 0:
        return cantidad_recibida
    if cantidad_lote_legacy is not None and cantidad_lote_legacy > 0:
        return cantidad_lote_legacy
    if lote_numero and lote_numero.strip():
        try:
            cantidad = Decimal(lote_numero.strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            cantidad = None
        if cantidad is not None and cantidad.is_finite() and cantidad > 0:
            return cantidad
    raise ValueError("Número de lote debe ser una cantidad numérica mayor que cero")


def _calcular_plan_guardado(
    nivel_inspeccion: str | None, cantidad_lote: Decimal
) -> tuple[str | None, int | None, Decimal | None]:
    if not nivel_inspeccion:
        return None, None, None
    from app.services.recepcion_muestreo_service import calcular_plan_muestreo

    try:
        plan = calcular_plan_muestreo(nivel_inspeccion, cantidad_lote)
    except ValueError:
        return None, None, None
    return (
        plan["letra_codigo"],
        plan["tamano_muestra"],
        Decimal(str(plan["porcentaje_muestreo"])),
    )


def listar_recepciones_operativas(
    db: Session,
    *,
    q: str | None = None,
    proveedor_codigo: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    condiciones = []
    params: dict[str, Any] = {"limit": limit}
    if q and q.strip():
        condiciones.append(
            "(rc.numero_recepcion LIKE :q OR p.nombre LIKE :q "
            "OR rc.orden_compra LIKE :q OR rc.remito LIKE :q "
            "OR EXISTS (SELECT 1 FROM recepcion_linea rl "
            "WHERE rl.recepcion_cabecera_id = rc.id "
            "AND (rl.numero_plano LIKE :q OR rl.designacion LIKE :q)))"
        )
        params["q"] = f"%{q.strip()}%"
    if proveedor_codigo and proveedor_codigo.strip():
        condiciones.append("p.codigo = :proveedor_codigo")
        params["proveedor_codigo"] = proveedor_codigo.strip()
    filtros = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    rows = db.execute(
        text(f"""
                 SELECT rc.id, rc.recepcion_staging_id, rc.numero_recepcion,
                     rc.orden_compra, rc.remito,
                   rc.fecha_recepcion, rc.fecha_control, rc.estado,
                     rc.usuario_creacion_id, rc.usuario_inspeccion_id,
                     ur.nombre AS usuario_recepcion_nombre,
                     ui.nombre AS usuario_calidad_nombre,
                                     p.codigo AS proveedor_codigo,
                   p.nombre AS proveedor_nombre,
                   (SELECT COUNT(*) FROM recepcion_linea rl
                    WHERE rl.recepcion_cabecera_id = rc.id) AS cantidad_lineas,
                   (SELECT COALESCE(SUM(rl.cantidad_recibida), 0) FROM recepcion_linea rl
                    WHERE rl.recepcion_cabecera_id = rc.id) AS cantidad_articulos
            FROM recepcion_cabecera rc
            JOIN proveedor p ON p.id = rc.proveedor_id
            LEFT JOIN usuario ur ON ur.id = rc.usuario_creacion_id
            LEFT JOIN usuario ui ON ui.id = rc.usuario_inspeccion_id
            {filtros}
            ORDER BY rc.fecha_recepcion DESC, rc.id DESC
            LIMIT :limit
            """),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def listar_lineas_pendientes_calidad(
    db: Session,
    *,
    q: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    """Lista materiales locales que aún requieren control o reinspección."""
    condiciones = [
        "rc.recepcion_staging_id IS NULL",
        "rl.estado_inspeccion IN ('NO_INSPECCIONADO', 'PENDIENTE', 'RECHAZADO')",
    ]
    params: dict[str, Any] = {"limit": limit}
    if q and q.strip():
        condiciones.append(
            "(rc.numero_recepcion LIKE :q OR rc.orden_compra LIKE :q "
            "OR rc.remito LIKE :q OR p.nombre LIKE :q OR p.codigo LIKE :q "
            "OR rl.numero_plano LIKE :q OR rl.designacion LIKE :q "
            "OR rl.lote_numero LIKE :q)"
        )
        params["q"] = f"%{q.strip()}%"

    rows = db.execute(
        text(f"""
            SELECT rl.id AS linea_id, rc.id AS recepcion_id,
                   rc.numero_recepcion, rc.proveedor_id,
                   p.codigo AS proveedor_codigo, p.nombre AS proveedor_nombre,
                   rc.orden_compra, rc.remito, rc.fecha_recepcion,
                   rc.fecha_entrega_esperada, rc.notas AS notas_recepcion,
                   rc.estado_embalaje,
                   rl.numero_linea, rl.producto_id,
                   pr.codigo AS producto_codigo, pr.nombre AS producto_nombre,
                   rl.designacion, rl.numero_plano, rl.lote_numero,
                   rl.cantidad_lote, rl.cantidad_solicitada,
                   rl.cantidad_recibida, um.codigo AS unidad_medida,
                   rl.material_utilizado, rl.estado_inspeccion,
                   rl.nivel_inspeccion, rl.tamano_muestra,
                   rl.letra_codigo_muestreo,
                   rl.porcentaje_muestreo, rl.observaciones,
                   ultimo.id AS ultimo_intento_id,
                   ultimo.numero_intento, ultimo.tipo_intento,
                   ultimo.decision AS ultima_decision,
                   ultimo.unidades_inspeccionadas,
                   ultimo.unidades_no_conformes,
                   ultimo.referencia_normativa
            FROM recepcion_linea rl
            JOIN recepcion_cabecera rc ON rc.id = rl.recepcion_cabecera_id
            JOIN proveedor p ON p.id = rc.proveedor_id
            JOIN producto pr ON pr.id = rl.producto_id
            LEFT JOIN unidad_medida um ON um.id = rl.unidad_medida_id
            LEFT JOIN recepcion_inspeccion_intento ultimo
              ON ultimo.recepcion_linea_id = rl.id
             AND ultimo.numero_intento = (
                SELECT MAX(anterior.numero_intento)
                FROM recepcion_inspeccion_intento anterior
                WHERE anterior.recepcion_linea_id = rl.id
             )
            WHERE {' AND '.join(condiciones)}
            ORDER BY rc.fecha_recepcion DESC, rc.id DESC, rl.numero_linea
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
                     rc.usuario_creacion_id, rc.usuario_inspeccion_id,
                   rc.notas, rc.estado_embalaje, rc.terminacion_superficial,
                   rc.control_dimensional, rc.embalaje,
                     p.codigo AS proveedor_codigo, p.nombre AS proveedor_nombre,
                     ur.nombre AS usuario_recepcion_nombre,
                     ui.nombre AS usuario_calidad_nombre
            FROM recepcion_cabecera rc
            JOIN proveedor p ON p.id = rc.proveedor_id
                 LEFT JOIN usuario ur ON ur.id = rc.usuario_creacion_id
                 LEFT JOIN usuario ui ON ui.id = rc.usuario_inspeccion_id
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
                   rl.nivel_inspeccion, rl.letra_codigo_muestreo,
                   rl.tamano_muestra,
                   rl.porcentaje_muestreo, rl.material_utilizado,
                     p.codigo AS producto_codigo, p.nombre AS producto_nombre,
                     um.codigo AS unidad_medida
            FROM recepcion_linea rl
            JOIN producto p ON p.id = rl.producto_id
                 LEFT JOIN unidad_medida um ON um.id = rl.unidad_medida_id
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
        intentos = (
            db.execute(
                text("""
                SELECT id, numero_intento, tipo_intento, intento_anterior_id,
                       nivel_inspeccion, tamano_muestra_planificado,
                       unidades_inspeccionadas, unidades_no_conformes,
                       decision, referencia_normativa, inspector_id,
                       fecha_inspeccion
                FROM recepcion_inspeccion_intento
                WHERE recepcion_linea_id = :linea_id
                ORDER BY numero_intento
                """),
                {"linea_id": linea["id"]},
            )
            .mappings()
            .all()
        )
        cotas = (
            db.execute(
                text("""
                SELECT id, intento_id, criterio_nombre, especificacion, valor_medido,
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
        cotas_por_intento: dict[int, list[dict[str, Any]]] = {}
        for cota in cotas:
            if cota["intento_id"] is not None:
                cotas_por_intento.setdefault(int(cota["intento_id"]), []).append(
                    dict(cota)
                )
        intentos_con_cotas = [
            {**dict(intento), "cotas": cotas_por_intento.get(int(intento["id"]), [])}
            for intento in intentos
        ]
        detalle_lineas.append(
            {
                **dict(linea),
                "intentos_inspeccion": intentos_con_cotas,
                "cotas": [dict(cota) for cota in cotas],
            }
        )

    return {**dict(cabecera), "lineas": detalle_lineas}


def actualizar_recepcion_operativa(
    db: Session,
    recepcion_id: int,
    payload: RecepcionOperativaCreate,
    *,
    usuario_id: int,
) -> dict[str, Any]:
    """Actualiza los datos capturados sin alterar cotas ni intentos registrados."""
    cantidad_lote = _resolver_cantidad_lote(
        payload.lote_numero, payload.cantidad_lote, payload.cantidad_recibida
    )
    letra_codigo, tamano_muestra, porcentaje_muestreo = _calcular_plan_guardado(
        payload.nivel_inspeccion, cantidad_lote
    )
    recepcion = db.execute(
        text("SELECT id, recepcion_staging_id FROM recepcion_cabecera WHERE id = :id"),
        {"id": recepcion_id},
    ).first()
    if not recepcion:
        raise ValueError("Recepción no encontrada")
    if recepcion.recepcion_staging_id is not None:
        raise ValueError("Las recepciones históricas importadas son de solo lectura")

    intentos = db.execute(
        text("""
            SELECT COUNT(*)
            FROM recepcion_inspeccion_intento ri
            JOIN recepcion_linea rl ON rl.id = ri.recepcion_linea_id
            WHERE rl.recepcion_cabecera_id = :id
            """),
        {"id": recepcion_id},
    ).scalar_one()
    if intentos:
        raise ValueError(
            "No se puede editar una recepción con intentos de inspección registrados"
        )
    no_conformidades = db.execute(
        text("""
            SELECT COUNT(*)
            FROM recepcion_no_conformidad rnc
            JOIN recepcion_linea rl ON rl.id = rnc.recepcion_linea_id
            WHERE rl.recepcion_cabecera_id = :id
            """),
        {"id": recepcion_id},
    ).scalar_one()
    if no_conformidades:
        raise ValueError(
            "No se puede editar una recepción con no conformidades registradas"
        )

    proveedor = db.execute(
        text("SELECT id FROM proveedor WHERE id = :id AND activo = 1"),
        {"id": payload.proveedor_id},
    ).first()
    if not proveedor:
        raise ValueError("El proveedor no existe o está inactivo")

    producto = (
        db.execute(
            text("""
            SELECT id, codigo, unidad_medida_id
            FROM producto
            WHERE id = :id AND activo = 1
            """),
            {"id": payload.producto_id},
        )
        .mappings()
        .first()
    )
    if not producto:
        raise ValueError("El artículo no existe o está inactivo")

    linea = db.execute(
        text("""
            SELECT id
            FROM recepcion_linea
            WHERE recepcion_cabecera_id = :id
            ORDER BY numero_linea
            LIMIT 1
            """),
        {"id": recepcion_id},
    ).first()
    if not linea:
        raise ValueError("La recepción no tiene una línea editable")

    plano_desde_codigo = re.search(r"(\d{4})$", str(producto["codigo"]))
    numero_plano = payload.numero_plano or (
        plano_desde_codigo.group(1) if plano_desde_codigo else None
    )
    db.execute(
        text("""
            UPDATE recepcion_cabecera
            SET proveedor_id = :proveedor_id,
                orden_compra = :orden_compra,
                remito = :remito,
                fecha_recepcion = :fecha_recepcion,
                fecha_entrega_esperada = :fecha_entrega_esperada,
                estado_embalaje = :estado_embalaje,
                notas = :notas
            WHERE id = :id
            """),
        {
            "id": recepcion_id,
            "proveedor_id": payload.proveedor_id,
            "orden_compra": payload.orden_compra.strip(),
            "remito": payload.remito,
            "fecha_recepcion": payload.fecha_recepcion,
            "fecha_entrega_esperada": payload.fecha_entrega_esperada,
            "estado_embalaje": payload.estado_embalaje,
            "notas": payload.notas,
        },
    )
    db.execute(
        text("""
            UPDATE recepcion_linea
            SET producto_id = :producto_id,
                numero_plano = :numero_plano,
                designacion = :designacion,
                cantidad_solicitada = :cantidad_solicitada,
                cantidad_recibida = :cantidad_recibida,
                cantidad_lote = :cantidad_lote,
                unidad_medida_id = :unidad_medida_id,
                lote_numero = :lote_numero,
                nivel_inspeccion = :nivel_inspeccion,
                letra_codigo_muestreo = :letra_codigo_muestreo,
                tamano_muestra = :tamano_muestra,
                porcentaje_muestreo = :porcentaje_muestreo,
                material_utilizado = :material_utilizado,
                observaciones = :observaciones
            WHERE id = :linea_id
            """),
        {
            "linea_id": linea.id,
            "producto_id": payload.producto_id,
            "numero_plano": numero_plano,
            "designacion": payload.designacion,
            "cantidad_solicitada": (
                str(payload.cantidad_solicitada)
                if payload.cantidad_solicitada is not None
                else None
            ),
            "cantidad_recibida": (
                str(payload.cantidad_recibida)
                if payload.cantidad_recibida is not None
                else None
            ),
            "cantidad_lote": str(cantidad_lote),
            "unidad_medida_id": producto["unidad_medida_id"],
            "lote_numero": payload.lote_numero,
            "nivel_inspeccion": payload.nivel_inspeccion,
            "letra_codigo_muestreo": letra_codigo,
            "tamano_muestra": tamano_muestra,
            "porcentaje_muestreo": str(porcentaje_muestreo) if porcentaje_muestreo is not None else None,
            "material_utilizado": payload.material_utilizado,
            "observaciones": payload.notas,
        },
    )
    db.execute(
        text("DELETE FROM recepcion_inspeccion WHERE recepcion_linea_id = :linea_id"),
        {"linea_id": linea.id},
    )
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
                "linea_id": linea.id,
                "criterio_nombre": cota.criterio_nombre,
                "especificacion": cota.especificacion,
                "valor_medido": cota.valor_medido,
                "desviacion": cota.desviacion,
                "resultado": cota.resultado,
                "observaciones": cota.observaciones,
                "usuario_id": usuario_id,
            },
        )
    resultados = [cota.resultado for cota in payload.cotas]
    if "NO_CONFORME" in resultados:
        estado_inspeccion = "RECHAZADO"
        estado_cabecera = "RECHAZADA"
    elif resultados and all(
        resultado in {"OK", "NO_APLICA"} for resultado in resultados
    ):
        estado_inspeccion = "APROBADO"
        estado_cabecera = "COMPLETA"
    elif resultados:
        estado_inspeccion = "PENDIENTE"
        estado_cabecera = "EN_INSPECCIÓN"
    else:
        estado_inspeccion = "NO_INSPECCIONADO"
        estado_cabecera = "PENDIENTE"
    db.execute(
        text("UPDATE recepcion_linea SET estado_inspeccion = :estado WHERE id = :id"),
        {"estado": estado_inspeccion, "id": linea.id},
    )
    db.execute(
        text("""
            UPDATE recepcion_cabecera
            SET estado = :estado,
                fecha_control = CASE WHEN :has_cotas THEN COALESCE(fecha_control, CURRENT_DATE) ELSE fecha_control END,
                usuario_inspeccion_id = CASE WHEN :has_cotas THEN :usuario_id ELSE usuario_inspeccion_id END,
                terminacion_superficial = :terminacion_superficial,
                control_dimensional = :control_dimensional,
                embalaje = :embalaje,
                cantidad_lineas = 1,
                cantidad_aceptadas = :aceptadas,
                cantidad_rechazadas = :rechazadas
            WHERE id = :id
            """),
        {
            "id": recepcion_id,
            "estado": estado_cabecera,
            "has_cotas": bool(resultados),
            "usuario_id": usuario_id,
            "terminacion_superficial": payload.terminacion_superficial,
            "control_dimensional": payload.control_dimensional,
            "embalaje": payload.embalaje,
            "aceptadas": int(estado_inspeccion == "APROBADO"),
            "rechazadas": int(estado_inspeccion == "RECHAZADO"),
        },
    )
    return {"id": recepcion_id, "estado": "ACTUALIZADA"}


def eliminar_recepcion_operativa(db: Session, recepcion_id: int) -> None:
    """Elimina una recepción local solo si no tiene intentos ni no conformidades."""
    recepcion = db.execute(
        text("SELECT id, recepcion_staging_id FROM recepcion_cabecera WHERE id = :id"),
        {"id": recepcion_id},
    ).first()
    if not recepcion:
        raise ValueError("Recepción no encontrada")
    if recepcion.recepcion_staging_id is not None:
        raise ValueError("Las recepciones históricas importadas son de solo lectura")

    intentos = db.execute(
        text("""
            SELECT COUNT(*)
            FROM recepcion_inspeccion_intento ri
            JOIN recepcion_linea rl ON rl.id = ri.recepcion_linea_id
            WHERE rl.recepcion_cabecera_id = :id
            """),
        {"id": recepcion_id},
    ).scalar_one()
    if intentos:
        raise ValueError(
            "No se puede borrar una recepción con intentos de inspección registrados"
        )

    no_conformidades = db.execute(
        text("""
            SELECT COUNT(*)
            FROM recepcion_no_conformidad rnc
            JOIN recepcion_linea rl ON rl.id = rnc.recepcion_linea_id
            WHERE rl.recepcion_cabecera_id = :id
            """),
        {"id": recepcion_id},
    ).scalar_one()
    if no_conformidades:
        raise ValueError(
            "No se puede borrar una recepción con no conformidades registradas"
        )

    linea_ids = (
        db.execute(
            text("SELECT id FROM recepcion_linea WHERE recepcion_cabecera_id = :id"),
            {"id": recepcion_id},
        )
        .scalars()
        .all()
    )
    for linea_id in linea_ids:
        db.execute(
            text("DELETE FROM recepcion_inspeccion WHERE recepcion_linea_id = :id"),
            {"id": linea_id},
        )
    db.execute(
        text("DELETE FROM recepcion_linea WHERE recepcion_cabecera_id = :id"),
        {"id": recepcion_id},
    )
    db.execute(
        text("DELETE FROM recepcion_cabecera WHERE id = :id"), {"id": recepcion_id}
    )


def crear_recepcion_operativa(
    db: Session,
    payload: RecepcionOperativaCreate,
    *,
    usuario_id: int,
) -> dict[str, Any]:
    cantidad_lote = _resolver_cantidad_lote(
        payload.lote_numero, payload.cantidad_lote, payload.cantidad_recibida
    )
    letra_codigo, tamano_muestra, porcentaje_muestreo = _calcular_plan_guardado(
        payload.nivel_inspeccion, cantidad_lote
    )
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
    numero_plano = payload.numero_plano or (
        plano_desde_codigo.group(1) if plano_desde_codigo else None
    )

    numero_temporal = f"TMP-{uuid4().hex}"
    cabecera_result = db.execute(
        text("""
            INSERT INTO recepcion_cabecera (
                numero_recepcion, proveedor_id, orden_compra, remito,
                fecha_recepcion, fecha_entrega_esperada, fecha_control,
                estado, usuario_creacion_id, usuario_inspeccion_id, notas,
                terminacion_superficial, control_dimensional, embalaje,
                estado_embalaje
            ) VALUES (
                :numero_recepcion, :proveedor_id, :orden_compra, :remito,
                :fecha_recepcion, :fecha_entrega_esperada, :fecha_control,
                'PENDIENTE', :usuario_id, :inspector_id, :notas,
                :terminacion_superficial, :control_dimensional, :embalaje,
                :estado_embalaje
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
            "inspector_id": usuario_id if payload.cotas else None,
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
            "estado_embalaje": payload.estado_embalaje,
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
                nivel_inspeccion, letra_codigo_muestreo,
                tamano_muestra, porcentaje_muestreo,
                material_utilizado
            ) VALUES (
                :recepcion_id, 1, :producto_id, :numero_plano, :designacion,
                :cantidad_solicitada, :cantidad_recibida, :cantidad_lote,
                :unidad_medida_id, :lote_numero, :estado_inspeccion, :notas,
                :nivel_inspeccion, :letra_codigo_muestreo,
                :tamano_muestra, :porcentaje_muestreo,
                :material_utilizado
            )
            """),
        {
            "recepcion_id": recepcion_id,
            "producto_id": payload.producto_id,
            "numero_plano": numero_plano,
            "designacion": payload.designacion,
            "cantidad_solicitada": (
                str(payload.cantidad_solicitada)
                if payload.cantidad_solicitada is not None
                else None
            ),
            "cantidad_recibida": (
                str(payload.cantidad_recibida)
                if payload.cantidad_recibida is not None
                else None
            ),
            "cantidad_lote": str(cantidad_lote),
            "unidad_medida_id": producto.unidad_medida_id,
            "lote_numero": payload.lote_numero,
            "estado_inspeccion": estado_inspeccion,
            "notas": payload.notas,
            "nivel_inspeccion": payload.nivel_inspeccion,
            "letra_codigo_muestreo": letra_codigo,
            "tamano_muestra": tamano_muestra,
            "porcentaje_muestreo": str(porcentaje_muestreo) if porcentaje_muestreo is not None else None,
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


def registrar_intento_inspeccion(
    db: Session,
    linea_id: int,
    payload: RecepcionIntentoInspeccionCreate,
    *,
    usuario_id: int,
) -> dict[str, Any]:
    """Registra un intento como dato observado sin decidir el plan IRAM."""
    linea = db.execute(
        text("""
                     SELECT rl.id, rl.recepcion_cabecera_id, rl.estado_inspeccion,
                         rl.cantidad_recibida, rl.nivel_inspeccion,
                         rl.tamano_muestra, rc.recepcion_staging_id
                 FROM recepcion_linea rl
                 JOIN recepcion_cabecera rc ON rc.id = rl.recepcion_cabecera_id
                 WHERE rl.id = :linea_id
            """),
        {"linea_id": linea_id},
    ).first()
    if not linea:
        raise ValueError("Línea de recepción no encontrada")
    if linea.recepcion_staging_id is not None:
        raise ValueError("Las recepciones históricas importadas son de solo lectura")
    if linea.estado_inspeccion not in {"NO_INSPECCIONADO", "PENDIENTE", "RECHAZADO"}:
        raise ValueError("El material no está pendiente de control o reinspección")

    if payload.unidades_no_conformes > payload.unidades_inspeccionadas:
        raise ValueError(
            "Las unidades no conformes no pueden superar las inspeccionadas"
        )
    ultimo = (
        db.execute(
            text("""
            SELECT id, numero_intento
            FROM recepcion_inspeccion_intento
            WHERE recepcion_linea_id = :linea_id
            ORDER BY numero_intento DESC
            LIMIT 1
            """),
            {"linea_id": linea_id},
        )
        .mappings()
        .first()
    )

    if payload.tipo_intento == "INICIAL":
        if payload.intento_anterior_id is not None or ultimo:
            raise ValueError(
                "La inspección inicial ya existe o tiene un intento anterior"
            )
        numero_intento = 1
    else:
        if payload.intento_anterior_id is None:
            raise ValueError("La reinspección debe indicar el intento anterior")
        if not ultimo or ultimo["id"] != payload.intento_anterior_id:
            raise ValueError(
                "El intento anterior debe ser el más reciente de esta línea"
            )
        numero_intento = int(ultimo["numero_intento"]) + 1

    if (
        linea.cantidad_recibida is not None
        and Decimal(payload.unidades_inspeccionadas)
        > Decimal(str(linea.cantidad_recibida))
    ):
        raise ValueError("Las unidades inspeccionadas superan la cantidad recibida")
    if (
        linea.tamano_muestra is not None
        and payload.tamano_muestra_planificado != linea.tamano_muestra
    ):
        raise ValueError("El tamaño planificado debe coincidir con la muestra guardada")
    if (
        linea.nivel_inspeccion is not None
        and payload.nivel_inspeccion != linea.nivel_inspeccion
    ):
        raise ValueError("El nivel debe coincidir con el plan guardado en la recepción")
    if (
        payload.tamano_muestra_planificado is not None
        and payload.unidades_inspeccionadas > payload.tamano_muestra_planificado
    ):
        raise ValueError("Las unidades inspeccionadas superan la muestra planificada")

    result = db.execute(
        text("""
            INSERT INTO recepcion_inspeccion_intento (
                recepcion_linea_id, numero_intento, tipo_intento,
                intento_anterior_id, nivel_inspeccion,
                tamano_muestra_planificado, unidades_inspeccionadas,
                unidades_no_conformes, decision, referencia_normativa,
                inspector_id, fecha_inspeccion
            ) VALUES (
                :linea_id, :numero_intento, :tipo_intento,
                :intento_anterior_id, :nivel_inspeccion,
                :tamano_muestra_planificado, :unidades_inspeccionadas,
                :unidades_no_conformes, :decision, :referencia_normativa,
                :usuario_id, COALESCE(:fecha_inspeccion, CURRENT_TIMESTAMP)
            )
            """),
        {
            "linea_id": linea_id,
            "numero_intento": numero_intento,
            "tipo_intento": payload.tipo_intento,
            "intento_anterior_id": payload.intento_anterior_id,
            "nivel_inspeccion": payload.nivel_inspeccion,
            "tamano_muestra_planificado": payload.tamano_muestra_planificado,
            "unidades_inspeccionadas": payload.unidades_inspeccionadas,
            "unidades_no_conformes": payload.unidades_no_conformes,
            "decision": payload.decision,
            "referencia_normativa": payload.referencia_normativa,
            "usuario_id": usuario_id,
            "fecha_inspeccion": payload.fecha_inspeccion,
        },
    )
    intento_id = result.lastrowid  # type: ignore[attr-defined]
    for cota in payload.cotas:
        db.execute(
            text("""
                INSERT INTO recepcion_inspeccion (
                    recepcion_linea_id, intento_id, criterio_nombre,
                    especificacion, valor_medido, desviacion, resultado,
                    observaciones, inspector_id
                ) VALUES (
                    :linea_id, :intento_id, :criterio_nombre,
                    :especificacion, :valor_medido, :desviacion, :resultado,
                    :observaciones, :usuario_id
                )
                """),
            {
                "linea_id": linea_id,
                "intento_id": intento_id,
                "criterio_nombre": cota.criterio_nombre,
                "especificacion": cota.especificacion,
                "valor_medido": cota.valor_medido,
                "desviacion": cota.desviacion,
                "resultado": cota.resultado,
                "observaciones": cota.observaciones,
                "usuario_id": usuario_id,
            },
        )

    estado_linea = {
        "ACEPTADO": "APROBADO",
        "RECHAZADO": "RECHAZADO",
        "PENDIENTE": "PENDIENTE",
    }[payload.decision]
    db.execute(
        text("""
            UPDATE recepcion_linea
            SET estado_inspeccion = :estado
            WHERE id = :linea_id
            """),
        {"estado": estado_linea, "linea_id": linea_id},
    )
    db.execute(
        text("""
            UPDATE recepcion_cabecera
            SET fecha_control = CURRENT_DATE,
                usuario_inspeccion_id = :usuario_id,
                cantidad_lineas = (
                    SELECT COUNT(*)
                    FROM recepcion_linea rl
                    WHERE rl.recepcion_cabecera_id = :recepcion_id
                ),
                cantidad_aceptadas = (
                    SELECT COUNT(*)
                    FROM recepcion_linea rl
                    WHERE rl.recepcion_cabecera_id = :recepcion_id
                      AND rl.estado_inspeccion = 'APROBADO'
                ),
                cantidad_rechazadas = (
                    SELECT COUNT(*)
                    FROM recepcion_linea rl
                    WHERE rl.recepcion_cabecera_id = :recepcion_id
                      AND rl.estado_inspeccion = 'RECHAZADO'
                ),
                estado = CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM recepcion_linea rl
                        WHERE rl.recepcion_cabecera_id = :recepcion_id
                          AND rl.estado_inspeccion IN (
                              'NO_INSPECCIONADO', 'PENDIENTE'
                          )
                    ) THEN 'EN_INSPECCIÓN'
                    WHEN EXISTS (
                        SELECT 1
                        FROM recepcion_linea rl
                        WHERE rl.recepcion_cabecera_id = :recepcion_id
                          AND rl.estado_inspeccion = 'RECHAZADO'
                    ) THEN 'RECHAZADA'
                    ELSE 'COMPLETA'
                END
            WHERE id = :recepcion_id
            """),
        {"usuario_id": usuario_id, "recepcion_id": linea.recepcion_cabecera_id},
    )
    return {"id": intento_id, "numero_intento": numero_intento}


def registrar_control_calidad(
    db: Session,
    recepcion_id: int,
    payload: RecepcionCalidadCreate,
    *,
    usuario_id: int,
) -> dict[str, Any]:
    """Guarda el control posterior e identifica al usuario que lo realizó."""
    recepcion = db.execute(
        text("""
                SELECT rc.usuario_inspeccion_id, rc.estado, rl.id AS linea_id,
                   (SELECT COUNT(*) FROM recepcion_inspeccion ri
                    WHERE ri.recepcion_linea_id = rl.id) AS cantidad_inspecciones
            FROM recepcion_cabecera rc
            JOIN recepcion_linea rl ON rl.recepcion_cabecera_id = rc.id
            WHERE rc.id = :recepcion_id
            ORDER BY rl.numero_linea
            LIMIT 1
            """),
        {"recepcion_id": recepcion_id},
    ).mappings().first()
    if not recepcion:
        raise ValueError("Recepción no encontrada")
    if recepcion["cantidad_inspecciones"] or recepcion["estado"] not in {
        "PENDIENTE",
        "EN_INSPECCIÓN",
    }:
        raise ValueError("El control de calidad ya fue registrado")

    resultados = [cota.resultado for cota in payload.cotas]
    if "NO_CONFORME" in resultados:
        estado_inspeccion = "RECHAZADO"
    elif all(resultado in {"OK", "NO_APLICA"} for resultado in resultados):
        estado_inspeccion = "APROBADO"
    else:
        estado_inspeccion = "PENDIENTE"

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
                "linea_id": recepcion["linea_id"],
                "criterio_nombre": cota.criterio_nombre,
                "especificacion": cota.especificacion,
                "valor_medido": cota.valor_medido,
                "desviacion": cota.desviacion,
                "resultado": cota.resultado,
                "observaciones": cota.observaciones,
                "usuario_id": usuario_id,
            },
        )

    estado_cabecera = (
        "RECHAZADA"
        if estado_inspeccion == "RECHAZADO"
        else "COMPLETA"
        if estado_inspeccion == "APROBADO"
        else "EN_INSPECCIÓN"
    )
    db.execute(
        text("""
            UPDATE recepcion_linea
            SET estado_inspeccion = :estado
            WHERE id = :linea_id
            """),
        {"estado": estado_inspeccion, "linea_id": recepcion["linea_id"]},
    )
    db.execute(
        text("""
            UPDATE recepcion_cabecera
            SET usuario_inspeccion_id = :usuario_id,
                fecha_control = CURRENT_DATE,
                estado = :estado,
                terminacion_superficial = :terminacion_superficial,
                control_dimensional = :control_dimensional,
                embalaje = :embalaje,
                cantidad_aceptadas = :aceptadas,
                cantidad_rechazadas = :rechazadas
            WHERE id = :recepcion_id
            """),
        {
            "usuario_id": usuario_id,
            "estado": estado_cabecera,
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
            "aceptadas": int(estado_inspeccion == "APROBADO"),
            "rechazadas": int(estado_inspeccion == "RECHAZADO"),
            "recepcion_id": recepcion_id,
        },
    )
    return {"estado": estado_cabecera, "estado_inspeccion": estado_inspeccion}
