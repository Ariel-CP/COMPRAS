from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _row_to_cabecera(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "producto_padre_id": row.producto_padre_id,
        "revision": row.revision,
        "estado": row.estado,
        "vigencia_desde": (
            row.vigencia_desde.isoformat() if row.vigencia_desde else None
        ),
        "vigencia_hasta": (
            row.vigencia_hasta.isoformat() if row.vigencia_hasta else None
        ),
        "notas": row.notas,
    }


def _row_to_detalle(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "mbom_id": row.mbom_id,
        "renglon": row.renglon,
        "componente_producto_id": row.componente_producto_id,
        "componente_codigo": row.comp_codigo,
        "componente_nombre": row.comp_nombre,
        "componente_tipo_producto": row.comp_tipo,
        "cantidad": float(row.cantidad),
        "unidad_medida_id": row.unidad_medida_id,
        "unidad_medida_codigo": row.um_codigo,
        "factor_merma": float(row.factor_merma),
        "operacion_secuencia": row.operacion_secuencia,
        "grupo_alternativa": row.grupo_alternativa,
        "designador_referencia": row.designador_referencia,
        "notas": row.notas,
    }


def get_cabecera_preferida(
    db: Session, producto_padre_id: int, preferir_estado: str = "ACTIVO"
) -> Optional[Dict[str, Any]]:
    """Obtiene cabecera preferida; si no, la más reciente."""
    estado = (
        preferir_estado
        if preferir_estado in {"ACTIVO", "BORRADOR", "ARCHIVADO"}
        else "ACTIVO"
    )
    row = db.execute(
        text(
            """
                 SELECT id, producto_padre_id, revision, estado,
                     vigencia_desde, vigencia_hasta, notas
            FROM mbom_cabecera
            WHERE producto_padre_id=:pid AND estado=:estado
              AND (vigencia_hasta IS NULL OR vigencia_hasta >= CURRENT_DATE())
            ORDER BY COALESCE(vigencia_desde, '1900-01-01') DESC,
                     fecha_creacion DESC
            LIMIT 1
            """
        ),
        {"pid": producto_padre_id, "estado": estado},
    ).first()
    if row:
        return _row_to_cabecera(row)

    # Fallback: cualquiera, la más reciente
    row2 = db.execute(
        text(
            """
                 SELECT id, producto_padre_id, revision, estado,
                     vigencia_desde, vigencia_hasta, notas
            FROM mbom_cabecera
            WHERE producto_padre_id=:pid
            ORDER BY fecha_creacion DESC
            LIMIT 1
            """
        ),
        {"pid": producto_padre_id},
    ).first()
    return _row_to_cabecera(row2) if row2 else None


def get_cabecera_por_id(db: Session, mbom_id: int) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            "SELECT id, producto_padre_id, revision, estado, vigencia_desde,"
            " vigencia_hasta, notas"
            " FROM mbom_cabecera WHERE id=:id"
        ),
        {"id": mbom_id},
    ).first()
    return _row_to_cabecera(row) if row else None


def _siguiente_revision(db: Session, producto_padre_id: int) -> str:
    last = db.execute(
        text(
            "SELECT revision FROM mbom_cabecera WHERE producto_padre_id=:pid "
            "ORDER BY fecha_creacion DESC LIMIT 1"
        ),
        {"pid": producto_padre_id},
    ).scalar()
    if not last:
        return "A"
    # Si es una letra, avanzar; si no, agregar 'A*'
    if isinstance(last, str) and len(last) == 1 and last.isalpha():
        return chr(ord(last.upper()) + 1)
    return f"{last}_1"


def obtener_o_crear_borrador(
    db: Session, producto_padre_id: int
) -> Dict[str, Any]:
    # Intentar encontrar BORRADOR existente
    row = db.execute(
        text(
            "SELECT id, producto_padre_id, revision, estado, vigencia_desde,"
            " vigencia_hasta, notas"
            " FROM mbom_cabecera WHERE producto_padre_id=:pid"
            " AND estado='BORRADOR'"
            " ORDER BY fecha_creacion DESC LIMIT 1"
        ),
        {"pid": producto_padre_id},
    ).first()
    if row:
        return _row_to_cabecera(row)

    # Crear nuevo BORRADOR con siguiente revision
    rev = _siguiente_revision(db, producto_padre_id)
    res = db.execute(
        text(
            "INSERT INTO mbom_cabecera (producto_padre_id, revision, estado)"
            " VALUES (:pid, :rev, 'BORRADOR')"
        ),
        {"pid": producto_padre_id, "rev": rev},
    )
    new_id_val = getattr(res, "lastrowid", None)
    if not new_id_val:
        new_id_val = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    if not new_id_val:
        raise ValueError("No se pudo obtener el ID de la nueva cabecera")
    return get_cabecera_por_id(
        db, int(new_id_val)
    )  # type: ignore[return-value]


