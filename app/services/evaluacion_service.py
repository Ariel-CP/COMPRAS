"""
Servicio de evaluación formal de proveedores (ISO 9001 — PG-4.06.02).

Reglas de clasificación:
  APROBADO          → puntaje_total >= 70
  APROB_CONDICIONAL → puntaje_total >= 55
  NO_APTO           → puntaje_total <  55
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reglas ISO PG-4.06.02
# ---------------------------------------------------------------------------

LIMITE_APROBADO = Decimal("70")
LIMITE_CONDICIONAL = Decimal("55")


def clasificar_resultado(puntaje_total: Optional[Decimal]) -> Optional[str]:
    """Retorna APROBADO / APROB_CONDICIONAL / NO_APTO según puntaje."""
    if puntaje_total is None:
        return None
    if puntaje_total >= LIMITE_APROBADO:
        return "APROBADO"
    if puntaje_total >= LIMITE_CONDICIONAL:
        return "APROB_CONDICIONAL"
    return "NO_APTO"


# ---------------------------------------------------------------------------
# CRUD evaluacion_proveedor_anual
# ---------------------------------------------------------------------------

def crear_evaluacion(db: Session, datos: dict) -> dict:
    """
    Inserta una evaluación + sus criterios de detalle.
    `datos` debe incluir:
      proveedor_id, anno, periodo, tipo_evaluacion,
      puntaje_calidad, puntaje_servicio, puntaje_embalaje,
      evaluador_nombre, sector_evaluador, fecha_evaluacion,
      proxima_evaluacion, observaciones, referencias, usuario_id,
      criterios: list[dict]  (puede ser vacía)
    """
    puntaje_total = _calcular_total(
        datos.get("puntaje_calidad"),
        datos.get("puntaje_servicio"),
        datos.get("puntaje_embalaje"),
    )
    resultado = clasificar_resultado(puntaje_total)

    insert_cab = text("""
        INSERT INTO evaluacion_proveedor_anual (
            proveedor_id, anno, periodo, tipo_evaluacion,
            puntaje_calidad, puntaje_servicio, puntaje_embalaje, puntaje_total,
            resultado,
            evaluador_nombre, sector_evaluador,
            fecha_evaluacion, proxima_evaluacion,
            observaciones, referencias,
            usuario_id
        ) VALUES (
            :proveedor_id, :anno, :periodo, :tipo_evaluacion,
            :puntaje_calidad, :puntaje_servicio, :puntaje_embalaje, :puntaje_total,
            :resultado,
            :evaluador_nombre, :sector_evaluador,
            :fecha_evaluacion, :proxima_evaluacion,
            :observaciones, :referencias,
            :usuario_id
        )
    """)
    db.execute(insert_cab, {
        "proveedor_id":       datos["proveedor_id"],
        "anno":               datos["anno"],
        "periodo":            datos.get("periodo", 0),
        "tipo_evaluacion":    datos.get("tipo_evaluacion", "ANUAL"),
        "puntaje_calidad":    datos.get("puntaje_calidad"),
        "puntaje_servicio":   datos.get("puntaje_servicio"),
        "puntaje_embalaje":   datos.get("puntaje_embalaje"),
        "puntaje_total":      puntaje_total,
        "resultado":          resultado,
        "evaluador_nombre":   datos.get("evaluador_nombre"),
        "sector_evaluador":   datos.get("sector_evaluador"),
        "fecha_evaluacion":   datos.get("fecha_evaluacion"),
        "proxima_evaluacion": datos.get("proxima_evaluacion"),
        "observaciones":      datos.get("observaciones"),
        "referencias":        datos.get("referencias"),
        "usuario_id":         datos.get("usuario_id"),
    })

    # Obtener ID generado
    row = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    if row is None:
        raise ValueError("No se pudo obtener el ID de la evaluación creada")
    evaluacion_id = int(row)

    # Insertar criterios
    criterios = datos.get("criterios") or []
    for crit in criterios:
        db.execute(text("""
            INSERT INTO evaluacion_criterio_detalle
              (evaluacion_id, categoria, criterio_codigo, criterio_nombre, puntaje, comentario)
            VALUES (:eid, :cat, :cod, :nom, :pts, :com)
        """), {
            "eid": evaluacion_id,
            "cat": crit.get("categoria"),
            "cod": crit.get("criterio_codigo"),
            "nom": crit.get("criterio_nombre"),
            "pts": crit.get("puntaje"),
            "com": crit.get("comentario"),
        })

    # Actualizar estado_calificacion del proveedor
    if resultado:
        db.execute(text("""
            UPDATE proveedor
            SET estado_calificacion = :r
            WHERE id = :pid
        """), {"r": resultado, "pid": datos["proveedor_id"]})

    db.commit()
    logger.info(
        "Evaluación %d creada: proveedor=%d anno=%s resultado=%s puntaje=%.2f",
        evaluacion_id, datos["proveedor_id"], datos["anno"], resultado or "N/A",
        float(puntaje_total or 0),
    )
    creada = obtener_evaluacion(db, evaluacion_id)
    if creada is None:
        raise ValueError("No se pudo recuperar la evaluación creada")
    return creada


def obtener_evaluacion(db: Session, evaluacion_id: int) -> Optional[dict]:
    """Retorna evaluación con sus criterios."""
    row = db.execute(text("""
        SELECT
            e.id, e.proveedor_id, p.nombre AS proveedor_nombre, p.codigo AS proveedor_codigo,
            e.anno, e.periodo, e.tipo_evaluacion,
            e.puntaje_calidad, e.puntaje_servicio, e.puntaje_embalaje, e.puntaje_total,
            e.resultado,
            e.evaluador_nombre, e.sector_evaluador,
            e.fecha_evaluacion, e.proxima_evaluacion,
            e.observaciones, e.referencias,
            e.usuario_id, e.fecha_creacion, e.fecha_actualizacion
        FROM evaluacion_proveedor_anual e
        JOIN proveedor p ON e.proveedor_id = p.id
        WHERE e.id = :id
    """), {"id": evaluacion_id}).fetchone()

    if not row:
        return None

    criterios = db.execute(text("""
        SELECT id, categoria, criterio_codigo, criterio_nombre, puntaje, comentario
        FROM evaluacion_criterio_detalle
        WHERE evaluacion_id = :eid
        ORDER BY categoria, criterio_codigo
    """), {"eid": evaluacion_id}).fetchall()

    return _fila_a_dict(row, criterios)


def listar_evaluaciones(
    db: Session,
    proveedor_id: Optional[int] = None,
    anno: Optional[int] = None,
    resultado: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    filtros = []
    params: dict = {"limit": limit, "offset": offset}

    if proveedor_id is not None:
        filtros.append("e.proveedor_id = :pid")
        params["pid"] = proveedor_id

    if anno is not None:
        filtros.append("e.anno = :anno")
        params["anno"] = anno

    if resultado is not None:
        filtros.append("e.resultado = :res")
        params["res"] = resultado

    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""

    rows = db.execute(text(f"""
        SELECT
            e.id, e.proveedor_id, p.nombre AS proveedor_nombre, p.codigo AS proveedor_codigo,
            e.anno, e.periodo, e.tipo_evaluacion,
            e.puntaje_calidad, e.puntaje_servicio, e.puntaje_embalaje, e.puntaje_total,
            e.resultado,
            e.evaluador_nombre, e.sector_evaluador,
            e.fecha_evaluacion, e.proxima_evaluacion,
            e.observaciones, e.referencias,
            e.usuario_id, e.fecha_creacion, e.fecha_actualizacion
        FROM evaluacion_proveedor_anual e
        JOIN proveedor p ON e.proveedor_id = p.id
        {where}
        ORDER BY e.anno DESC, e.periodo DESC, p.nombre ASC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    return [_fila_a_dict(r, []) for r in rows]


