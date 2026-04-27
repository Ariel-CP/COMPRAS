"""
Servicio de importación de proveedores desde CSV (formato ERP Flexxus)
"""

import csv
import io
import logging
import re
from typing import Optional, Callable, Any
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Mapeo de alias de columnas → campos esperados
COLUMN_ALIASES = {
    "código": "codigo",
    "code": "codigo",
    "proveedor_codigo": "codigo",
    "razón social": "nombre",
    "razon social": "nombre",
    "nombre": "nombre",
    "name": "nombre",
    "proveedor_nombre": "nombre",
    "c.u.i.t.": "cuit",
    "cuit": "cuit",
    "dirección": "direccion",
    "direccion": "direccion",
    "address": "direccion",
    "localidad": "localidad",
    "ciudad": "localidad",
    "city": "localidad",
    "provincia": "provincia",
    "estado": "provincia",
    "state": "provincia",
    "e-mail": "email",
    "email": "email",
    "mail": "email",
    "teléfono": "telefono",
    "telefono": "telefono",
    "phone": "telefono",
    "activo": "activo",
    "active": "activo",
    "estado": "activo",
    "enabled": "activo",
}


def _normalize_column_name(name: str) -> str:
    """Normaliza nombre de columna para mapeo"""
    return name.strip().lower()


def _detect_delimiter(sample: str) -> str:
    """Detecta delimitador de CSV usando csv.Sniffer, con fallback a ';'"""
    try:
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample, delimiters=",;\t|").delimiter
        if delimiter and isinstance(delimiter, str) and len(delimiter) == 1:
            logger.info(f"Delimitador detectado: {repr(delimiter)}")
            return delimiter
    except (csv.Error, Exception) as e:
        logger.warning(f"No se pudo detectar delimitador ({e}), usando ';'")
    return ";"


def _map_columns(header_row: list[str]) -> dict[int, str]:
    """
    Mapea índices de columnas CSV a nombres canónicos.
    
    Returns: {índice_original: nombre_canónico}
    """
    mapping = {}
    for idx, col_name in enumerate(header_row):
        normalized = _normalize_column_name(col_name)
        canonical = COLUMN_ALIASES.get(normalized, normalized)
        if canonical in ["codigo", "nombre", "cuit", "direccion", "localidad", "provincia", "email", "telefono", "activo"]:
            mapping[idx] = canonical
            logger.debug(f"Columna '{col_name}' → '{canonical}'")
    return mapping


def _validate_email(email: Optional[str]) -> tuple[str, Optional[str]]:
    """Valida y limpia email. Muy permisivo - solo limpia espacios."""
    if not email:
        return None, None
    
    email = email.strip()
    if not email or len(email) < 3:
        return None, None
    
    # Aceptar email incluso si no tiene @ (se almacena como es)
    return email, None


def _validate_telefono(telefono: Optional[str]) -> tuple[str, Optional[str]]:
    """
    Normaliza teléfono. Muy permisivo - solo limpia espacios.
    
    Returns: (telefono_limpio, error_msg)
    """
    if not telefono:
        return None, None
    
    telefono = telefono.strip()
    if not telefono:
        return None, None
    
    # Aceptar cualquier cosa, solo remover espacios extra
    return telefono, None


def _validate_cuit(cuit: Optional[str]) -> tuple[str, Optional[str]]:
    """
    Normaliza CUIT. Muy permisivo - acepta múltiples formatos.
    Intenta formatear como XX-XXXXXXXX-X si es posible, sino acepta como está.
    
    Returns: (cuit_normalizado, error_msg)
    """
    if not cuit:
        return None, None
    
    cuit = cuit.strip()
    if not cuit:
        return None, None
    
    # Intentar normalizar si tiene exactamente 11 dígitos
    cuit_clean = cuit.replace(" ", "").replace("-", "")
    
    if cuit_clean.isdigit() and len(cuit_clean) == 11:
        # Formatear como XX-XXXXXXXX-X
        cuit_formatted = f"{cuit_clean[:2]}-{cuit_clean[2:10]}-{cuit_clean[10]}"
        return cuit_formatted, None
    
    # Aceptar como está si no cumple el formato exacto (muy permisivo)
    return cuit, None


def _clean_string(value: Optional[str]) -> Optional[str]:
    """Limpia y normaliza string"""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_activo(value: Optional[str]) -> tuple[int, Optional[str]]:
    """
    Convierte valor de campo "Activo" del CSV a 0 o 1.
    
    Acepta: '1', 'si', 'sí', 'true', 'yes', 'activo', 'enabled'
             '0', 'no', 'false', 'no', 'inactivo', 'disabled'
    
    Returns: (valor_0_o_1, error_msg)
    """
    if not value:
        return 1, None  # Por defecto activo
    
    value_clean = str(value).strip().lower()
    
    if value_clean in {'1', 'si', 'sí', 'true', 'yes', 'activo', 'enabled', 'a'}:
        return 1, None
    elif value_clean in {'0', 'no', 'false', 'inactivo', 'disabled', 'i', 'n'}:
        return 0, None
    else:
        return None, f"Valor 'Activo' inválido: {value} (use 1/Si/True o 0/No/False)"