def listar_lineas(db: Session, mbom_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
                 SELECT d.id, d.mbom_id, d.renglon, d.componente_producto_id,
                     d.cantidad,
                   d.unidad_medida_id, d.factor_merma, d.operacion_secuencia,
                   d.grupo_alternativa, d.designador_referencia, d.notas,
                   p.codigo AS comp_codigo, p.nombre AS comp_nombre,
                   p.tipo_producto AS comp_tipo,
                   um.codigo AS um_codigo
            FROM mbom_detalle d
            JOIN producto p ON p.id = d.componente_producto_id
            JOIN unidad_medida um ON um.id = d.unidad_medida_id
            WHERE d.mbom_id = :mb
            ORDER BY d.renglon
            """
        ),
        {"mb": mbom_id},
    ).fetchall()
    return [_row_to_detalle(r) for r in rows]


def upsert_linea(
    db: Session,
    mbom_id: int,
    renglon: int,
    componente_producto_id: int,
    cantidad: float,
    unidad_medida_id: int,
    factor_merma: float = 0.0,
    operacion_secuencia: Optional[int] = None,
    grupo_alternativa: Optional[str] = None,
    designador_referencia: Optional[str] = None,
    notas: Optional[str] = None,
    detalle_id: Optional[int] = None,
) -> Dict[str, Any]:
    # Validaciones básicas (dejar FKs a DB)
    if cantidad <= 0:
        raise ValueError("cantidad debe ser > 0")
    if factor_merma < 0 or factor_merma >= 1:
        raise ValueError("factor_merma fuera de rango [0,1)")

    if detalle_id:
        db.execute(
            text(
                """
                UPDATE mbom_detalle
                SET mbom_id=:mb, renglon=:r, componente_producto_id=:cp,
                    cantidad=:cant, unidad_medida_id=:um, factor_merma=:merma,
                    operacion_secuencia=:opsec, grupo_alternativa=:grp,
                    designador_referencia=:desig, notas=:notas
                WHERE id=:id
                """
            ),
            {
                "mb": mbom_id,
                "r": renglon,
                "cp": componente_producto_id,
                "cant": cantidad,
                "um": unidad_medida_id,
                "merma": factor_merma,
                "opsec": operacion_secuencia,
                "grp": grupo_alternativa,
                "desig": designador_referencia,
                "notas": notas,
                "id": detalle_id,
            },
        )
        return get_detalle_por_id(
            db, int(detalle_id)
        )  # type: ignore[return-value]

    res = db.execute(
        text(
            """
            INSERT INTO mbom_detalle (
                mbom_id, renglon, componente_producto_id, cantidad,
                unidad_medida_id, factor_merma, operacion_secuencia,
                grupo_alternativa, designador_referencia, notas
            ) VALUES (
                :mb, :r, :cp, :cant, :um, :merma, :opsec, :grp, :desig, :notas
            )
            """
        ),
        {
            "mb": mbom_id,
            "r": renglon,
            "cp": componente_producto_id,
            "cant": cantidad,
            "um": unidad_medida_id,
            "merma": factor_merma,
            "opsec": operacion_secuencia,
            "grp": grupo_alternativa,
            "desig": designador_referencia,
            "notas": notas,
        },
    )
    new_id_val = getattr(res, "lastrowid", None)
    if not new_id_val:
        new_id_val = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    if not new_id_val:
        raise ValueError("No se pudo obtener el ID del detalle")
    return get_detalle_por_id(
        db, int(new_id_val)
    )  # type: ignore[return-value]


def get_detalle_por_id(
    db: Session, detalle_id: int
) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
                 SELECT d.id, d.mbom_id, d.renglon, d.componente_producto_id,
                     d.cantidad,
                   d.unidad_medida_id, d.factor_merma, d.operacion_secuencia,
                   d.grupo_alternativa, d.designador_referencia, d.notas,
                   p.codigo AS comp_codigo, p.nombre AS comp_nombre,
                   p.tipo_producto AS comp_tipo,
                   um.codigo AS um_codigo
            FROM mbom_detalle d
            JOIN producto p ON p.id = d.componente_producto_id
            JOIN unidad_medida um ON um.id = d.unidad_medida_id
            WHERE d.id = :id
            """
        ),
        {"id": detalle_id},
    ).first()
    return _row_to_detalle(row) if row else None


