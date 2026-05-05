"""
Importación del historial de evaluaciones de proveedores desde Access (avaprov).

Archivo Access:
  R:\\COMPARTIR-Calidad-ID\\CALIDAD\\Ecotermo Server
  \\Gestión de Evaluación de Proveedores\\Evaluación de Proveedores Database.accdb

Tabla: avaprov
Ejecutable manualmente vía endpoint POST /api/evaluaciones/importar-historial.
Idempotente: si ya existe una evaluación para proveedor+año+período, la salta.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ruta del archivo Access
# ---------------------------------------------------------------------------
RUTA_ACCDB = (
    r"R:\COMPARTIR-Calidad-ID\CALIDAD\Ecotermo Server"
    r"\Gestión de Evaluación de Proveedores\Evaluación de Proveedores Database.accdb"
)
TABLA_ACCESS = "avaprov"

# ---------------------------------------------------------------------------
# Mapas de criterios (columna Access → (codigo, nombre, categoria))
# ---------------------------------------------------------------------------
CRITERIOS_CALIDAD = [
    ("Cal_Cum_Esp",   "CAL_CUM_ESP",   "Cumplimiento de especificaciones"),
    ("Cal_Cert_Cal",  "CAL_CERT_CAL",  "Certificación de calidad"),
    ("Cal_Inno",      "CAL_INNO",      "Innovación"),
]
CRITERIOS_SERVICIO = [
    ("Ser_Tie_Ent",       "SER_TIE_ENT",     "Tiempo de entrega"),
    ("Ser_Dis_Rec",       "SER_DIS_REC",     "Disponibilidad de recambios"),
    ("Ser_Rel_Pre&Mer",   "SER_REL_PRE_MER", "Relación precio/mercado"),
    ("Ser_Asi_Pos",       "SER_ASI_POS",     "Asistencia post-venta"),
    ("ser_Ent",           "SER_ENT",         "Entrega"),
    ("Ser_Con_Pag",       "SER_CON_PAG",     "Condiciones de pago"),
    ("Ser_Sto_Pro",       "SER_STO_PRO",     "Stock propio"),
    ("Ser_Com_Pro",       "SER_COM_PRO",     "Comunicación / proactividad"),
]
CRITERIOS_EMBALAJE = [
    ("Emb_Pre_Pro",  "EMB_PRE_PRO",  "Presentación del producto"),
    ("Emb_Ide",      "EMB_IDE",      "Identificación"),
    ("Emb_Tip_Emb",  "EMB_TIP_EMB",  "Tipo de embalaje"),
    ("Emb_Dur_Emb",  "EMB_DUR_EMB",  "Durabilidad del embalaje"),
]


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _safe_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _safe_date(v: Any) -> Optional[date]:
    """Convierte varios formatos de fecha a date."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _mapear_calificacion(v: Any) -> Optional[str]:
    """Mapea texto de CALIFICACION Access a nuestro ENUM."""
    if v is None:
        return None
    s = str(v).strip().upper()
    if "CONDICIONAL" in s:
        return "APROB_CONDICIONAL"
    if "APROBADO" in s or "APROBADO" in s:
        return "APROBADO"
    if "NO APTO" in s or "NO_APTO" in s:
        return "NO_APTO"
    return None


def _mapear_periodo(v: Any) -> int:
    """
    Convierte el valor PERIODO del Access a entero 0-3.
    0 = Anual, 1 = 1er Cuatrimestre, 2 = 2do, 3 = 3er.
    """
    if v is None:
        return 0
    s = str(v).strip()
    if s.startswith("1") or "1°" in s or "PRIMER" in s.upper() or s == "1":
        return 1
    if s.startswith("2") or "2°" in s or "SEGUNDO" in s.upper() or s == "2":
        return 2
    if s.startswith("3") or "3°" in s or "TERCER" in s.upper() or s == "3":
        return 3
    return 0  # Anual por defecto


def _mapear_tipo_evaluacion(v: Any, periodo: int) -> str:
    if v is not None:
        s = str(v).strip().upper()
        if "CUATRI" in s:
            return "CUATRIMESTRAL"
        if "ANUAL" in s:
            return "ANUAL"
    return "ANUAL" if periodo == 0 else "CUATRIMESTRAL"


def _get_col(fila: dict, *candidatos: str) -> Any:
    """Busca el primer candidato que exista como clave (case-insensitive)."""
    keys_lower = {k.lower(): k for k in fila}
    for c in candidatos:
        k = keys_lower.get(c.lower())
        if k is not None:
            return fila[k]
    return None


# ---------------------------------------------------------------------------
# Lectura del Access
# ---------------------------------------------------------------------------

