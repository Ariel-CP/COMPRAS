"""
Servicio de normalización: recepcion_staging → Tablas canónicas

Fase 3: Transforma staging (crudo) a tablas normalizadas con validaciones,
manteniendo integridad referencial y registrando errores sin perder datos crudos.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from app.db import get_db

logger = logging.getLogger(__name__)


def obtener_proveedor_por_codigo(codigo_proveedor: str, db=None) -> Optional[int]:
    """Busca ID de proveedor por código."""
    if not codigo_proveedor:
        return None
    
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id FROM proveedor WHERE codigo = %s LIMIT 1",
            (codigo_proveedor.strip(),)
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Exception as e:
        logger.error(f"Error buscando proveedor {codigo_proveedor}: {e}")
        return None


def obtener_producto_por_codigo(codigo_producto: str, db=None) -> Optional[int]:
    """Busca ID de producto por código."""
    if not codigo_producto:
        return None
    
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id FROM producto WHERE codigo = %s LIMIT 1",
            (codigo_producto.strip(),)
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Exception as e:
        logger.error(f"Error buscando producto {codigo_producto}: {e}")
        return None


def obtener_unidad_medida_default(db=None) -> Optional[int]:
    """Obtiene ID de unidad de medida por defecto (ej: 'UN')."""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id FROM unidad_medida WHERE codigo IN ('UN', 'UNIDAD', 'U') LIMIT 1"
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Exception as e:
        logger.error(f"Error obteniendo unidad default: {e}")
        return None


def validar_fila_staging(fila_staging: Dict) -> Tuple[bool, List[str]]:
    """
    Valida fila de staging para normalización.
    
    Retorna: (es_válida, lista_de_errores)
    """
    errores = []
    
    # Validaciones obligatorias
    if not fila_staging.get('proveedor_codigo'):
        errores.append("proveedor_codigo: requerido")
    
    if not fila_staging.get('producto_codigo'):
        errores.append("producto_codigo: requerido")
    
    if not fila_staging.get('fecha_recepcion_original'):
        errores.append("fecha_recepcion_original: requerido")
    
    if fila_staging.get('cantidad_recibida') is None:
        errores.append("cantidad_recibida: requerido")
    elif fila_staging.get('cantidad_recibida') < 0:
        errores.append("cantidad_recibida: no puede ser negativa")
    
    # Validación de datos tipo
    if fila_staging.get('calidad_ok') not in (0, 1):
        errores.append("calidad_ok: debe ser 0 o 1")
    
    return (len(errores) == 0, errores)


def normalizar_fila_staging(
    staging_id: int,
    fila_staging: Dict,
    db=None
) -> Tuple[bool, Optional[Dict], str]:
    """
    Normaliza una fila de staging a tablas canónicas.
    
    Retorna: (éxito, datos_procesados, mensaje)
    """
    
    try:
        # 1. Validar
        es_valida, errores_validacion = validar_fila_staging(fila_staging)
        
        if not es_valida:
            error_msg = "; ".join(errores_validacion)
            logger.warning(f"Fila staging {staging_id}: Validación fallida: {error_msg}")
            
            # Registrar errores en staging
            cursor = db.cursor()
            cursor.execute(
                "UPDATE recepcion_staging SET errores_validacion = %s, estado_procesamiento = 'RECHAZADO' WHERE id = %s",
                (error_msg, staging_id)
            )
            db.commit()
            
            return (False, None, f"Validación fallida: {error_msg}")
        
        # 2. Resolver referencias a maestros
        proveedor_id = obtener_proveedor_por_codigo(fila_staging['proveedor_codigo'], db)
        if not proveedor_id:
            msg = f"Proveedor {fila_staging['proveedor_codigo']} no encontrado"
            logger.warning(f"Fila staging {staging_id}: {msg}")
            return (False, None, msg)
        
        producto_id = obtener_producto_por_codigo(fila_staging['producto_codigo'], db)
        if not producto_id:
            msg = f"Producto {fila_staging['producto_codigo']} no encontrado"
            logger.warning(f"Fila staging {staging_id}: {msg}")
            return (False, None, msg)
        
        unidad_medida_id = obtener_unidad_medida_default(db)
        
        # 3. Crear o actualizar recepcion_cabecera
        # Clave: proveedor + fecha + numero_recepcion (si existe en original)
        numero_recepcion = (
            fila_staging.get('id_recepcion_original') or 
            f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        
        cursor = db.cursor()
        
        # Buscar cabecera existente
        cursor.execute(
            """SELECT id FROM recepcion_cabecera 
               WHERE proveedor_id = %s AND fecha_recepcion = %s 
               LIMIT 1""",
            (proveedor_id, fila_staging['fecha_recepcion_original'])
        )
        cabecera_existente = cursor.fetchone()
        
        if cabecera_existente:
            recepcion_cabecera_id = cabecera_existente[0]
            logger.debug(f"Usando cabecera existente: {recepcion_cabecera_id}")
        else:
            # Crear nueva cabecera
            cursor.execute(
                """INSERT INTO recepcion_cabecera (
                    numero_recepcion, proveedor_id, fecha_recepcion, estado
                ) VALUES (%s, %s, %s, 'PENDIENTE')""",
                (numero_recepcion, proveedor_id, fila_staging['fecha_recepcion_original'])
            )
            db.commit()
            recepcion_cabecera_id = cursor.lastrowid
            logger.debug(f"Cabecera creada: {recepcion_cabecera_id}")
        
        # 4. Crear recepcion_linea
        cursor.execute(
            """SELECT MAX(numero_linea) FROM recepcion_linea 
               WHERE recepcion_cabecera_id = %s""",
            (recepcion_cabecera_id,)
        )
        max_linea = cursor.fetchone()[0] or 0
        numero_linea = max_linea + 1
        
        # Determinar estado de inspección
        estado_inspeccion = 'PENDIENTE'
        if fila_staging.get('calidad_ok'):
            estado_inspeccion = 'APROBADO'
        elif not fila_staging.get('calidad_ok') and fila_staging.get('calidad_ok') is not None:
            estado_inspeccion = 'RECHAZADO'
        
        cursor.execute(
            """INSERT INTO recepcion_linea (
                recepcion_cabecera_id, numero_linea, producto_id, 
                cantidad_solicitada, cantidad_recibida, unidad_medida_id,
                lote_numero, fecha_vencimiento, estado_inspeccion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                recepcion_cabecera_id,
                numero_linea,
                producto_id,
                fila_staging.get('cantidad_solicitada'),
                fila_staging.get('cantidad_recibida'),
                unidad_medida_id,
                fila_staging.get('lote_numero'),
                fila_staging.get('fecha_vencimiento'),
                estado_inspeccion
            )
        )
        db.commit()
        recepcion_linea_id = cursor.lastrowid
        logger.debug(f"Línea creada: {recepcion_linea_id}")
        
        # 5. Si hay no conformidad, crear registro
        if fila_staging.get('codigo_no_conformidad'):
            cursor.execute(
                """INSERT INTO recepcion_no_conformidad (
                    recepcion_linea_id, codigo_nc, descripcion, estado_nc
                ) VALUES (%s, %s, %s, 'ABIERTA')""",
                (
                    recepcion_linea_id,
                    fila_staging['codigo_no_conformidad'],
                    fila_staging.get('descripcion_no_conformidad', 'NC importada de Access')
                )
            )
            db.commit()
            logger.debug(f"NC creada: {fila_staging['codigo_no_conformidad']}")
        
        # 6. Marcar fila staging como procesada
        cursor.execute(
            """UPDATE recepcion_staging 
               SET estado_procesamiento = 'PROCESADO', 
                   fecha_procesamiento = NOW(),
                   errores_validacion = NULL
               WHERE id = %s""",
            (staging_id,)
        )
        db.commit()
        
        resultado = {
            'recepcion_cabecera_id': recepcion_cabecera_id,
            'recepcion_linea_id': recepcion_linea_id,
            'numero_linea': numero_linea,
            'proveedor_id': proveedor_id,
            'producto_id': producto_id,
        }
        
        return (True, resultado, "Fila normalizada exitosamente")
        
    except Exception as e:
        logger.error(f"Error normalizando fila {staging_id}: {e}")
        return (False, None, f"Error de normalización: {str(e)}")


