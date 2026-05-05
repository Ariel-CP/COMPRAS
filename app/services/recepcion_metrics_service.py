"""
Servicio de cálculo de métricas: KPIs versionados por proveedor y mes

Fase 4: Calcula puntajes de calidad, cumplimiento y respuesta a NC.
Permite recalcular histórico sin reimportar datos crudos.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

from app.db import get_db

logger = logging.getLogger(__name__)


def obtener_parametro_sistema(clave: str, valor_default=None, db=None):
    """Obtiene parámetro de configuración del sistema."""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT valor FROM parametro_sistema WHERE clave = %s AND activo = 1",
            (clave,)
        )
        resultado = cursor.fetchone()
        return float(resultado[0]) if resultado else valor_default
    except Exception as e:
        logger.warning(f"Error obteniendo parámetro {clave}: {e}")
        return valor_default


def calcular_metricas_recepcion(
    proveedor_id: int,
    anno: int,
    mes: int,
    db=None
) -> Dict:
    """
    Calcula todas las métricas para un proveedor en un período específico.
    
    Retorna diccionario con métricas crudas y scores.
    """
    
    cursor = db.cursor()
    fecha_inicio = f"{anno}-{mes:02d}-01"
    
    # Calcular último día del mes
    if mes == 12:
        fecha_fin = f"{anno + 1}-01-01"
    else:
        fecha_fin = f"{anno}-{mes + 1:02d}-01"
    
    # 1. Contar recepciones y líneas
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT rc.id) as cantidad_recepciones,
            COUNT(DISTINCT rl.id) as cantidad_lineas_totales,
            SUM(CASE WHEN rl.estado_inspeccion = 'APROBADO' THEN 1 ELSE 0 END) 
                as cantidad_lineas_aceptadas,
            SUM(CASE WHEN rl.estado_inspeccion = 'RECHAZADO' THEN 1 ELSE 0 END) 
                as cantidad_lineas_rechazadas
        FROM recepcion_cabecera rc
        LEFT JOIN recepcion_linea rl ON rc.id = rl.recepcion_cabecera_id
        WHERE rc.proveedor_id = %s
            AND DATE(rc.fecha_recepcion) >= %s
            AND DATE(rc.fecha_recepcion) < DATE_ADD(%s, INTERVAL 1 DAY)
    """, (proveedor_id, fecha_inicio, fecha_fin))
    
    row = cursor.fetchone()
    cantidad_recepciones = row[0] or 0
    cantidad_lineas_totales = row[1] or 0
    cantidad_aceptadas = row[2] or 0
    cantidad_rechazadas = row[3] or 0
    
    # Calcular % aceptación
    if cantidad_lineas_totales > 0:
        porcentaje_aceptacion = Decimal(cantidad_aceptadas) / Decimal(cantidad_lineas_totales) * 100
    else:
        porcentaje_aceptacion = 0
    
    # 2. Métricas de no conformidades
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN estado_nc = 'ABIERTA' THEN 1 END) as nc_abiertas,
            COUNT(CASE WHEN estado_nc = 'CERRADA' THEN 1 END) as nc_cerradas,
            AVG(DATEDIFF(fecha_cierre, fecha_creacion)) as promedio_dias_cierre
        FROM recepcion_no_conformidad rnc
        JOIN recepcion_linea rl ON rnc.recepcion_linea_id = rl.id
        JOIN recepcion_cabecera rc ON rl.recepcion_cabecera_id = rc.id
        WHERE rc.proveedor_id = %s
            AND DATE(rc.fecha_recepcion) >= %s
            AND DATE(rc.fecha_recepcion) < DATE_ADD(%s, INTERVAL 1 DAY)
    """, (proveedor_id, fecha_inicio, fecha_fin))
    
    row = cursor.fetchone()
    cantidad_nc_abiertas = row[0] or 0
    cantidad_nc_cerradas = row[1] or 0
    promedio_dias_cierre_nc = Decimal(row[2]) if row[2] else 0
    
    # 3. Cumplimiento de entrega (comparar con fecha esperada)
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN fecha_recepcion <= fecha_entrega_esperada THEN 1 END) 
                as a_tiempo,
            COUNT(*) as total
        FROM recepcion_cabecera
        WHERE proveedor_id = %s
            AND fecha_entrega_esperada IS NOT NULL
            AND DATE(fecha_recepcion) >= %s
            AND DATE(fecha_recepcion) < DATE_ADD(%s, INTERVAL 1 DAY)
    """, (proveedor_id, fecha_inicio, fecha_fin))
    
    row = cursor.fetchone()
    recepciones_a_tiempo = row[0] or 0
    total_con_fecha_esperada = row[1] or 0
    
    if total_con_fecha_esperada > 0:
        porcentaje_cumplimiento = Decimal(recepciones_a_tiempo) / Decimal(total_con_fecha_esperada) * 100
    else:
        porcentaje_cumplimiento = 0
    
    # 4. Compilar resultados
    metricas = {
        'cantidad_recepciones': cantidad_recepciones,
        'cantidad_lineas_totales': cantidad_lineas_totales,
        'cantidad_lineas_aceptadas': cantidad_aceptadas,
        'cantidad_lineas_rechazadas': cantidad_rechazadas,
        'porcentaje_aceptacion': float(porcentaje_aceptacion),
        'cantidad_nc_abiertas': cantidad_nc_abiertas,
        'cantidad_nc_cerradas': cantidad_nc_cerradas,
        'promedio_dias_cierre_nc': float(promedio_dias_cierre_nc),
        'cantidad_recepciones_a_tiempo': recepciones_a_tiempo,
        'porcentaje_cumplimiento_entrega': float(porcentaje_cumplimiento),
    }
    
    return metricas