def leer_tabla_access(ruta: str = RUTA_ACCDB, tabla: str = TABLA_ACCESS) -> list[dict]:
    """Abre el .accdb con pyodbc y retorna todas las filas como lista de dicts."""
    try:
        import pyodbc  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyodbc no está instalado. Ejecutar: pip install pyodbc") from exc

    conn_str = (
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        rf"Dbq={ruta};"
        r"Exclusive=0;"
    )
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
    except pyodbc.Error as exc:
        raise RuntimeError(f"No se puede abrir el Access: {exc}") from exc

    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM [{tabla}]")
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Resolución de proveedor_id por código
# ---------------------------------------------------------------------------

def _build_codigo_map(db: Session) -> dict[str, int]:
    """Retorna {codigo_proveedor: id} para búsqueda rápida."""
    rows = db.execute(text("SELECT id, codigo FROM proveedor")).fetchall()
    return {str(r.codigo).strip(): r.id for r in rows if r.codigo}


# ---------------------------------------------------------------------------
# Inserción de una evaluación (idempotente via UNIQUE constraint)
# ---------------------------------------------------------------------------

def _insertar_evaluacion(db: Session, datos: dict) -> tuple[bool, str]:
    """
    Inserta cabecera + criterios.
    Retorna (insertada: bool, mensaje: str).
    """
    # Verificar existencia previa
    existe = db.execute(text("""
        SELECT id FROM evaluacion_proveedor_anual
        WHERE proveedor_id = :pid AND anno = :anno AND periodo = :periodo
    """), {
        "pid":    datos["proveedor_id"],
        "anno":   datos["anno"],
        "periodo": datos["periodo"],
    }).fetchone()

    if existe:
        return False, "duplicado"

    try:
        db.execute(text("""
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
        """), datos)

        eval_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        # Insertar criterios de detalle
        for crit in datos.get("criterios", []):
            if crit.get("puntaje") is not None:
                db.execute(text("""
                    INSERT INTO evaluacion_criterio_detalle
                      (evaluacion_id, categoria, criterio_codigo, criterio_nombre, puntaje)
                    VALUES (:eid, :cat, :cod, :nom, :pts)
                """), {
                    "eid": eval_id,
                    "cat": crit["categoria"],
                    "cod": crit["criterio_codigo"],
                    "nom": crit["criterio_nombre"],
                    "pts": crit["puntaje"],
                })

        # Actualizar estado_calificacion del proveedor (solo si es la evaluación más reciente)
        if datos.get("resultado"):
            db.execute(text("""
                UPDATE proveedor SET estado_calificacion = :res
                WHERE id = :pid
            """), {"res": datos["resultado"], "pid": datos["proveedor_id"]})

        return True, "ok"

    except Exception as exc:
        logger.warning("Error insertando evaluación proveedor_id=%s anno=%s: %s",
                       datos.get("proveedor_id"), datos.get("anno"), exc)
        return False, str(exc)


# ---------------------------------------------------------------------------
# Mapeo de una fila Access → dict para DB
# ---------------------------------------------------------------------------