def _existe_codigo(db: Session, codigo: str, exclude_id: Optional[int] = None) -> bool:
    """Verifica si un código de proveedor ya existe"""
    sql = "SELECT id FROM proveedor WHERE codigo = :codigo"
    params: dict[str, Any] = {"codigo": codigo}
    if exclude_id:
        sql += " AND id <> :exclude_id"
        params["exclude_id"] = exclude_id
    return db.execute(text(sql), params).first() is not None


def _crear_o_actualizar_proveedor(
    db: Session,
    codigo: str,
    data: dict[str, Any],
) -> tuple[str, Optional[str]]:
    """
    Crea o actualiza un proveedor.
    
    Returns: (acción: 'insertado'|'actualizado', error_msg)
    """
    # Verificar si existe
    result = db.execute(
        text("SELECT id FROM proveedor WHERE codigo = :codigo"),
        {"codigo": codigo},
    ).first()
    
    if result:
        proveedor_id = result[0]
        # Actualizar
        sets = []
        params: dict[str, Any] = {"id": proveedor_id}
        for key, value in data.items():
            sets.append(f"{key} = :{key}")
            params[key] = value
        
        if sets:
            params["fecha_actualizacion"] = "NOW()"
            sql = f"UPDATE proveedor SET {', '.join(sets)}, fecha_actualizacion = NOW() WHERE id = :id"
            db.execute(text(sql), params)
        
        return "actualizado", None
    else:
        # Insertar
        data["codigo"] = codigo
        # Si no viene "activo" en los datos, por defecto 1
        if "activo" not in data:
            data["activo"] = 1
        
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = f"INSERT INTO proveedor ({columns}) VALUES ({placeholders})"
        
        db.execute(text(sql), data)
        
        return "insertado", None


