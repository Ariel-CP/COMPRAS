"""
Importación del historial de evaluaciones de proveedores desde archivos tabulares
(CSV o XLSX) exportados de Power BI.

Origen: tabla "CONTROL DE RECEPCION" exportada como CSV (sep=;, decimal=,)
o planilla XLSX equivalente.
Lógica:
  - Cada fila es una recepción individual de material.
  - Se deduplica por Codigo Proveedor + Año → 1 evaluación anual por proveedor.
  - Los puntajes (PuntajeCalidadPonderado, PuntajeEntregaPonderado, etc.) son
    constantes por proveedor+año (calculados por Power BI), se toma el último valor.
  - Idempotente: si ya existe la evaluación (proveedor_id + anno + periodo=0), se salta.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import pandas as pd

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

IMPORT_REF_CSV = "IMPORT_POWERBI_CSV"
IMPORT_REF_XLSX = "IMPORT_POWERBI_XLSX"

COLUMNAS_REQUERIDAS = {
    "codigo_proveedor": ("Codigo Proveedor", "CodigoProveedor", "codigo_proveedor"),
    "anno": ("Año", "Anno", "Year", "Anio"),
}

COLUMNAS_RECOMENDADAS = {
    "puntaje_calidad": ("PuntajeCalidadPonderado", "Puntaje Calidad Ponderado"),
    "puntaje_entrega": ("PuntajeEntregaPonderado", "Puntaje Entrega Ponderado"),
    "puntaje_certificado": (
        "PuntajeCertificadoPonderado",
        "Puntaje Certificado Ponderado",
    ),
    "puntaje_total": ("PuntajeTotalProveedor", "Puntaje Total Proveedor"),
    "clasificacion": ("ClasificacionProveedor", "Clasificacion Proveedor"),
    "controlo": ("Controlo", "controlo"),
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _safe_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    # pandas puede dejar NaN
    try:
        import math

        if math.isnan(float(v)):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return Decimal(str(v).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none", "") else None


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def _mapear_clasificacion(v: Any) -> Optional[str]:
    """Mapea texto de ClasificacionProveedor → ENUM de BD."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if "condicional" in s:
        return "APROB_CONDICIONAL"
    if "apto" in s and "no" not in s:
        return "APROBADO"
    if "no" in s and "apto" in s:
        return "NO_APTO"
    if s == "aprobado":
        return "APROBADO"
    return None


# ---------------------------------------------------------------------------
# Lectura y deduplicación del CSV
# ---------------------------------------------------------------------------


def _leer_csv(contenido: bytes) -> "pd.DataFrame":
    """
    Lee el CSV con separador ; y decimal ,
    Prueba encodings utf-8, latin-1, cp1252 en ese orden.
    """
    import pandas as pd

    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(
                io.BytesIO(contenido),
                sep=";",
                decimal=",",
                encoding=enc,
                low_memory=False,
            )
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo decodificar el CSV (probados utf-8, latin-1, cp1252)")


def _leer_xlsx(contenido: bytes) -> "pd.DataFrame":
    """
    Lee XLSX y devuelve DataFrame.

    Se usa dtype=object para preservar formatos y aplicar conversiones seguras
    posteriormente con _safe_int/_safe_decimal.
    """
    import pandas as pd

    try:
        return pd.read_excel(io.BytesIO(contenido), dtype=object)
    except Exception as exc:  # pragma: no cover - errores de archivo corrupto/hoja inválida
        raise ValueError(f"No se pudo leer el XLSX: {exc}") from exc