def eliminar_evaluacion(db: Session, evaluacion_id: int) -> bool:
    existe = db.execute(
        text("SELECT id FROM evaluacion_proveedor_anual WHERE id = :id"),
        {"id": evaluacion_id},
    ).fetchone()
    if not existe:
        return False

    db.execute(
        text("DELETE FROM evaluacion_proveedor_anual WHERE id = :id"),
        {"id": evaluacion_id},
    )
    db.commit()
    return True


def actualizar_evaluacion(
    db: Session, evaluacion_id: int, datos: dict
) -> Optional[dict]:
    """Actualiza una evaluación existente y recalcula puntaje/resultado."""
    actual = db.execute(
        text("""
        SELECT
            id, proveedor_id, anno, periodo, tipo_evaluacion,
            puntaje_calidad, puntaje_servicio, puntaje_embalaje,
            evaluador_nombre, sector_evaluador,
            fecha_evaluacion, proxima_evaluacion,
            observaciones, referencias
        FROM evaluacion_proveedor_anual
        WHERE id = :id
    """),
        {"id": evaluacion_id},
    ).fetchone()

    if not actual:
        return None

    payload = {
        "proveedor_id": datos.get("proveedor_id", actual[1]),
        "anno": datos.get("anno", actual[2]),
        "periodo": datos.get("periodo", actual[3]),
        "tipo_evaluacion": datos.get("tipo_evaluacion", actual[4]),
        "puntaje_calidad": datos.get("puntaje_calidad", _dec(actual[5])),
        "puntaje_servicio": datos.get("puntaje_servicio", _dec(actual[6])),
        "puntaje_embalaje": datos.get("puntaje_embalaje", _dec(actual[7])),
        "evaluador_nombre": datos.get("evaluador_nombre", actual[8]),
        "sector_evaluador": datos.get("sector_evaluador", actual[9]),
        "fecha_evaluacion": datos.get("fecha_evaluacion", actual[10]),
        "proxima_evaluacion": datos.get("proxima_evaluacion", actual[11]),
        "observaciones": datos.get("observaciones", actual[12]),
        "referencias": datos.get("referencias", actual[13]),
    }

    puntaje_total = _calcular_total(
        payload.get("puntaje_calidad"),
        payload.get("puntaje_servicio"),
        payload.get("puntaje_embalaje"),
    )
    resultado = clasificar_resultado(puntaje_total)

    db.execute(
        text("""
        UPDATE evaluacion_proveedor_anual
        SET
            proveedor_id = :proveedor_id,
            anno = :anno,
            periodo = :periodo,
            tipo_evaluacion = :tipo_evaluacion,
            puntaje_calidad = :puntaje_calidad,
            puntaje_servicio = :puntaje_servicio,
            puntaje_embalaje = :puntaje_embalaje,
            puntaje_total = :puntaje_total,
            resultado = :resultado,
            evaluador_nombre = :evaluador_nombre,
            sector_evaluador = :sector_evaluador,
            fecha_evaluacion = :fecha_evaluacion,
            proxima_evaluacion = :proxima_evaluacion,
            observaciones = :observaciones,
            referencias = :referencias,
            fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = :id
    """),
        {
            "id": evaluacion_id,
            "puntaje_total": puntaje_total,
            "resultado": resultado,
            **payload,
        },
    )

    if resultado:
        db.execute(
            text("""
            UPDATE proveedor
            SET estado_calificacion = :res
            WHERE id = :pid
        """),
            {"res": resultado, "pid": payload["proveedor_id"]},
        )

    db.commit()
    return obtener_evaluacion(db, evaluacion_id)


