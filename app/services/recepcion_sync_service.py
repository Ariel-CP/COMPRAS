"""
Servicio de sincronización: Access (CONTROL DE RECEPCION) → recepcion_staging.

Diseñado para ejecutarse automáticamente cada noche a las 22:00.
Usa SHA-256 por fila para idempotencia: re-correr el job nunca duplica datos.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de rutas (ajustar si cambia la ubicación del archivo)
# ---------------------------------------------------------------------------
RUTA_ACCDB = (
    r"R:\COMPARTIR-Calidad-ID\CALIDAD\Ecotermo Server"
    r"\Control de Recepción Server\Control de Recepción Database.accdb"
)
TABLA_ACCESS = "CONTROL DE RECEPCION"


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _safe_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _generar_hash_fila(datos: dict) -> str:
    """SHA-256 del contenido de la fila (reproducible)."""
    serializado = json.dumps(datos, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Lectura del Access
# ---------------------------------------------------------------------------

def leer_tabla_access(ruta: str = RUTA_ACCDB, tabla: str = TABLA_ACCESS) -> list[dict]:
    """
    Abre el archivo .accdb con pyodbc y retorna todas las filas como lista de dicts.
    Levanta FileNotFoundError si el archivo no existe o no es accesible.
    """
    import os

    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Archivo Access no encontrado: {ruta}")

    try:
        import pyodbc  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyodbc no está instalado. Ejecutá: pip install pyodbc") from exc

    conn_str = (
        f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};"
        f"DBQ={ruta};"
        f"Exclusive=0;"
    )
    try:
        conn = pyodbc.connect(conn_str)
    except Exception as exc:
        raise ConnectionError(f"No se pudo conectar al Access: {exc}") from exc

    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM [{tabla}]")
        columnas = [desc[0] for desc in cursor.description]
        filas = [dict(zip(columnas, row)) for row in cursor.fetchall()]
        logger.info("Access: %d filas leídas de [%s]", len(filas), tabla)
        return filas
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Mapeo Access → staging
# ---------------------------------------------------------------------------

# Candidatos de nombres de columnas para cada campo semántico.
# Se prueban en orden; se usa el primero que exista en la fila.
_CAMPO_MAP: dict[str, list[str]] = {
    "id_recepcion_original":    ["Id", "ID", "id"],
    "proveedor_codigo":         ["Proveedor_Codigo", "Codigo_Proveedor", "PROVEEDOR_CODIGO", "CODIGO"],
    "proveedor_nombre":         ["Proveedor_Nombre", "Nombre_Proveedor", "PROVEEDOR", "Proveedor"],
    "producto_codigo":          ["Producto_Codigo", "Codigo_Producto", "PRODUCTO_CODIGO", "ARTICULO"],
    "producto_nombre":          ["Producto_Nombre", "Nombre_Producto", "PRODUCTO", "Producto"],
    "cantidad_solicitada":      ["Cantidad_Solicitada", "CANTIDAD_SOLICITADA", "Cant_Sol"],
    "cantidad_recibida":        ["Cantidad_Recibida", "CANTIDAD_RECIBIDA", "Cant_Rec"],
    "lote_numero":              ["Lote_Numero", "Lote", "LOTE", "LOTE_NUMERO"],
    "fecha_vencimiento":        ["Fecha_Vencimiento", "FECHA_VENCIMIENTO", "Fec_Venc"],
    "fecha_recepcion_original": ["Fecha_Recepcion", "FECHA_RECEPCION", "Fecha_Ingreso", "FECHA DE ENTREGA"],
    "estado_inspeccion_original": ["Estado_Inspeccion", "ESTADO_INSPECCION", "Estado", "PLAN MUESTREO"],
    "calidad_ok":               ["Calidad_OK", "CALIDAD_OK", "Calidad", "TieneCertificado"],
    "codigo_no_conformidad":    ["Codigo_NC", "CODIGO_NC", "NC"],
    "descripcion_no_conformidad": ["Descripcion_NC", "DESC_NC", "Descripcion"],
    "notas_adicionales":        ["Notas", "NOTAS", "Observaciones", "OBSERVACIONES"],
    "inspector_nombre":         ["Inspector_Nombre", "Inspector", "INSPECTOR"],
}


def _resolver_campo(fila: dict, candidatos: list[str]) -> Any:
    """Retorna el valor del primer candidato encontrado en la fila."""
    for nombre in candidatos:
        if nombre in fila:
            return fila[nombre]
    return None


def mapear_fila_a_staging(fila: dict) -> dict:
    """Convierte una fila cruda del Access al formato de recepcion_staging."""
    calidad_raw = _resolver_campo(fila, _CAMPO_MAP["calidad_ok"])
    calidad_ok: Optional[int]
    if calidad_raw is None:
        calidad_ok = None
    elif isinstance(calidad_raw, bool):
        calidad_ok = 1 if calidad_raw else 0
    else:
        calidad_ok = 1 if str(calidad_raw).strip().lower() in ("1", "true", "si", "sí", "ok", "s") else 0

    return {
        "id_recepcion_original":    _safe_str(_resolver_campo(fila, _CAMPO_MAP["id_recepcion_original"])),
        "proveedor_codigo":         _safe_str(_resolver_campo(fila, _CAMPO_MAP["proveedor_codigo"])),
        "proveedor_nombre":         _safe_str(_resolver_campo(fila, _CAMPO_MAP["proveedor_nombre"])),
        "producto_codigo":          _safe_str(_resolver_campo(fila, _CAMPO_MAP["producto_codigo"])),
        "producto_nombre":          _safe_str(_resolver_campo(fila, _CAMPO_MAP["producto_nombre"])),
        "cantidad_solicitada":      _safe_decimal(_resolver_campo(fila, _CAMPO_MAP["cantidad_solicitada"])),
        "cantidad_recibida":        _safe_decimal(_resolver_campo(fila, _CAMPO_MAP["cantidad_recibida"])),
        "lote_numero":              _safe_str(_resolver_campo(fila, _CAMPO_MAP["lote_numero"])),
        "fecha_vencimiento":        _resolver_campo(fila, _CAMPO_MAP["fecha_vencimiento"]),
        "fecha_recepcion_original": _resolver_campo(fila, _CAMPO_MAP["fecha_recepcion_original"]),
        "estado_inspeccion_original": _safe_str(_resolver_campo(fila, _CAMPO_MAP["estado_inspeccion_original"])),
        "calidad_ok":               calidad_ok,
        "codigo_no_conformidad":    _safe_str(_resolver_campo(fila, _CAMPO_MAP["codigo_no_conformidad"])),
        "descripcion_no_conformidad": _safe_str(_resolver_campo(fila, _CAMPO_MAP["descripcion_no_conformidad"])),
        "notas_adicionales":        _safe_str(_resolver_campo(fila, _CAMPO_MAP["notas_adicionales"])),
        "inspector_nombre":         _safe_str(_resolver_campo(fila, _CAMPO_MAP["inspector_nombre"])),
    }


# ---------------------------------------------------------------------------
# Importación a recepcion_staging
# ---------------------------------------------------------------------------

def importar_filas_a_staging(
    db: Session,
    filas_access: list[dict],
    usuario_id: int = 1,
) -> dict:
    """
    Inserta filas del Access en recepcion_staging, ignorando duplicados (por hash).
    Retorna contadores.
    """
    nuevas = 0
    duplicadas = 0
    errores: list[dict] = []

    SQL_EXISTE = text("SELECT 1 FROM recepcion_staging WHERE fila_hash = :h LIMIT 1")
    SQL_INSERT = text("""
        INSERT INTO recepcion_staging (
            fuente, fila_hash, fecha_importacion, usuario_importacion_id,
            id_recepcion_original, proveedor_codigo, proveedor_nombre,
            producto_codigo, producto_nombre,
            cantidad_solicitada, cantidad_recibida,
            lote_numero, fecha_vencimiento, fecha_recepcion_original,
            estado_inspeccion_original, calidad_ok,
            codigo_no_conformidad, descripcion_no_conformidad,
            notas_adicionales, inspector_nombre,
            estado_procesamiento
        ) VALUES (
            'ACCESS_CONTROL_RECEPCION', :fila_hash, NOW(), :usuario_id,
            :id_recepcion_original, :proveedor_codigo, :proveedor_nombre,
            :producto_codigo, :producto_nombre,
            :cantidad_solicitada, :cantidad_recibida,
            :lote_numero, :fecha_vencimiento, :fecha_recepcion_original,
            :estado_inspeccion_original, :calidad_ok,
            :codigo_no_conformidad, :descripcion_no_conformidad,
            :notas_adicionales, :inspector_nombre,
            'PENDIENTE'
        )
    """)

    for idx, fila_raw in enumerate(filas_access):
        try:
            fila_hash = _generar_hash_fila(fila_raw)

            existe = db.execute(SQL_EXISTE, {"h": fila_hash}).first()
            if existe:
                duplicadas += 1
                continue

            datos = mapear_fila_a_staging(fila_raw)
            datos["fila_hash"] = fila_hash
            datos["usuario_id"] = usuario_id

            db.execute(SQL_INSERT, datos)
            nuevas += 1

        except SQLAlchemyError as exc:
            logger.warning("Fila %d: error SQL: %s", idx + 1, exc)
            errores.append({"fila": idx + 1, "error": str(exc)})
        except Exception as exc:
            logger.warning("Fila %d: error inesperado: %s", idx + 1, exc)
            errores.append({"fila": idx + 1, "error": str(exc)})

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Error en commit de staging: %s", exc)
        raise

    logger.info(
        "Staging → nuevas: %d | duplicadas: %d | errores: %d",
        nuevas, duplicadas, len(errores),
    )
    return {"nuevas_insertadas": nuevas, "duplicadas": duplicadas, "errores": errores}


# ---------------------------------------------------------------------------
# Registro en sincronizacion_log
# ---------------------------------------------------------------------------

def _registrar_log(
    db: Session,
    fecha_inicio: datetime,
    fecha_fin: datetime,
    resultado_import: dict,
    estado: str,
    mensaje_error: Optional[str],
    usuario_id: int,
) -> None:
    duracion = (fecha_fin - fecha_inicio).total_seconds()
    total_leidas = resultado_import.get("nuevas_insertadas", 0) + resultado_import.get("duplicadas", 0)

    db.execute(
        text("""
            INSERT INTO sincronizacion_log (
                fecha_inicio, fecha_fin, duracion_segundos,
                filas_leidas, filas_nuevas, filas_duplicadas, filas_errores,
                estado, mensaje_error, usuario_id
            ) VALUES (
                :fi, :ff, :dur,
                :leidas, :nuevas, :dup, :err,
                :estado, :msg, :uid
            )
        """),
        {
            "fi": fecha_inicio,
            "ff": fecha_fin,
            "dur": duracion,
            "leidas": total_leidas,
            "nuevas": resultado_import.get("nuevas_insertadas", 0),
            "dup": resultado_import.get("duplicadas", 0),
            "err": len(resultado_import.get("errores", [])),
            "estado": estado,
            "msg": mensaje_error,
            "uid": usuario_id,
        },
    )
    db.commit()


# ---------------------------------------------------------------------------
# Ciclo completo de sincronización
# ---------------------------------------------------------------------------

def sincronizar_ciclo_completo(db: Session, usuario_id: int = 1) -> dict:
    """
    Ciclo completo: lee Access → inserta staging → normaliza → registra log.
    Retorna un dict con el resumen de la operación.
    """
    inicio = datetime.now()
    logger.info("=" * 70)
    logger.info("[SYNC] INICIANDO  %s", inicio.isoformat())
    logger.info("=" * 70)

    resultado_import: dict = {"nuevas_insertadas": 0, "duplicadas": 0, "errores": []}

    try:
        # 1 – Leer Access
        logger.info("[SYNC 1/3] Leyendo Access …")
        filas = leer_tabla_access()

        # 2 – Importar a staging
        logger.info("[SYNC 2/3] Importando %d filas a staging …", len(filas))
        resultado_import = importar_filas_a_staging(db, filas, usuario_id)

        # 3 – Normalizar staging
        logger.info("[SYNC 3/3] Normalizando staging …")
        from app.services.recepcion_normalization_service import normalizar_todo_staging
        resultado_norm = normalizar_todo_staging()

        duracion = (datetime.now() - inicio).total_seconds()
        estado = "PARCIAL" if resultado_import["errores"] else "EXITOSA"

        try:
            _registrar_log(db, inicio, datetime.now(), resultado_import, estado, None, usuario_id)
        except Exception as exc:
            logger.warning("No se pudo registrar log de sync: %s", exc)

        logger.info(
            "[SYNC] COMPLETADA en %.1fs | nuevas=%d duplicadas=%d errores=%d",
            duracion,
            resultado_import["nuevas_insertadas"],
            resultado_import["duplicadas"],
            len(resultado_import["errores"]),
        )

        return {
            "exitoso": True,
            "filas_leidas": len(filas),
            "nuevas_insertadas": resultado_import["nuevas_insertadas"],
            "duplicadas": resultado_import["duplicadas"],
            "errores_import": len(resultado_import["errores"]),
            "normalizadas_exitosas": resultado_norm.get("exitosas", 0),
            "normalizadas_rechazadas": resultado_norm.get("rechazadas", 0),
            "duracion_segundos": duracion,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as exc:
        duracion = (datetime.now() - inicio).total_seconds()
        logger.error("[SYNC] ERROR: %s", exc, exc_info=True)

        try:
            _registrar_log(
                db, inicio, datetime.now(),
                resultado_import, "ERROR", str(exc), usuario_id,
            )
        except Exception:
            pass

        return {
            "exitoso": False,
            "error": str(exc),
            "duracion_segundos": duracion,
            "timestamp": datetime.now().isoformat(),
        }