def _deduplicar(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Agrupa por Codigo Proveedor + Año y toma la última fila de cada grupo.
    Los puntajes anuales son constantes dentro del grupo, pero Controlo puede variar.
    """
    col_codigo = _buscar_col(
        df, "Codigo Proveedor", "CodigoProveedor", "codigo_proveedor"
    )
    col_anno = _buscar_col(df, "Año", "Anno", "Year", "Anio")

    if col_codigo is None or col_anno is None:
        raise ValueError(
            f"No se encontraron las columnas 'Codigo Proveedor' y/o 'Año' en el CSV. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    return df.groupby([col_codigo, col_anno], sort=False).last().reset_index()


def _buscar_col(df: "pd.DataFrame", *candidatos: str) -> Optional[str]:
    """Busca el primer candidato (case-insensitive) en las columnas del DataFrame."""
    cols_lower = {c.lower(): c for c in df.columns}
    for c in candidatos:
        found = cols_lower.get(c.lower())
        if found is not None:
            return found
    return None


def _mapa_columnas_detectadas(df: "pd.DataFrame") -> dict[str, Optional[str]]:
    """Devuelve el mapeo de columnas detectadas para requeridas/recomendadas."""
    mapping: dict[str, Optional[str]] = {}
    for key, candidatos in {**COLUMNAS_REQUERIDAS, **COLUMNAS_RECOMENDADAS}.items():
        mapping[key] = _buscar_col(df, *candidatos)
    return mapping


# ---------------------------------------------------------------------------
# Lookup de proveedores
# ---------------------------------------------------------------------------


def _build_codigo_map(db: Session) -> dict[str, int]:
    rows = db.execute(text("SELECT id, codigo FROM proveedor")).fetchall()
    return {str(r.codigo).strip(): r.id for r in rows if r.codigo}


# ---------------------------------------------------------------------------
# Inserción idempotente
# ---------------------------------------------------------------------------


def _insertar_evaluacion(db: Session, datos: dict) -> tuple[bool, str]:
    """Inserta 1 evaluación. Retorna (ok, mensaje)."""
    existe = db.execute(
        text("""
        SELECT id FROM evaluacion_proveedor_anual
        WHERE proveedor_id = :pid AND anno = :anno AND periodo = :periodo
    """),
        {
            "pid": datos["proveedor_id"],
            "anno": datos["anno"],
            "periodo": datos["periodo"],
        },
    ).fetchone()

    if existe:
        return False, "duplicado"

    try:
        db.execute(
            text("""
            INSERT INTO evaluacion_proveedor_anual (
                proveedor_id, anno, periodo, tipo_evaluacion,
                puntaje_calidad, puntaje_servicio, puntaje_embalaje, puntaje_total,
                resultado, evaluador_nombre, referencias, usuario_id
            ) VALUES (
                :proveedor_id, :anno, :periodo, :tipo_evaluacion,
                :puntaje_calidad, :puntaje_servicio, :puntaje_embalaje, :puntaje_total,
                :resultado, :evaluador_nombre, :referencias, :usuario_id
            )
        """),
            datos,
        )

        # Actualizar estado_calificacion en proveedor
        if datos.get("resultado"):
            db.execute(
                text("""
                UPDATE proveedor SET estado_calificacion = :res WHERE id = :pid
            """),
                {"res": datos["resultado"], "pid": datos["proveedor_id"]},
            )

        return True, "ok"

    except Exception as exc:
        logger.warning(
            "Error insertando evaluación proveedor_id=%s anno=%s: %s",
            datos.get("proveedor_id"),
            datos.get("anno"),
            exc,
        )
        return False, str(exc)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def _importar_desde_dataframe(
    db: Session,
    df_raw: "pd.DataFrame",
    usuario_id: Optional[int],
    origen: str,
) -> dict:
    """Procesa un DataFrame tabular e importa una evaluación anual por proveedor."""
    inicio = datetime.now()

    stats: dict = {
        "origen": origen,
        "filas_csv": 0,
        "proveedores_unicos": 0,
        "importadas": 0,
        "duplicadas": 0,
        "sin_proveedor": 0,
        "errores": 0,
        "errores_detalle": [],
        "duracion_segundos": 0.0,
    }

    stats["filas_csv"] = len(df_raw)

    # 2) Validar columnas requeridas
    detectadas = _mapa_columnas_detectadas(df_raw)
    faltantes_requeridas = [k for k in COLUMNAS_REQUERIDAS if not detectadas.get(k)]
    if faltantes_requeridas:
        stats["errores"] = 1
        stats["errores_detalle"].append(
            "Faltan columnas requeridas: " + ", ".join(faltantes_requeridas)
        )
        return stats

    # 3) Deduplicar por proveedor + año
    try:
        df = _deduplicar(df_raw)
    except ValueError as exc:
        stats["errores"] = 1
        stats["errores_detalle"].append(str(exc))
        return stats

    stats["proveedores_unicos"] = len(df)
    logger.info(
        "%s: %d filas, %d combinaciones proveedor+año",
        origen,
        stats["filas_csv"],
        len(df),
    )

    # 4) Detectar nombres de columnas relevantes
    col_codigo = _buscar_col(df, "Codigo Proveedor", "CodigoProveedor")
    col_anno = _buscar_col(df, "Año", "Anno", "Year", "Anio")
    col_calidad = _buscar_col(
        df, "PuntajeCalidadPonderado", "Puntaje Calidad Ponderado"
    )
    col_entrega = _buscar_col(
        df, "PuntajeEntregaPonderado", "Puntaje Entrega Ponderado"
    )
    col_cert = _buscar_col(
        df, "PuntajeCertificadoPonderado", "Puntaje Certificado Ponderado"
    )
    col_total = _buscar_col(df, "PuntajeTotalProveedor", "Puntaje Total Proveedor")
    col_clasif = _buscar_col(df, "ClasificacionProveedor", "Clasificacion Proveedor")
    col_controlo = _buscar_col(df, "Controlo", "controlo")

    # 5) Mapa de códigos de proveedor
    codigo_map = _build_codigo_map(db)

    referencia_origen = IMPORT_REF_CSV if origen == "csv" else IMPORT_REF_XLSX

    # 6) Procesar cada fila deduplicada
    for _, row in df.iterrows():
        codigo = _safe_str(row.get(col_codigo)) if col_codigo else None
        anno = _safe_int(row.get(col_anno)) if col_anno else None

        if not codigo or not anno:
            stats["sin_proveedor"] += 1
            continue

        proveedor_id = codigo_map.get(codigo)
        if proveedor_id is None:
            stats["sin_proveedor"] += 1
            logger.debug("Proveedor codigo=%s no encontrado en BD", codigo)
            continue

        p_cal = _safe_decimal(row.get(col_calidad) if col_calidad else None)
        p_ser = _safe_decimal(row.get(col_entrega) if col_entrega else None)
        p_emb = _safe_decimal(row.get(col_cert) if col_cert else None)
        p_tot = _safe_decimal(row.get(col_total) if col_total else None)
        clasif = _mapear_clasificacion(row.get(col_clasif) if col_clasif else None)

        # Si puntaje_total no está en archivo, calcularlo
        if (
            p_tot is None
            and p_cal is not None
            and p_ser is not None
            and p_emb is not None
        ):
            p_tot = p_cal + p_ser + p_emb

        # Si clasificación no viene, aplicar regla ISO
        if clasif is None and p_tot is not None:
            if p_tot >= Decimal("70"):
                clasif = "APROBADO"
            elif p_tot >= Decimal("55"):
                clasif = "APROB_CONDICIONAL"
            else:
                clasif = "NO_APTO"

        evaluador = _safe_str(row.get(col_controlo) if col_controlo else None)

        datos = {
            "proveedor_id": proveedor_id,
            "anno": anno,
            "periodo": 0,
            "tipo_evaluacion": "ANUAL",
            "puntaje_calidad": float(p_cal) if p_cal is not None else None,
            "puntaje_servicio": float(p_ser) if p_ser is not None else None,
            "puntaje_embalaje": float(p_emb) if p_emb is not None else None,
            "puntaje_total": float(p_tot) if p_tot is not None else None,
            "resultado": clasif,
            "evaluador_nombre": evaluador,
            "referencias": referencia_origen,
            "usuario_id": usuario_id,
        }

        ok, msg = _insertar_evaluacion(db, datos)
        if ok:
            stats["importadas"] += 1
        elif msg == "duplicado":
            stats["duplicadas"] += 1
        else:
            stats["errores"] += 1
            if len(stats["errores_detalle"]) < 20:
                stats["errores_detalle"].append(f"prov={codigo} año={anno}: {msg}")

    # 7) Commit
    if stats["importadas"] > 0:
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Error en commit final: %s", exc)
            stats["errores"] += 1
            stats["errores_detalle"].append(f"Commit fallido: {exc}")

    stats["duracion_segundos"] = round((datetime.now() - inicio).total_seconds(), 2)
    logger.info(
        "%s import finalizado: importadas=%d duplicadas=%d sin_proveedor=%d errores=%d",
        origen,
        stats["importadas"],
        stats["duplicadas"],
        stats["sin_proveedor"],
        stats["errores"],
    )
    return stats


def prevalidar_archivo_importacion(contenido: bytes, extension: str) -> dict:
    """Valida estructura del archivo antes de importar y devuelve diagnóstico legible."""
    ext = (extension or "").lower().strip(".")
    if ext not in ("csv", "xlsx"):
        return {
            "ok": False,
            "extension": ext,
            "error": "Formato no soportado. Usa .csv o .xlsx",
            "columnas": [],
            "mapeo": {},
            "faltantes_requeridas": [*COLUMNAS_REQUERIDAS.keys()],
            "faltantes_recomendadas": [*COLUMNAS_RECOMENDADAS.keys()],
            "filas_archivo": 0,
        }

    try:
        df = _leer_csv(contenido) if ext == "csv" else _leer_xlsx(contenido)
    except Exception as exc:
        return {
            "ok": False,
            "extension": ext,
            "error": str(exc),
            "columnas": [],
            "mapeo": {},
            "faltantes_requeridas": [*COLUMNAS_REQUERIDAS.keys()],
            "faltantes_recomendadas": [*COLUMNAS_RECOMENDADAS.keys()],
            "filas_archivo": 0,
        }

    mapeo = _mapa_columnas_detectadas(df)
    faltantes_requeridas = [k for k in COLUMNAS_REQUERIDAS if not mapeo.get(k)]
    faltantes_recomendadas = [k for k in COLUMNAS_RECOMENDADAS if not mapeo.get(k)]

    return {
        "ok": len(faltantes_requeridas) == 0,
        "extension": ext,
        "error": None,
        "columnas": [str(c) for c in df.columns],
        "mapeo": mapeo,
        "faltantes_requeridas": faltantes_requeridas,
        "faltantes_recomendadas": faltantes_recomendadas,
        "filas_archivo": int(len(df)),
    }


def limpiar_evaluaciones_importadas(db: Session, incluir_legacy: bool = False) -> dict:
    """
    Elimina evaluaciones importadas para volver a cargar en limpio.

    - Siempre borra registros marcados por referencias IMPORT_POWERBI_CSV/XLSX.
    - Opcionalmente borra legado detectado por heurística:
      periodo=0, tipo ANUAL y sin detalle de criterios.
    """
    filtros = [
        "e.referencias = :ref_csv OR e.referencias = :ref_xlsx",
    ]
    params: dict[str, object] = {
        "ref_csv": IMPORT_REF_CSV,
        "ref_xlsx": IMPORT_REF_XLSX,
    }

    if incluir_legacy:
        filtros.append(
            "(e.periodo = 0 AND e.tipo_evaluacion = 'ANUAL' "
            "AND NOT EXISTS (SELECT 1 FROM evaluacion_criterio_detalle d WHERE d.evaluacion_id = e.id))"
        )

    where_clause = " OR ".join(f"({f})" for f in filtros)

    candidatos = db.execute(
        text(
            f"""
            SELECT e.id, e.proveedor_id,
                   CASE
                     WHEN e.referencias = :ref_csv OR e.referencias = :ref_xlsx THEN 'marcado'
                     ELSE 'legacy'
                   END AS tipo_borrado
            FROM evaluacion_proveedor_anual e
            WHERE {where_clause}
            """
        ),
        params,
    ).mappings().all()

    if not candidatos:
        return {
            "eliminadas_total": 0,
            "eliminadas_marcadas": 0,
            "eliminadas_legacy": 0,
            "proveedores_afectados": 0,
        }

    ids = [int(r["id"]) for r in candidatos]
    proveedores = sorted({int(r["proveedor_id"]) for r in candidatos if r["proveedor_id"] is not None})
    eliminadas_marcadas = sum(1 for r in candidatos if r["tipo_borrado"] == "marcado")
    eliminadas_legacy = len(candidatos) - eliminadas_marcadas

    db.execute(
        text(
            "DELETE FROM evaluacion_proveedor_anual "
            f"WHERE id IN ({','.join(str(i) for i in ids)})"
        )
    )

    # Recalcular estado_calificacion por proveedor afectado según última evaluación restante.
    for proveedor_id in proveedores:
        ultima = db.execute(
            text(
                """
                SELECT resultado
                FROM evaluacion_proveedor_anual
                WHERE proveedor_id = :pid AND resultado IS NOT NULL
                ORDER BY anno DESC, periodo DESC, id DESC
                LIMIT 1
                """
            ),
            {"pid": proveedor_id},
        ).fetchone()
        nuevo_estado = ultima[0] if ultima else None
        db.execute(
            text(
                """
                UPDATE proveedor
                SET estado_calificacion = :estado
                WHERE id = :pid
                """
            ),
            {"estado": nuevo_estado, "pid": proveedor_id},
        )

    db.commit()

    return {
        "eliminadas_total": len(ids),
        "eliminadas_marcadas": eliminadas_marcadas,
        "eliminadas_legacy": eliminadas_legacy,
        "proveedores_afectados": len(proveedores),
    }


def importar_desde_csv(
    db: Session, contenido: bytes, usuario_id: Optional[int] = None
) -> dict:
    """
    Procesa el CSV exportado de Power BI e importa una evaluación anual por proveedor.

    Parámetros:
        db          : sesión SQLAlchemy
        contenido   : bytes del archivo CSV
        usuario_id  : ID del usuario que ejecuta la importación (opcional)

    Retorna dict con estadísticas:
        filas_csv, proveedores_unicos, importadas, duplicadas,
        sin_proveedor, errores, errores_detalle, duracion_segundos
    """
    # 1) Leer CSV
    try:
        df_raw = _leer_csv(contenido)
    except Exception as exc:
        return {
            "origen": "csv",
            "filas_csv": 0,
            "proveedores_unicos": 0,
            "importadas": 0,
            "duplicadas": 0,
            "sin_proveedor": 0,
            "errores": 1,
            "errores_detalle": [f"Error al leer CSV: {exc}"],
            "duracion_segundos": 0.0,
        }

    return _importar_desde_dataframe(db, df_raw, usuario_id=usuario_id, origen="csv")


def importar_desde_xlsx(
    db: Session, contenido: bytes, usuario_id: Optional[int] = None
) -> dict:
    """Procesa XLSX con la misma lógica de importación usada para CSV."""
    try:
        df_raw = _leer_xlsx(contenido)
    except Exception as exc:
        return {
            "origen": "xlsx",
            "filas_csv": 0,
            "proveedores_unicos": 0,
            "importadas": 0,
            "duplicadas": 0,
            "sin_proveedor": 0,
            "errores": 1,
            "errores_detalle": [f"Error al leer XLSX: {exc}"],
            "duracion_segundos": 0.0,
        }

    return _importar_desde_dataframe(db, df_raw, usuario_id=usuario_id, origen="xlsx")