# ---------------------------------------------------------------------------
# Historial del proveedor (útil para el panel lateral)
# ---------------------------------------------------------------------------

def historial_proveedor(
    db: Session,
    proveedor_id: int,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> list[dict]:
    filtros = ["proveedor_id = :pid"]
    params: dict = {"pid": proveedor_id}

    if desde is not None:
        filtros.append(
            "COALESCE(fecha_evaluacion, STR_TO_DATE(CONCAT(anno, '-01-01'), '%Y-%m-%d')) >= :desde"
        )
        params["desde"] = desde
    if hasta is not None:
        filtros.append(
            "COALESCE(fecha_evaluacion, STR_TO_DATE(CONCAT(anno, '-01-01'), '%Y-%m-%d')) <= :hasta"
        )
        params["hasta"] = hasta

    where_clause = " AND ".join(filtros)

    rows = db.execute(text(f"""
        SELECT
            id, anno, periodo, tipo_evaluacion,
            puntaje_calidad, puntaje_servicio, puntaje_embalaje, puntaje_total,
            resultado, evaluador_nombre, sector_evaluador,
            fecha_evaluacion, proxima_evaluacion, observaciones
        FROM evaluacion_proveedor_anual
        WHERE {where_clause}
        ORDER BY anno DESC, periodo DESC
    """), params).fetchall()

    return [
        {
            "id": r[0], "anno": r[1], "periodo": r[2], "tipo_evaluacion": r[3],
            "puntaje_calidad": _dec(r[4]), "puntaje_servicio": _dec(r[5]),
            "puntaje_embalaje": _dec(r[6]), "puntaje_total": _dec(r[7]),
            "resultado": r[8], "evaluador_nombre": r[9], "sector_evaluador": r[10],
            "fecha_evaluacion": str(r[11]) if r[11] else None,
            "proxima_evaluacion": str(r[12]) if r[12] else None,
            "observaciones": r[13],
        }
        for r in rows
    ]


def ranking_proveedores_periodo(db: Session, desde: date, hasta: date) -> dict:
    """
    Retorna ranking agregado por proveedor en un rango de fechas.

    - mejores_10: promedio de puntaje_total descendente
    - peores_20: promedio de puntaje_total ascendente
    """
    rows = db.execute(
        text(
            """
            SELECT
                p.id AS proveedor_id,
                p.codigo AS proveedor_codigo,
                p.nombre AS proveedor_nombre,
                COUNT(*) AS cantidad_evaluaciones,
                AVG(e.puntaje_total) AS puntaje_promedio,
                MIN(e.puntaje_total) AS puntaje_minimo,
                MAX(e.puntaje_total) AS puntaje_maximo
            FROM evaluacion_proveedor_anual e
            JOIN proveedor p ON p.id = e.proveedor_id
            WHERE e.puntaje_total IS NOT NULL
              AND COALESCE(
                    e.fecha_evaluacion,
                    STR_TO_DATE(CONCAT(e.anno, '-01-01'), '%Y-%m-%d')
                  ) BETWEEN :desde AND :hasta
            GROUP BY p.id, p.codigo, p.nombre
            """
        ),
        {"desde": desde, "hasta": hasta},
    ).mappings().all()

    items = [
        {
            "proveedor_id": int(r["proveedor_id"]),
            "proveedor_codigo": r["proveedor_codigo"],
            "proveedor_nombre": r["proveedor_nombre"],
            "cantidad_evaluaciones": int(r["cantidad_evaluaciones"] or 0),
            "puntaje_promedio": _dec(r["puntaje_promedio"]),
            "puntaje_minimo": _dec(r["puntaje_minimo"]),
            "puntaje_maximo": _dec(r["puntaje_maximo"]),
        }
        for r in rows
    ]

    mejores_10 = sorted(
        items,
        key=lambda x: (x["puntaje_promedio"] if x["puntaje_promedio"] is not None else -1),
        reverse=True,
    )[:10]
    peores_20 = sorted(
        items,
        key=lambda x: (x["puntaje_promedio"] if x["puntaje_promedio"] is not None else 999),
    )[:20]

    total_evaluaciones = sum(i["cantidad_evaluaciones"] for i in items)
    if total_evaluaciones > 0:
        sumatoria_ponderada = sum(
            (i["puntaje_promedio"] or 0.0) * i["cantidad_evaluaciones"] for i in items
        )
        promedio_general = round(sumatoria_ponderada / total_evaluaciones, 2)
    else:
        promedio_general = None

    return {
        "desde": str(desde),
        "hasta": str(hasta),
        "total_proveedores": len(items),
        "promedio_general": promedio_general,
        "mejores_10": mejores_10,
        "peores_20": peores_20,
    }


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _calcular_total(
    calidad: Optional[float],
    servicio: Optional[float],
    embalaje: Optional[float],
) -> Optional[Decimal]:
    """Suma simple de los tres puntajes parciales ya ponderados."""
    if calidad is None and servicio is None and embalaje is None:
        return None
    total = Decimal(str(calidad or 0)) + Decimal(str(servicio or 0)) + Decimal(str(embalaje or 0))
    return total.quantize(Decimal("0.01"))


def _dec(v) -> Optional[float]:
    return float(v) if v is not None else None


def _fila_a_dict(row, criterios) -> dict:
    return {
        "id": row[0],
        "proveedor_id": row[1],
        "proveedor_nombre": row[2],
        "proveedor_codigo": row[3],
        "anno": row[4],
        "periodo": row[5],
        "tipo_evaluacion": row[6],
        "puntaje_calidad": _dec(row[7]),
        "puntaje_servicio": _dec(row[8]),
        "puntaje_embalaje": _dec(row[9]),
        "puntaje_total": _dec(row[10]),
        "resultado": row[11],
        "evaluador_nombre": row[12],
        "sector_evaluador": row[13],
        "fecha_evaluacion": str(row[14]) if row[14] else None,
        "proxima_evaluacion": str(row[15]) if row[15] else None,
        "observaciones": row[16],
        "referencias": row[17],
        "usuario_id": row[18],
        "fecha_creacion": row[19].isoformat() if row[19] else None,
        "fecha_actualizacion": row[20].isoformat() if row[20] else None,
        "criterios": [
            {
                "id": c[0],
                "categoria": c[1],
                "criterio_codigo": c[2],
                "criterio_nombre": c[3],
                "puntaje": _dec(c[4]),
                "comentario": c[5],
            }
            for c in criterios
        ],
    }