def borrar_linea(db: Session, detalle_id: int) -> None:
    db.execute(
        text("DELETE FROM mbom_detalle WHERE id=:id"), {"id": detalle_id}
    )


def actualizar_cabecera(
    db: Session,
    mbom_id: int,
    estado: Optional[str] = None,
    revision: Optional[str] = None,
    vigencia_desde: Optional[str] = None,
    vigencia_hasta: Optional[str] = None,
    notas: Optional[str] = None,
) -> Dict[str, Any]:
    sets = []
    params: Dict[str, Any] = {"id": mbom_id}
    if estado:
        if estado not in {"BORRADOR", "ACTIVO", "ARCHIVADO"}:
            raise ValueError("Estado inválido")
        sets.append("estado=:estado")
        params["estado"] = estado
    if revision:
        sets.append("revision=:revision")
        params["revision"] = revision
    if vigencia_desde is not None:
        sets.append("vigencia_desde=:vd")
        params["vd"] = vigencia_desde
    if vigencia_hasta is not None:
        sets.append("vigencia_hasta=:vh")
        params["vh"] = vigencia_hasta
    if notas is not None:
        sets.append("notas=:notas")
        params["notas"] = notas

    if sets:
        db.execute(
            text(
                "UPDATE mbom_cabecera SET "
                + ", ".join(sets)
                + " WHERE id=:id"
            ),
            params,
        )
    return get_cabecera_por_id(db, mbom_id)  # type: ignore[return-value]


def activar_revision(db: Session, mbom_id: int) -> Dict[str, Any]:
    # Setear ACTIVO y archivar otras activas del mismo producto
    cab = get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise ValueError("MBOM no encontrada")
    pid = cab["producto_padre_id"]
    db.execute(
        text(
            "UPDATE mbom_cabecera SET estado='ARCHIVADO' "
            "WHERE producto_padre_id=:pid AND estado='ACTIVO'"
        ),
        {"pid": pid},
    )
    db.execute(
        text("UPDATE mbom_cabecera SET estado='ACTIVO' WHERE id=:id"),
        {"id": mbom_id},
    )
    return get_cabecera_por_id(db, mbom_id)  # type: ignore[return-value]


def clonar_revision_a_borrador(db: Session, mbom_id: int) -> Dict[str, Any]:
    cab = get_cabecera_por_id(db, mbom_id)
    if not cab:
        raise ValueError("MBOM no encontrada")
    pid = cab["producto_padre_id"]
    nueva_rev = _siguiente_revision(db, pid)
    res = db.execute(
        text(
            "INSERT INTO mbom_cabecera (producto_padre_id, revision, estado,"
            " vigencia_desde, vigencia_hasta, notas)"
            " SELECT producto_padre_id, :rev, 'BORRADOR', vigencia_desde,"
            " vigencia_hasta, notas FROM mbom_cabecera WHERE id=:id"
        ),
        {"rev": nueva_rev, "id": mbom_id},
    )
    new_id_val = getattr(res, "lastrowid", None)
    if not new_id_val:
        new_id_val = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    # Copiar detalle
    db.execute(
        text(
            "INSERT INTO mbom_detalle (mbom_id, renglon,"
            " componente_producto_id,"
            " cantidad, unidad_medida_id, factor_merma, operacion_secuencia,"
            " grupo_alternativa, designador_referencia, notas)"
            " SELECT :new_id, renglon, componente_producto_id, cantidad,"
            " unidad_medida_id, factor_merma, operacion_secuencia,"
            " grupo_alternativa, designador_referencia, notas"
            " FROM mbom_detalle WHERE mbom_id=:old_id"
        ),
        {"new_id": new_id_val, "old_id": mbom_id},
    )
    if not new_id_val:
        raise ValueError("No se pudo clonar la cabecera")
    return get_cabecera_por_id(
        db, int(new_id_val)
    )  # type: ignore[return-value]