def calcular_scores(metricas: Dict, db=None) -> Dict:
    """
    Calcula scores (0-10) a partir de métricas crudas.
    
    Utiliza parámetros configurables del sistema para recalcular sin código.
    """
    
    # Leer pesos de configuración
    peso_calidad = obtener_parametro_sistema(
        'EVALUACION_PROVEEDOR_PESO_CALIDAD', 0.40, db
    )
    peso_cumplimiento = obtener_parametro_sistema(
        'EVALUACION_PROVEEDOR_PESO_CUMPLIMIENTO', 0.35, db
    )
    peso_respuesta_nc = obtener_parametro_sistema(
        'EVALUACION_PROVEEDOR_PESO_RESPUESTA_NC', 0.25, db
    )
    umbral_riesgo = obtener_parametro_sistema(
        'EVALUACION_PROVEEDOR_UMBRAL_RIESGO', 6.5, db
    )
    
    # Score de calidad: porcentaje de aceptación (0-100 → 0-10)
    puntaje_calidad = metricas['porcentaje_aceptacion'] / 10
    
    # Score de cumplimiento: porcentaje entrega a tiempo (0-100 → 0-10)
    puntaje_cumplimiento = metricas['porcentaje_cumplimiento_entrega'] / 10
    
    # Score de respuesta a NC: inversamente proporcional a tiempo de cierre
    # Si cierre < 5 días: 10, si cierre > 30 días: 0, escalado
    promedio_dias = metricas['promedio_dias_cierre_nc']
    if promedio_dias == 0:
        puntaje_respuesta_nc = 10  # Sin NC o todas cerradas instantáneamente
    elif promedio_dias <= 5:
        puntaje_respuesta_nc = 10
    elif promedio_dias >= 30:
        puntaje_respuesta_nc = 0
    else:
        # Escala lineal entre 5 y 30 días
        puntaje_respuesta_nc = 10 - ((promedio_dias - 5) / (30 - 5)) * 10
    
    # Puntaje general: promedio ponderado
    puntaje_general = (
        puntaje_calidad * peso_calidad +
        puntaje_cumplimiento * peso_cumplimiento +
        puntaje_respuesta_nc * peso_respuesta_nc
    )
    
    # Detectar riesgo
    en_riesgo = 1 if puntaje_general < umbral_riesgo else 0
    razon_riesgo = None
    
    if en_riesgo:
        razones = []
        if puntaje_calidad < 6:
            razones.append("Baja calidad")
        if puntaje_cumplimiento < 6:
            razones.append("Baja entrega a tiempo")
        if puntaje_respuesta_nc < 6:
            razones.append("Lenta respuesta a NC")
        razon_riesgo = "; ".join(razones)
    
    scores = {
        'puntaje_calidad': round(float(puntaje_calidad), 2),
        'puntaje_cumplimiento': round(float(puntaje_cumplimiento), 2),
        'puntaje_respuesta_nc': round(float(puntaje_respuesta_nc), 2),
        'puntaje_general': round(float(puntaje_general), 2),
        'en_riesgo': en_riesgo,
        'razon_riesgo': razon_riesgo,
        'version_formula': 'v1',
    }
    
    return scores


