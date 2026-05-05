"""
Servicio de importación desde Access: CONTROL DE RECEPCION → recepcion_staging

Fase 2: Contrato de ingesta con idempotencia, hash de fila y trazabilidad.
"""

import hashlib
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db import get_db

logger = logging.getLogger(__name__)


def _generar_hash_fila(datos_fila: Dict) -> str:
    """Genera SHA256 de fila para idempotencia."""
    # Serializa en orden determinista
    contenido = json.dumps(datos_fila, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(contenido.encode()).hexdigest()


def _convertir_tipo_dato(valor, tipo_esperado: str):
    """Convierte valores desde Access a tipos Python."""
    if valor is None:
        return None

    if tipo_esperado == "DATE":
        if isinstance(valor, date):
            return valor
        if isinstance(valor, str):
            try:
                return datetime.strptime(valor, "%Y-%m-%d").date()
            except Exception:
                return None
        return None

    elif tipo_esperado == "DECIMAL":
        try:
            return Decimal(str(valor))
        except Exception:
            return None

    elif tipo_esperado == "INT":
        try:
            return int(valor)
        except Exception:
            return None

    return str(valor) if valor else None


def leer_tabla_access(
    ruta_accdb: str, tabla_nombre: str = "CONTROL DE RECEPCION"
) -> List[Dict]:
    """
    Lee tabla desde archivo Access (.accdb).

    Args:
        ruta_accdb: Ruta completa al archivo .accdb (ej: R:\\COMPARTIR-Calidad-ID\\...)
        tabla_nombre: Nombre de tabla en Access (default: CONTROL DE RECEPCION)

    Returns:
        Lista de diccionarios con filas

    Raises:
        FileNotFoundError: Si el archivo no existe
        Exception: Si falla la conexión o lectura
    """

    # Validar archivo
    path = Path(ruta_accdb)
    if not path.exists():
        raise FileNotFoundError(f"Archivo Access no encontrado: {ruta_accdb}")

    logger.info(f"Leyendo {tabla_nombre} desde {ruta_accdb}")

    try:
        import pyodbc  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "No se puede importar desde Access: falta la dependencia 'pyodbc'"
        ) from exc

    # Conexión a Access (OLEDB para .accdb en Windows)
    connection_string = (
        f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};"
        f"DBQ={ruta_accdb};"
        f"Exclusive=0;"
    )

    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Leer tabla
        cursor.execute(f"SELECT * FROM [{tabla_nombre}]")

        # Obtener nombres de columna
        columnas = [desc[0] for desc in cursor.description]

        # Convertir a lista de diccionarios
        filas = []
        for fila in cursor.fetchall():
            fila_dict = dict(zip(columnas, fila))
            filas.append(fila_dict)

        cursor.close()
        conn.close()

        logger.info(f"Lectura exitosa: {len(filas)} filas de {tabla_nombre}")
        return filas

    except Exception as e:
        logger.error(f"Error leyendo Access: {e}")
        raise


def mapear_campos_access_a_staging(fila_access: Dict) -> Dict:
    """
    Mapea campos de Access CONTROL DE RECEPCION a campos de recepcion_staging.

    Ajusta los nombres de campos según la estructura real de Access.
    """

    mapeo = {
        "id_recepcion_original": fila_access.get("ID")
        or fila_access.get("IDRecepcion"),
        "proveedor_codigo": fila_access.get("Proveedor_Codigo")
        or fila_access.get("Código Proveedor"),
        "proveedor_nombre": fila_access.get("Proveedor_Nombre")
        or fila_access.get("Proveedor"),
        "producto_codigo": fila_access.get("Producto_Codigo")
        or fila_access.get("Código Producto"),
        "producto_nombre": fila_access.get("Producto_Nombre")
        or fila_access.get("Producto"),
        "cantidad_solicitada": _convertir_tipo_dato(
            fila_access.get("Cantidad_Solicitada")
            or fila_access.get("Cant. Solicitada"),
            "DECIMAL",
        ),
        "cantidad_recibida": _convertir_tipo_dato(
            fila_access.get("Cantidad_Recibida") or fila_access.get("Cant. Recibida"),
            "DECIMAL",
        ),
        "lote_numero": fila_access.get("Lote") or fila_access.get("Lote_Número"),
        "fecha_vencimiento": _convertir_tipo_dato(
            fila_access.get("Fecha_Vencimiento") or fila_access.get("Vencimiento"),
            "DATE",
        ),
        "fecha_recepcion_original": _convertir_tipo_dato(
            fila_access.get("Fecha_Recepcion") or fila_access.get("Fecha de Recepción"),
            "DATE",
        ),
        "estado_inspeccion_original": fila_access.get("Estado_Inspeccion")
        or fila_access.get("Estado"),
        "calidad_ok": (
            1
            if str(fila_access.get("Calidad_OK", "")).upper()
            in ["SI", "TRUE", "1", "OK"]
            else 0
        ),
        "codigo_no_conformidad": fila_access.get("Codigo_NC") or fila_access.get("NC"),
        "descripcion_no_conformidad": fila_access.get("Descripcion_NC")
        or fila_access.get("Descripción NC"),
        "notas_adicionales": fila_access.get("Notas"),
        "inspector_nombre": fila_access.get("Inspector"),
    }

    return mapeo