def normalizar_todo_staging() -> Dict:
    """
    Procesa todas las filas de staging con estado PENDIENTE
    y las transforma a tablas canónicas.
    
    Retorna resumen de procesamiento.
    """
    
    resultado = {
        'exitoso': False,
        'total_procesadas': 0,
        'exitosas': 0,
        'rechazadas': 0,
        'timestamp': datetime.now().isoformat(),
    }
    
    try:
        db = next(get_db())
        cursor = db.cursor()
        
        # Obtener filas PENDIENTE
        cursor.execute(
            "SELECT id, * FROM recepcion_staging WHERE estado_procesamiento = 'PENDIENTE'"
        )
        filas_staging = cursor.fetchall()
        
        # Convertir a diccionarios
        columnas = [desc[0] for desc in cursor.description]
        
        total = len(filas_staging)
        logger.info(f"Iniciando normalización de {total} filas staging")
        
        for idx, fila_tuple in enumerate(filas_staging, 1):
            fila_dict = dict(zip(columnas, fila_tuple))
            staging_id = fila_dict['id']
            
            exito, datos, msg = normalizar_fila_staging(staging_id, fila_dict, db)
            
            resultado['total_procesadas'] += 1
            
            if exito:
                resultado['exitosas'] += 1
                logger.info(f"[{idx}/{total}] Fila {staging_id}: OK")
            else:
                resultado['rechazadas'] += 1
                logger.warning(f"[{idx}/{total}] Fila {staging_id}: RECHAZADA - {msg}")
        
        resultado['exitoso'] = True
        logger.info(
            f"Normalización completada: "
            f"{resultado['exitosas']} exitosas, "
            f"{resultado['rechazadas']} rechazadas"
        )
        
    except Exception as e:
        logger.error(f"Error fatal en normalización: {e}")
    
    return resultado