def importar_proveedores_desde_csv(
    db: Session,
    contenido_csv: bytes,
    encoding: str = "utf-8",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> dict[str, Any]:
    """
    Importa proveedores desde archivo CSV.
    
    Args:
        db: Sesión SQLAlchemy
        contenido_csv: Contenido del archivo CSV en bytes
        encoding: Encoding del archivo (intentará utf-8 → latin-1 si falla)
        progress_callback: Función para reportar progreso (fila_actual, total_filas)
    
    Returns:
        {
            "status": "success" | "error",
            "insertados": int,
            "actualizados": int,
            "rechazados": int,
            "errores": [
                {"fila": int, "codigo": str, "mensaje": str},
                ...
            ]
        }
    """
    insertados = 0
    actualizados = 0
    rechazados = 0
    errores = []
    
    try:
        # Intentar decodificar
        try:
            texto = contenido_csv.decode(encoding)
        except UnicodeDecodeError:
            logger.warning(f"Encoding {encoding} falló, intentando latin-1")
            texto = contenido_csv.decode("latin-1")
        
        # Detectar delimitador
        sample = texto[:4096]
        delimiter = _detect_delimiter(sample)
        
        # Parsear CSV
        reader = csv.reader(io.StringIO(texto), delimiter=delimiter)
        
        # Leer encabezado
        header = None
        try:
            header = next(reader)
        except StopIteration:
            return {
                "status": "error",
                "insertados": 0,
                "actualizados": 0,
                "rechazados": 0,
                "errores": [{"fila": 0, "codigo": "-", "mensaje": "CSV vacío"}],
            }
        
        # Mapear columnas
        col_mapping = _map_columns(header)
        if not col_mapping:
            return {
                "status": "error",
                "insertados": 0,
                "actualizados": 0,
                "rechazados": 0,
                "errores": [
                    {
                        "fila": 1,
                        "codigo": "-",
                        "mensaje": "No se encontraron columnas válidas en el CSV",
                    }
                ],
            }
        
        # Procesar filas
        total_rows = sum(1 for _ in io.StringIO(texto).readlines()) - 1  # -1 por header
        
        for fila_num, row in enumerate(reader, start=2):
            try:
                # Reportar progreso
                if progress_callback:
                    progress_callback(fila_num - 1, total_rows)
                
                # Mapear valores
                datos_fila = {}
                for idx, valor in enumerate(row):
                    if idx in col_mapping:
                        canonical_name = col_mapping[idx]
                        datos_fila[canonical_name] = valor
                
                # Validaciones obligatorias
                codigo = _clean_string(datos_fila.get("codigo"))
                nombre = _clean_string(datos_fila.get("nombre"))
                
                if not codigo:
                    errores.append(
                        {"fila": fila_num, "codigo": "-", "mensaje": "Código vacío o inválido"}
                    )
                    rechazados += 1
                    continue
                
                if not nombre:
                    errores.append(
                        {
                            "fila": fila_num,
                            "codigo": codigo,
                            "mensaje": "Nombre/Razón social vacío o inválido",
                        }
                    )
                    rechazados += 1
                    continue
                
                # Validar email (NO rechaza, simplemente no incluye si inválido)
                email = _clean_string(datos_fila.get("email"))
                if email:
                    email_clean, _ = _validate_email(email)
                    if email_clean:
                        datos_fila["email"] = email_clean
                    else:
                        datos_fila.pop("email", None)  # Remover si inválido
                
                # Validar teléfono (NO rechaza, simplemente normaliza)
                telefono = _clean_string(datos_fila.get("telefono"))
                if telefono:
                    telefono_clean, _ = _validate_telefono(telefono)
                    if telefono_clean:
                        datos_fila["telefono"] = telefono_clean
                    else:
                        datos_fila.pop("telefono", None)  # Remover si inválido
                
                # Validar CUIT (NO rechaza, simplemente normaliza)
                cuit = _clean_string(datos_fila.get("cuit"))
                if cuit:
                    cuit_normalized, _ = _validate_cuit(cuit)
                    if cuit_normalized:
                        datos_fila["cuit"] = cuit_normalized
                    else:
                        datos_fila.pop("cuit", None)  # Remover si inválido
                
                # Procesar campo "activo" si está presente (NO rechaza)
                if "activo" in datos_fila:
                    activo_val, _ = _parse_activo(datos_fila.get("activo"))
                    if activo_val is not None:
                        datos_fila["activo"] = activo_val
                    else:
                        datos_fila.pop("activo", None)  # Remover si no puede parsed
                
                # Limpiar otros campos (sin rechazar si son inválidos)
                if "email" in datos_fila:
                    email_clean = _clean_string(datos_fila.get("email"))
                    if email_clean:
                        datos_fila["email"] = email_clean
                    else:
                        datos_fila.pop("email", None)
                
                if "direccion" in datos_fila:
                    direccion_clean = _clean_string(datos_fila.get("direccion"))
                    if direccion_clean:
                        datos_fila["direccion"] = direccion_clean
                    else:
                        datos_fila.pop("direccion", None)
                
                if "localidad" in datos_fila:
                    localidad_clean = _clean_string(datos_fila.get("localidad"))
                    if localidad_clean:
                        datos_fila["localidad"] = localidad_clean
                    else:
                        datos_fila.pop("localidad", None)
                
                if "provincia" in datos_fila:
                    provincia_clean = _clean_string(datos_fila.get("provincia"))
                    if provincia_clean:
                        datos_fila["provincia"] = provincia_clean
                    else:
                        datos_fila.pop("provincia", None)
                
                # Asegurar que nombre y código estén presentes
                datos_fila["nombre"] = nombre
                
                # Eliminar campo codigo del diccionario para update
                datos_insert = {k: v for k, v in datos_fila.items() if k != "codigo"}
                
                # Crear o actualizar
                accion, err = _crear_o_actualizar_proveedor(db, codigo, datos_insert)
                
                if err:
                    errores.append(
                        {"fila": fila_num, "codigo": codigo, "mensaje": err}
                    )
                    rechazados += 1
                elif accion == "insertado":
                    insertados += 1
                elif accion == "actualizado":
                    actualizados += 1
                
            except Exception as ex:
                logger.error(f"Error procesando fila {fila_num}: {ex}")
                errores.append(
                    {
                        "fila": fila_num,
                        "codigo": datos_fila.get("codigo", "-"),
                        "mensaje": f"Error: {str(ex)[:100]}",
                    }
                )
                rechazados += 1
                continue
        
        # Commit de toda la transacción
        try:
            db.commit()
            logger.info(f"Importación completada: {insertados} insertados, {actualizados} actualizados, {rechazados} rechazados")
        except Exception as ex:
            db.rollback()
            logger.error(f"Error en commit: {ex}")
            return {
                "status": "error",
                "insertados": 0,
                "actualizados": 0,
                "rechazados": total_rows,
                "errores": [
                    {
                        "fila": -1,
                        "codigo": "-",
                        "mensaje": f"Error en transacción: {str(ex)[:200]}",
                    }
                ],
            }
        
        return {
            "status": "success",
            "insertados": insertados,
            "actualizados": actualizados,
            "rechazados": rechazados,
            "errores": errores,
        }
        
    except Exception as ex:
        logger.error(f"Error general en importación: {ex}", exc_info=True)
        return {
            "status": "error",
            "insertados": 0,
            "actualizados": 0,
            "rechazados": 0,
            "errores": [
                {
                    "fila": 0,
                    "codigo": "-",
                    "mensaje": f"Error general: {str(ex)[:200]}",
                }
            ],
        }