def guardar_metrica_calculada(
    proveedor_id: int,
    anno: int,
    mes: int,
    metricas: Dict,
    scores: Dict,
    usuario_id: Optional[int] = None,
    db=None
) -> bool:
    """Inserta o actualiza registro de métrica en BD."""
    
    try:
        cursor = db.cursor()
        
        # Verificar si ya existe
        cursor.execute(
            """SELECT id FROM evaluacion_proveedor_metrica 
               WHERE proveedor_id = %s AND anno = %s AND mes = %s""",
            (proveedor_id, anno, mes)
        )
        existe = cursor.fetchone()
        
        if existe:
            # Actualizar
            cursor.execute("""
                UPDATE evaluacion_proveedor_metrica SET
                    cantidad_recepciones = %s,
                    cantidad_lineas_totales = %s,
                    cantidad_lineas_aceptadas = %s,
                    cantidad_lineas_rechazadas = %s,
                    porcentaje_aceptacion = %s,
                    cantidad_nc_abiertas = %s,
                    cantidad_nc_cerradas = %s,
                    promedio_dias_cierre_nc = %s,
                    cantidad_recepciones_a_tiempo = %s,
                    porcentaje_cumplimiento_entrega = %s,
                    puntaje_calidad = %s,
                    puntaje_cumplimiento = %s,
                    puntaje_respuesta_nc = %s,
                    puntaje_general = %s,
                    en_riesgo = %s,
                    razon_riesgo = %s,
                    version_formula = %s,
                    usuario_calculo_id = %s,
                    fecha_calculo = NOW()
                WHERE proveedor_id = %s AND anno = %s AND mes = %s
            """, (
                metricas['cantidad_recepciones'],
                metricas['cantidad_lineas_totales'],
                metricas['cantidad_lineas_aceptadas'],
                metricas['cantidad_lineas_rechazadas'],
                metricas['porcentaje_aceptacion'],
                metricas['cantidad_nc_abiertas'],
                metricas['cantidad_nc_cerradas'],
                metricas['promedio_dias_cierre_nc'],
                metricas['cantidad_recepciones_a_tiempo'],
                metricas['porcentaje_cumplimiento_entrega'],
                scores['puntaje_calidad'],
                scores['puntaje_cumplimiento'],
                scores['puntaje_respuesta_nc'],
                scores['puntaje_general'],
                scores['en_riesgo'],
                scores['razon_riesgo'],
                scores['version_formula'],
                usuario_id,
                proveedor_id, anno, mes
            ))
        else:
            # Insertar
            cursor.execute("""
                INSERT INTO evaluacion_proveedor_metrica (
                    proveedor_id, anno, mes,
                    cantidad_recepciones,
                    cantidad_lineas_totales,
                    cantidad_lineas_aceptadas,
                    cantidad_lineas_rechazadas,
                    porcentaje_aceptacion,
                    cantidad_nc_abiertas,
                    cantidad_nc_cerradas,
                    promedio_dias_cierre_nc,
                    cantidad_recepciones_a_tiempo,
                    porcentaje_cumplimiento_entrega,
                    puntaje_calidad,
                    puntaje_cumplimiento,
                    puntaje_respuesta_nc,
                    puntaje_general,
                    en_riesgo,
                    razon_riesgo,
                    version_formula,
                    usuario_calculo_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                proveedor_id, anno, mes,
                metricas['cantidad_recepciones'],
                metricas['cantidad_lineas_totales'],
                metricas['cantidad_lineas_aceptadas'],
                metricas['cantidad_lineas_rechazadas'],
                metricas['porcentaje_aceptacion'],
                metricas['cantidad_nc_abiertas'],
                metricas['cantidad_nc_cerradas'],
                metricas['promedio_dias_cierre_nc'],
                metricas['cantidad_recepciones_a_tiempo'],
                metricas['porcentaje_cumplimiento_entrega'],
                scores['puntaje_calidad'],
                scores['puntaje_cumplimiento'],
                scores['puntaje_respuesta_nc'],
                scores['puntaje_general'],
                scores['en_riesgo'],
                scores['razon_riesgo'],
                scores['version_formula'],
                usuario_id
            ))
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error guardando métrica: {e}")
        return False


def calcular_metricas_todos_proveedores(
    anno: int,
    mes: int,
    usuario_id: Optional[int] = None
) -> Dict:
    """
    Calcula métricas para TODOS los proveedores en un período.
    
    Permitir recalcular histórico entero sin reimportar.
    """
    
    resultado = {
        'exitoso': False,
        'total_proveedores': 0,
        'calculadas': 0,
        'errores': 0,
        'timestamp': datetime.now().isoformat(),
    }
    
    try:
        db = next(get_db())
        cursor = db.cursor()
        
        # Obtener proveedores con al menos una recepción
        cursor.execute("""
            SELECT DISTINCT proveedor_id FROM recepcion_cabecera
            WHERE YEAR(fecha_recepcion) = %s AND MONTH(fecha_recepcion) = %s
        """, (anno, mes))
        
        proveedores = cursor.fetchall()
        resultado['total_proveedores'] = len(proveedores)
        
        logger.info(f"Calculando métricas para {len(proveedores)} proveedores ({anno}-{mes:02d})")
        
        for proveedor_id, in proveedores:
            try:
                # 1. Calcular métricas crudas
                metricas = calcular_metricas_recepcion(proveedor_id, anno, mes, db)
                
                # 2. Calcular scores
                scores = calcular_scores(metricas, db)
                
                # 3. Guardar en BD
                guardado = guardar_metrica_calculada(
                    proveedor_id, anno, mes, metricas, scores, usuario_id, db
                )
                
                if guardado:
                    resultado['calculadas'] += 1
                    logger.debug(f"Proveedor {proveedor_id}: score {scores['puntaje_general']}")
                else:
                    resultado['errores'] += 1
                    
            except Exception as e:
                logger.error(f"Error calculando métricas para proveedor {proveedor_id}: {e}")
                resultado['errores'] += 1
        
        resultado['exitoso'] = True
        logger.info(f"Cálculo completado: {resultado['calculadas']} exitosas, {resultado['errores']} errores")
        
    except Exception as e:
        logger.error(f"Error fatal en cálculo de métricas: {e}")
    
    return resultado