def _mapear_fila(fila: dict, codigo_map: dict[str, int]) -> Optional[dict]:
    """
    Convierte una fila del Access al dict que espera `_insertar_evaluacion`.
    Retorna None si no se puede resolver el proveedor.
    """
    codigo = _safe_str(_get_col(fila, "Codigo", "CODIGO", "codigo"))
    if not codigo:
        return None

    proveedor_id = codigo_map.get(codigo)
    if proveedor_id is None:
        return None

    fecha = _safe_date(_get_col(fila, "Fecha", "FECHA", "fecha"))
    anno = fecha.year if fecha else None
    if not anno:
        # Intentar extraer año de algún campo de texto
        raw = _get_col(fila, "Fecha", "FECHA")
        if raw:
            s = str(raw)
            for tok in s.split("/"):
                tok = tok.strip()
                if len(tok) == 4 and tok.isdigit():
                    anno = int(tok)
                    break
    if not anno:
        return None

    periodo_raw = _get_col(fila, "PERIODO", "Periodo", "periodo")
    periodo = _mapear_periodo(periodo_raw)
    tipo_raw = _get_col(fila, "Tipo_Eva", "TIPO_EVA", "tipo_evaluacion")
    tipo_ev = _mapear_tipo_evaluacion(tipo_raw, periodo)

    p_cal = _safe_decimal(_get_col(fila, "P_CAL", "p_cal"))
    p_ser = _safe_decimal(_get_col(fila, "P_SER", "p_ser"))
    p_emb = _safe_decimal(_get_col(fila, "P_EMB", "p_emb"))

    # puntaje_total: preferir P_CAL + P_SER + P_EMB; fallback a Calif_Total
    if p_cal is not None and p_ser is not None and p_emb is not None:
        puntaje_total = p_cal + p_ser + p_emb
    else:
        puntaje_total = _safe_decimal(_get_col(fila, "Calif_Total", "CALIF_TOTAL"))

    resultado = _mapear_calificacion(_get_col(fila, "CALIFICACION", "Calificacion"))
    if resultado is None and puntaje_total is not None:
        # Recalcular según regla ISO si el campo de texto no es legible
        if puntaje_total >= Decimal("70"):
            resultado = "APROBADO"
        elif puntaje_total >= Decimal("55"):
            resultado = "APROB_CONDICIONAL"
        else:
            resultado = "NO_APTO"

    # Criterios individuales
    criterios: list[dict] = []
    for col_access, cod, nombre in CRITERIOS_CALIDAD:
        v = _safe_decimal(_get_col(fila, col_access))
        if v is not None:
            criterios.append({"categoria": "CALIDAD", "criterio_codigo": cod,
                               "criterio_nombre": nombre, "puntaje": float(v)})
    for col_access, cod, nombre in CRITERIOS_SERVICIO:
        v = _safe_decimal(_get_col(fila, col_access))
        if v is not None:
            criterios.append({"categoria": "SERVICIO", "criterio_codigo": cod,
                               "criterio_nombre": nombre, "puntaje": float(v)})
    for col_access, cod, nombre in CRITERIOS_EMBALAJE:
        v = _safe_decimal(_get_col(fila, col_access))
        if v is not None:
            criterios.append({"categoria": "EMBALAJE", "criterio_codigo": cod,
                               "criterio_nombre": nombre, "puntaje": float(v)})

    return {
        "proveedor_id":     proveedor_id,
        "anno":             anno,
        "periodo":          periodo,
        "tipo_evaluacion":  tipo_ev,
        "puntaje_calidad":  float(p_cal) if p_cal is not None else None,
        "puntaje_servicio": float(p_ser) if p_ser is not None else None,
        "puntaje_embalaje": float(p_emb) if p_emb is not None else None,
        "puntaje_total":    float(puntaje_total) if puntaje_total is not None else None,
        "resultado":        resultado,
        "evaluador_nombre": _safe_str(_get_col(fila, "EVALUADOR", "Evaluador")),
        "sector_evaluador": _safe_str(_get_col(fila, "SECTOR AFECTADO", "SECTOR_AFECTADO",
                                                "Sector", "SECTOR")),
        "fecha_evaluacion":    fecha,
        "proxima_evaluacion":  _safe_date(_get_col(fila, "Prox_Eva", "PROX_EVA",
                                                    "proxima_evaluacion")),
        "observaciones":    _safe_str(_get_col(fila, "COMENTARIOS", "Comentarios")),
        "referencias":      _safe_str(_get_col(fila, "REFERENCIAS", "Referencias")),
        "usuario_id":       None,
        "criterios":        criterios,
    }


# ---------------------------------------------------------------------------
# Función principal de importación
# ---------------------------------------------------------------------------

def importar_historial_desde_access(
    db: Session,
    ruta: str = RUTA_ACCDB,
    tabla: str = TABLA_ACCESS,
) -> dict:
    """
    Lee la tabla `avaprov` del Access y la importa a `evaluacion_proveedor_anual`.

    Retorna un dict con estadísticas:
      filas_leidas, importadas, duplicadas, sin_proveedor, errores, duracion_segundos
    """
    from datetime import datetime as dt
    inicio = dt.now()

    stats = {
        "filas_leidas":   0,
        "importadas":     0,
        "duplicadas":     0,
        "sin_proveedor":  0,
        "errores":        0,
        "errores_detalle": [],
        "duracion_segundos": 0.0,
    }

    # 1) Leer Access
    try:
        filas = leer_tabla_access(ruta, tabla)
    except RuntimeError as exc:
        stats["errores"] = 1
        stats["errores_detalle"].append(str(exc))
        return stats

    stats["filas_leidas"] = len(filas)
    logger.info("avaprov: %d filas leídas desde Access", len(filas))

    # 2) Construir mapa de códigos de proveedor
    codigo_map = _build_codigo_map(db)

    # 3) Procesar cada fila
    for fila in filas:
        datos = _mapear_fila(fila, codigo_map)
        if datos is None:
            stats["sin_proveedor"] += 1
            continue

        ok, msg = _insertar_evaluacion(db, datos)
        if ok:
            stats["importadas"] += 1
        elif msg == "duplicado":
            stats["duplicadas"] += 1
        else:
            stats["errores"] += 1
            if len(stats["errores_detalle"]) < 20:
                stats["errores_detalle"].append(msg)

    # 4) Commit si hubo inserciones
    if stats["importadas"] > 0:
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Error en commit final: %s", exc)
            stats["errores"] += 1
            stats["errores_detalle"].append(f"Commit fallido: {exc}")

    stats["duracion_segundos"] = round((dt.now() - inicio).total_seconds(), 2)
    logger.info(
        "Importación avaprov finalizada: importadas=%d duplicadas=%d sin_proveedor=%d errores=%d",
        stats["importadas"], stats["duplicadas"], stats["sin_proveedor"], stats["errores"],
    )
    return stats