def importar_recepcion_desde_access(
    ruta_accdb: str,
    usuario_id: Optional[int] = None,
    tabla_nombre: str = "CONTROL DE RECEPCION",
) -> Dict:
    """
    Importa tabla Access completa a recepcion_staging.

    - Lee Access
    - Mapea campos
    - Genera hash de fila
    - Inserta en staging (idempotente)
    - Retorna resumen de resultados

    Args:
        ruta_accdb: Ruta del archivo .accdb
        usuario_id: ID del usuario realizando la importación
        tabla_nombre: Nombre de tabla en Access

    Returns:
        {
            'exitoso': bool,
            'total_filas': int,
            'nuevas_insertadas': int,
            'duplicadas': int,
            'errores': int,
            'errores_detalle': [{'fila': int, 'error': str}],
            'timestamp': str
        }
    """

    resultado: Dict[str, Any] = {
        "exitoso": False,
        "total_filas": 0,
        "nuevas_insertadas": 0,
        "duplicadas": 0,
        "errores": 0,
        "errores_detalle": [],
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # 1. Leer desde Access
        filas_access = leer_tabla_access(ruta_accdb, tabla_nombre)
        resultado["total_filas"] = len(filas_access)
        logger.info(f"Total de filas a procesar: {len(filas_access)}")

        # 2. Procesar e insertar
        db = next(get_db())
        cursor = db.cursor()  # type: ignore[attr-defined]

        for idx, fila_access in enumerate(filas_access, 1):
            try:
                # Mapear campos
                fila_mapeada = mapear_campos_access_a_staging(fila_access)

                # Generar hash
                fila_hash = _generar_hash_fila(fila_access)

                # Validar clave única (fila_hash) - si existe, es duplicada
                cursor.execute(
                    "SELECT id FROM recepcion_staging WHERE fila_hash = %s",
                    (fila_hash,),
                )
                existe = cursor.fetchone()

                if existe:
                    resultado["duplicadas"] += 1
                    logger.debug(f"Fila {idx}: Duplicada (hash existente)")
                    continue

                # Insertar nueva fila
                cursor.execute(
                    """
                    INSERT INTO recepcion_staging (
                        fila_hash,
                        usuario_importacion_id,
                        id_recepcion_original,
                        proveedor_codigo,
                        proveedor_nombre,
                        producto_codigo,
                        producto_nombre,
                        cantidad_solicitada,
                        cantidad_recibida,
                        lote_numero,
                        fecha_vencimiento,
                        fecha_recepcion_original,
                        estado_inspeccion_original,
                        calidad_ok,
                        codigo_no_conformidad,
                        descripcion_no_conformidad,
                        notas_adicionales,
                        inspector_nombre,
                        estado_procesamiento
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """,
                    (
                        fila_hash,
                        usuario_id,
                        fila_mapeada["id_recepcion_original"],
                        fila_mapeada["proveedor_codigo"],
                        fila_mapeada["proveedor_nombre"],
                        fila_mapeada["producto_codigo"],
                        fila_mapeada["producto_nombre"],
                        fila_mapeada["cantidad_solicitada"],
                        fila_mapeada["cantidad_recibida"],
                        fila_mapeada["lote_numero"],
                        fila_mapeada["fecha_vencimiento"],
                        fila_mapeada["fecha_recepcion_original"],
                        fila_mapeada["estado_inspeccion_original"],
                        fila_mapeada["calidad_ok"],
                        fila_mapeada["codigo_no_conformidad"],
                        fila_mapeada["descripcion_no_conformidad"],
                        fila_mapeada["notas_adicionales"],
                        fila_mapeada["inspector_nombre"],
                        "PENDIENTE",
                    ),
                )

                resultado["nuevas_insertadas"] += 1

            except Exception as e:
                resultado["errores"] += 1
                resultado["errores_detalle"].append({"fila": idx, "error": str(e)})
                logger.error(f"Fila {idx}: Error de inserción: {e}")

        # Commit
        db.commit()
        cursor.close()

        resultado["exitoso"] = True
        logger.info(
            f"Importación completada: "
            f"{resultado['nuevas_insertadas']} nuevas, "
            f"{resultado['duplicadas']} duplicadas, "
            f"{resultado['errores']} errores"
        )

    except Exception as e:
        logger.error(f"Error fatal en importación: {e}")
        resultado["errores_detalle"].append({"fila": "GLOBAL", "error": str(e)})

    return resultado
