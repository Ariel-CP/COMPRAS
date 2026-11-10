"""
Servicio de importación desde Access: CONTROL DE RECEPCION → recepcion_staging

Fase 2: Contrato de ingesta con idempotencia, hash de fila y trazabilidad.
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db import get_db

logger = logging.getLogger(__name__)


def _generar_hash_fila(datos_fila: Dict) -> str:
    """Genera SHA256 de fila para idempotencia."""
    # Serializa en orden determinista
    contenido = json.dumps(datos_fila, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


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


def _normalizar_nombre_producto(valor: Any, notas: Any = None) -> str | None:
    """Normaliza el nombre del producto sin mezclar la dimensión técnica de la nota."""
    nombre = str(valor).strip() if valor is not None else ""
    if not nombre:
        return None

    # Si el nombre trae una dimensión técnica al final, la removemos para mantener
    # el nombre del artículo estable y mantener la nota como detalle técnico.
    nombre_limpio = re.sub(
        r"(?i)\s*(?:\d+(?:[.,]\d+)?\s*[xX]\s*\d+(?:[.,]\d+)?(?:\s*[xX]\s*\d+(?:[.,]\d+)?)?\s*(?:mm|cm|mts|m|mm\s*)?)$",
        "",
        nombre,
    ).strip(" -/")
    if nombre_limpio:
        nombre = nombre_limpio

    if notas and isinstance(notas, str):
        notas_formateado = notas.strip()
        if notas_formateado and "x" in notas_formateado.lower():
            return nombre

    return nombre or None


def _derivar_codigo_producto(fila_access: Dict) -> str | None:
    """Deriva un código canónico para el artículo usando el PLANO cuando no existe código real."""
    codigo = (
        fila_access.get("Codigo Producto")
        or fila_access.get("Código Producto")
        or fila_access.get("Producto_Codigo")
        or fila_access.get("PRODUCTO_CODIGO")
    )
    if codigo is not None and str(codigo).strip():
        codigo_str = str(codigo).strip()
        if codigo_str.upper().startswith("10NIP"):
            return codigo_str
        return codigo_str

    plano = (
        fila_access.get("PLANO")
        or fila_access.get("Plano")
        or fila_access.get("Numero Plano")
    )
    if plano is None:
        return None

    plano_str = str(plano).strip()
    if not plano_str:
        return None

    if plano_str.upper().startswith("10NIP"):
        return plano_str

    return f"10NIP{plano_str}"


def mapear_campos_access_a_staging(fila_access: Dict) -> Dict:
    """
    Mapea campos reales de la tabla Access CONTROL DE RECEPCION a recepcion_staging.

    El esquema real del archivo recibido usa nombres con mayúsculas, espacios y
    variantes como 'Codigo Proveedor', 'CANTIDAD OC', 'Fecha Control', 'Material',
    'PLANO' y 'NOTA'.
    """

    def _valor(*claves):
        for clave in claves:
            if clave in fila_access and fila_access[clave] is not None:
                return fila_access[clave]
        return None

    proveedor_codigo = _valor(
        "Codigo Proveedor",
        "Código Proveedor",
        "Proveedor_Codigo",
        "PROVEEDOR_CODIGO",
    )
    proveedor_nombre = _valor(
        "PROVEEDOR",
        "Proveedor",
        "Proveedor_Nombre",
        "Nombre Proveedor",
    )
    producto_nombre_raw = _valor(
        "Material",
        "Producto",
        "Producto_Nombre",
        "Materiales",
    )
    notas = _valor("NOTA", "Notas", "Nota")
    producto_nombre = _normalizar_nombre_producto(producto_nombre_raw, notas)
    cantidad_solicitada = _valor(
        "CANTIDAD OC",
        "Cantidad_Solicitada",
        "Cant. Solicitada",
        "Cantidad Solicitada",
    )
    fecha_recepcion = _valor(
        "Fecha Control",
        "Fecha_Recepcion",
        "Fecha de Recepción",
        "FECHA EMISION OC",
    )
    estado = _valor("Estado", "Estado_Inspeccion", "ESTADO")
    lote = _valor("Lote", "Lote_Número", "LOTENUMERO")
    inspector = _valor("Controlo", "Inspector", "Recibio")

    mapeo = {
        "id_recepcion_original": _valor("ID_INT", "ID", "IDRecepcion", "N_interno"),
        "proveedor_codigo": proveedor_codigo,
        "proveedor_nombre": proveedor_nombre,
        "producto_codigo": _derivar_codigo_producto(fila_access),
        "producto_nombre": producto_nombre,
        "cantidad_solicitada": _convertir_tipo_dato(cantidad_solicitada, "DECIMAL"),
        "cantidad_recibida": _convertir_tipo_dato(
            _valor("Cantidad Recibida", "Cantidad_Recibida", "Cant. Recibida"),
            "DECIMAL",
        ),
        "lote_numero": lote,
        "fecha_vencimiento": _convertir_tipo_dato(
            _valor("Fecha de Entrega", "Fecha_Vencimiento", "Vencimiento"),
            "DATE",
        ),
        "fecha_recepcion_original": _convertir_tipo_dato(fecha_recepcion, "DATE"),
        "estado_inspeccion_original": estado,
        "calidad_ok": (
            1
            if str(
                _valor("TieneCertificado", "Calidad_OK", "Calidad ok", "Calidad_OK")
            ).upper()
            in ["SI", "TRUE", "1", "OK", "Y", "YES", "T", "CERTIFICADO"]
            else 0
        ),
        "codigo_no_conformidad": _valor("Codigo_NC", "NC", "Codigo NC"),
        "descripcion_no_conformidad": _valor(
            "Descripcion_NC",
            "Descripción NC",
            "Descripcion NC",
        ),
        "notas_adicionales": notas,
        "inspector_nombre": inspector,
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

        # 2. Procesar e insertar con la sesión SQLAlchemy real del proyecto
        db = next(get_db())

        for idx, fila_access in enumerate(filas_access, 1):
            try:
                # Mapear campos
                fila_mapeada = mapear_campos_access_a_staging(fila_access)

                # Generar hash
                fila_hash = _generar_hash_fila(fila_access)

                # Validar clave única (fila_hash) - si existe, es duplicada
                existe = db.execute(
                    text(
                        """
                        SELECT id FROM recepcion_staging
                        WHERE fila_hash = :fila_hash
                           OR (:id_original IS NOT NULL
                               AND id_recepcion_original = :id_original)
                        LIMIT 1
                        """
                    ),
                    {
                        "fila_hash": fila_hash,
                        "id_original": fila_mapeada["id_recepcion_original"],
                    },
                ).fetchone()

                if existe:
                    db.execute(
                        text("""
                            UPDATE recepcion_staging
                            SET id_recepcion_original = COALESCE(
                                    id_recepcion_original, :id_recepcion_original
                                ),
                                proveedor_codigo = COALESCE(
                                    proveedor_codigo, :proveedor_codigo
                                ),
                                fecha_recepcion_original = COALESCE(
                                    fecha_recepcion_original, :fecha_recepcion_original
                                ),
                                estado_inspeccion_original = COALESCE(
                                    estado_inspeccion_original,
                                    :estado_inspeccion_original
                                ),
                                lote_numero = COALESCE(lote_numero, :lote_numero)
                            WHERE fila_hash = :fila_hash
                               OR (:id_recepcion_original IS NOT NULL
                                   AND id_recepcion_original = :id_recepcion_original)
                            """),
                        {
                            "id_recepcion_original": fila_mapeada[
                                "id_recepcion_original"
                            ],
                            "proveedor_codigo": fila_mapeada["proveedor_codigo"],
                            "fecha_recepcion_original": fila_mapeada[
                                "fecha_recepcion_original"
                            ],
                            "estado_inspeccion_original": fila_mapeada[
                                "estado_inspeccion_original"
                            ],
                            "lote_numero": fila_mapeada["lote_numero"],
                            "fila_hash": fila_hash,
                        },
                    )
                    resultado["duplicadas"] += 1
                    logger.debug(
                        "Fila %d: duplicada; se completaron campos históricos faltantes",
                        idx,
                    )
                    continue

                # Insertar nueva fila
                db.execute(
                    text("""
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
                            :fila_hash, :usuario_id, :id_recepcion_original, :proveedor_codigo,
                            :proveedor_nombre, :producto_codigo, :producto_nombre,
                            :cantidad_solicitada, :cantidad_recibida, :lote_numero,
                            :fecha_vencimiento, :fecha_recepcion_original,
                            :estado_inspeccion_original, :calidad_ok,
                            :codigo_no_conformidad, :descripcion_no_conformidad,
                            :notas_adicionales, :inspector_nombre, :estado_procesamiento
                        )
                        """),
                    {
                        "fila_hash": fila_hash,
                        "usuario_id": usuario_id,
                        "id_recepcion_original": fila_mapeada["id_recepcion_original"],
                        "proveedor_codigo": fila_mapeada["proveedor_codigo"],
                        "proveedor_nombre": fila_mapeada["proveedor_nombre"],
                        "producto_codigo": fila_mapeada["producto_codigo"],
                        "producto_nombre": fila_mapeada["producto_nombre"],
                        "cantidad_solicitada": fila_mapeada["cantidad_solicitada"],
                        "cantidad_recibida": fila_mapeada["cantidad_recibida"],
                        "lote_numero": fila_mapeada["lote_numero"],
                        "fecha_vencimiento": fila_mapeada["fecha_vencimiento"],
                        "fecha_recepcion_original": fila_mapeada[
                            "fecha_recepcion_original"
                        ],
                        "estado_inspeccion_original": fila_mapeada[
                            "estado_inspeccion_original"
                        ],
                        "calidad_ok": fila_mapeada["calidad_ok"],
                        "codigo_no_conformidad": fila_mapeada["codigo_no_conformidad"],
                        "descripcion_no_conformidad": fila_mapeada[
                            "descripcion_no_conformidad"
                        ],
                        "notas_adicionales": fila_mapeada["notas_adicionales"],
                        "inspector_nombre": fila_mapeada["inspector_nombre"],
                        "estado_procesamiento": "PENDIENTE",
                    },
                )

                resultado["nuevas_insertadas"] += 1

            except Exception as e:
                resultado["errores"] += 1
                resultado["errores_detalle"].append({"fila": idx, "error": str(e)})
                logger.error(f"Fila {idx}: Error de inserción: {e}")

        # Commit
        db.commit()

        resultado["exitoso"] = True
        logger.info(
            f"Importación completada: "
            f"{resultado['nuevas_insertadas']} nuevas, "
            f"{resultado['duplicadas']} duplicadas, "
            f"{resultado['errores']} errores"
        )

    except Exception as e:
        logger.error(f"Error fatal en importación: {e}")
        resultado["errores_detalle"].append({"fila": -1, "error": str(e)})

    return resultado
