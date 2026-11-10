"""
API endpoints para recepción de materiales y evaluación de proveedores.

Fase 5: Explotación de datos - lecturas analíticas separadas de operaciones.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import bindparam, text

from app.api.deps_auth import get_current_user, require_permission
from app.db import get_db
from app.schemas.recepcion import (
    EvaluacionCalculoResult,
    EvaluacionProveedorMetricaOut,
    EvaluacionProveedorRanking,
    RecepcionCalidadCreate,
    RecepcionImportResult,
    RecepcionIntentoInspeccionCreate,
    RecepcionNormalizacionResult,
    RecepcionOperativaCreate,
    RecepcionOperativaOut,
)
from app.services.access_read_service import (
    AccessReadError,
    inspect_access_schema,
    inspect_access_table,
    listar_controles_access,
    obtener_control_access,
)
from app.services.plano_service import obtener_plano_pdf
from app.services.producto_service import listar_productos
from app.services.proveedor_service import listar_proveedores
from app.services.recepcion_access_import_service import importar_recepcion_desde_access
from app.services.recepcion_metrics_service import calcular_metricas_todos_proveedores
from app.services.recepcion_muestreo_service import calcular_plan_muestreo
from app.services.recepcion_normalization_service import normalizar_todo_staging
from app.services.recepcion_operativa_service import (
    actualizar_recepcion_operativa,
    crear_recepcion_operativa,
    eliminar_recepcion_operativa,
    listar_recepciones_operativas,
    listar_lineas_pendientes_calidad,
    obtener_recepcion_operativa,
    registrar_control_calidad,
    registrar_intento_inspeccion,
)
from app.services.recepcion_recomendacion_service import recomendar_nivel_inspeccion
from app.services.recepcion_scheduler import get_scheduler_status
from app.services.recepcion_sync_service import sincronizar_ciclo_completo

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recepcion",
    tags=["recepcion"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/proveedores/buscar")
def buscar_proveedores_recepcion(
    q: str = Query(min_length=2, max_length=100),
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Busca proveedores activos por código o nombre para el formulario."""
    proveedores = listar_proveedores(db, q=q, activo=True, limit=10, offset=0)
    return [
        {
            "id": proveedor["id"],
            "codigo": proveedor["codigo"],
            "nombre": proveedor["nombre"],
        }
        for proveedor in proveedores
    ]


@router.get("/proveedores/{proveedor_id}/recomendacion-control")
def obtener_recomendacion_control_proveedor(
    proveedor_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Clasifica desempeño reciente con el criterio interno legado de Access."""
    try:
        return recomendar_nivel_inspeccion(db, proveedor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/plan-muestreo")
def obtener_plan_muestreo(
    nivel: str = Query(min_length=1, max_length=30),
    lote: str = Query(min_length=1, max_length=30),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Calcula la letra de código y muestra por nivel y tamaño del lote."""
    try:
        return calcular_plan_muestreo(nivel, lote)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AccessReadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/articulos/buscar")
def buscar_articulos_recepcion(
    q: str = Query(min_length=2, max_length=100),
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Busca artículos activos por código o nombre para el formulario."""
    articulos = listar_productos(db, q=q, activo=True, limit=10, offset=0)
    unidad_ids = [
        articulo.get("unidad_medida_id")
        for articulo in articulos
        if articulo.get("unidad_medida_id") is not None
    ]
    unidades = {}
    if unidad_ids:
        unidades = {
            row.id: row.codigo
            for row in db.execute(
                text("SELECT id, codigo FROM unidad_medida WHERE id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": unidad_ids},
            )
        }
    return [
        {
            "id": articulo["id"],
            "codigo": articulo["codigo"],
            "nombre": articulo["nombre"],
            **(
                {"unidad_medida": unidades[articulo["unidad_medida_id"]]}
                if articulo.get("unidad_medida_id") in unidades
                else {}
            ),
        }
        for articulo in articulos
    ]


@router.get("/planos/{numero_plano}/pdf")
def abrir_plano_pdf(
    numero_plano: str,
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Entrega inline el PDF asociado a un número de plano de cuatro dígitos."""
    try:
        path = obtener_plano_pdf(numero_plano)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.get("/planos/{numero_plano}/ultima-version")
def obtener_ultima_version_plano(
    numero_plano: str,
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Devuelve el nombre de la revisión más alta disponible del plano."""
    try:
        path = obtener_plano_pdf(numero_plano)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"numero_plano": path.stem, "archivo": path.name}


@router.get("/operativas")
def listar_recepciones(
    q: str | None = Query(default=None, max_length=100),
    proveedor_codigo: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=500),
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Lista recepciones operativas guardadas en COMPRAS."""

    return listar_recepciones_operativas(
        db, q=q, proveedor_codigo=proveedor_codigo, limit=limit
    )


@router.get("/operativas/lineas-pendientes")
def listar_lineas_pendientes_control_calidad(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=300, ge=1, le=500),
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Lista materiales operativos que esperan control o reinspección."""
    return listar_lineas_pendientes_calidad(db, q=q, limit=limit)


@router.get("/operativas/{recepcion_id}")
def obtener_recepcion(
    recepcion_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Devuelve el detalle operativo de una recepción guardada en COMPRAS."""
    recepcion = obtener_recepcion_operativa(db, recepcion_id)
    if recepcion is None:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    return recepcion


@router.post(
    "/operativas",
    response_model=RecepcionOperativaOut,
    status_code=201,
)
def crear_recepcion(
    payload: RecepcionOperativaCreate,
    db=Depends(get_db),
    current_user=Depends(require_permission("recepcion", True)),
):
    """Registra en COMPRAS una recepción y sus mediciones, sin escribir en Access."""
    try:
        return crear_recepcion_operativa(
            db,
            payload,
            usuario_id=int(current_user["id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/operativas/{recepcion_id}")
def actualizar_recepcion(
    recepcion_id: int,
    payload: RecepcionOperativaCreate,
    db=Depends(get_db),
    current_user=Depends(require_permission("recepcion", True)),
):
    """Actualiza una recepción local manteniendo sus cotas actuales editadas."""
    try:
        return actualizar_recepcion_operativa(
            db,
            recepcion_id,
            payload,
            usuario_id=int(current_user["id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/operativas/{recepcion_id}", status_code=204)
def borrar_recepcion(
    recepcion_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_permission("recepcion", True)),
):
    """Borra una recepción local sin intentos de inspección ni NC asociadas."""
    try:
        eliminar_recepcion_operativa(db, recepcion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/operativas/{recepcion_id}/control-calidad")
def guardar_control_calidad(
    recepcion_id: int,
    payload: RecepcionCalidadCreate,
    db=Depends(get_db),
    current_user=Depends(require_permission("recepcion", True)),
):
    """Guarda la inspección posterior con el usuario autenticado como inspector."""
    try:
        return registrar_control_calidad(
            db,
            recepcion_id,
            payload,
            usuario_id=int(current_user["id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/operativas/lineas/{linea_id}/intentos-inspeccion", status_code=201)
def guardar_intento_inspeccion(
    linea_id: int,
    payload: RecepcionIntentoInspeccionCreate,
    db=Depends(get_db),
    current_user=Depends(require_permission("recepcion", True)),
):
    """Registra el resultado observado; no calcula ni valida reglas IRAM."""
    try:
        return registrar_intento_inspeccion(
            db,
            linea_id,
            payload,
            usuario_id=int(current_user["id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/access/inspect")
async def inspeccionar_access(
    sample_limit: int = Query(default=10, ge=1, le=100),
):
    """Inspecciona Access sin importar ni modificar datos."""
    try:
        return inspect_access_table(sample_limit=sample_limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccessReadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/access/schema")
async def inspeccionar_esquema_access():
    """Inspecciona tablas y columnas Access sin modificar datos."""
    try:
        return inspect_access_schema()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccessReadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/access/controles")
def listar_controles_historicos_access(
    q: str | None = Query(default=None, max_length=100),
    proveedor_codigo: str | None = Query(default=None, max_length=50),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Lista controles históricos directamente desde Access, en modo readonly."""
    try:
        return listar_controles_access(
            q=q,
            proveedor_codigo=proveedor_codigo,
            desde=desde,
            hasta=hasta,
            before_id=before_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccessReadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/access/controles/{access_id}")
def obtener_control_historico_access(
    access_id: int,
    _current_user=Depends(require_permission("recepcion", False)),
):
    """Devuelve una recepción histórica y sus cotas CRD asociadas."""
    try:
        control = obtener_control_access(access_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccessReadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if control is None:
        raise HTTPException(status_code=404, detail="Control Access no encontrado")
    return control


# ============================================================================
# FASE 2: Endpoints de Importación desde Access
# ============================================================================


@router.post("/import-access", response_model=RecepcionImportResult)
async def importar_desde_access(
    ruta_archivo: str = Query(..., description="Ruta completa al archivo .accdb"),
    usuario_id: Optional[int] = Query(None),
    tabla_nombre: str = Query(
        default="CONTROL DE RECEPCION",
        description="Nombre de tabla en Access"
    ),
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Importa tabla CONTROL DE RECEPCION desde archivo Access a staging.
    
    - Lee archivo .accdb
    - Mapea campos
    - Genera hash para idempotencia
    - Inserta en recepcion_staging
    
    Ejemplo:
    ```
    POST /recepcion/import-access?ruta_archivo=R:\\COMPARTIR-Calidad-ID\\...\\Control.accdb
    ```
    """

    usuario_id = usuario_id or int(current_user["id"])

    logger.info(f"Iniciando importación desde Access: {ruta_archivo}")

    try:
        resultado = importar_recepcion_desde_access(
            ruta_accdb=ruta_archivo,
            usuario_id=usuario_id,
            tabla_nombre=tabla_nombre
        )

        return resultado

    except FileNotFoundError as e:
        logger.error(f"Archivo no encontrado: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Archivo no encontrado: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error importando desde Access: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante importación: {str(e)}"
        )


# ============================================================================
# FASE 3: Endpoints de Normalización
# ============================================================================


@router.post("/normalizar-staging", response_model=RecepcionNormalizacionResult)
async def normalizar_staging(
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Normaliza todas las filas PENDIENTE en recepcion_staging
    hacia tablas canónicas (cabecera, línea, inspección, NC).
    
    - Valida referencias (proveedor, producto)
    - Crea/actualiza recepciones
    - Registra no conformidades
    - Marca filas como PROCESADO o RECHAZADO
    """

    logger.info(f"Usuario {current_user['id']} iniciando normalización de staging")

    try:
        resultado = normalizar_todo_staging()
        return resultado
    except Exception as e:
        logger.error(f"Error normalizando: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante normalización: {str(e)}"
        )


# ============================================================================
# FASE 4: Endpoints de Cálculo de Métricas
# ============================================================================


@router.post("/calcular-metricas", response_model=EvaluacionCalculoResult)
async def calcular_metricas(
    anno: int = Query(..., ge=2000, le=2099),
    mes: int = Query(..., ge=1, le=12),
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Calcula todas las métricas y scores para todos los proveedores
    en un período específico (año-mes).
    
    - Calcula KPIs de recepción, NC, cumplimiento
    - Calcula scores ponderados (calidad, cumplimiento, respuesta NC)
    - Detecta proveedores en riesgo
    - Permite recalcular histórico sin reimportar
    """

    logger.info(
        f"Usuario {current_user['id']} iniciando cálculo de métricas "
        f"para {anno}-{mes:02d}"
    )

    try:
        resultado = calcular_metricas_todos_proveedores(
            anno=anno, mes=mes, usuario_id=int(current_user["id"])
        )
        return resultado
    except Exception as e:
        logger.error(f"Error calculando métricas: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante cálculo: {str(e)}"
        )


# ============================================================================
# FASE 5: Endpoints de Consulta (Lectura analítica)
# ============================================================================


@router.get("/evaluar/{proveedor_id}", response_model=list[EvaluacionProveedorMetricaOut])
async def obtener_evaluaciones_proveedor(
    proveedor_id: int,
    anno: Optional[int] = None,
    mes: Optional[int] = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Obtiene histórico de evaluaciones para un proveedor.
    
    - Filtrable por año/mes
    - Retorna scores, métricas e indicadores de riesgo
    """
    
    try:
        cursor = db.cursor()
        
        query = """
            SELECT 
                id, proveedor_id, anno, mes,
                cantidad_recepciones, cantidad_lineas_totales,
                cantidad_lineas_aceptadas, cantidad_lineas_rechazadas,
                porcentaje_aceptacion,
                cantidad_nc_abiertas, cantidad_nc_cerradas,
                promedio_dias_cierre_nc,
                cantidad_recepciones_a_tiempo,
                porcentaje_cumplimiento_entrega,
                puntaje_calidad, puntaje_cumplimiento,
                puntaje_respuesta_nc, puntaje_general,
                en_riesgo, razon_riesgo, version_formula,
                fecha_calculo
            FROM evaluacion_proveedor_metrica
            WHERE proveedor_id = %s
        """
        params = [proveedor_id]
        
        if anno:
            query += " AND anno = %s"
            params.append(anno)
        
        if mes:
            query += " AND mes = %s"
            params.append(mes)
        
        query += " ORDER BY anno DESC, mes DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convertir a modelos
        resultados = []
        for row in rows:
            # Mapear campos (ajustar según estructura real)
            metrica = EvaluacionProveedorMetricaOut(
                id=row[0],
                proveedor_id=row[1],
                anno=row[2],
                mes=row[3],
                cantidad_recepciones=row[4],
                cantidad_lineas_totales=row[5],
                cantidad_lineas_aceptadas=row[6],
                cantidad_lineas_rechazadas=row[7],
                porcentaje_aceptacion=row[8],
                cantidad_nc_abiertas=row[9],
                cantidad_nc_cerradas=row[10],
                promedio_dias_cierre_nc=row[11],
                cantidad_recepciones_a_tiempo=row[12],
                porcentaje_cumplimiento_entrega=row[13],
                puntaje_calidad=row[14],
                puntaje_cumplimiento=row[15],
                puntaje_respuesta_nc=row[16],
                puntaje_general=row[17],
                en_riesgo=row[18],
                razon_riesgo=row[19],
                version_formula=row[20],
                fecha_calculo=row[21],
            )
            resultados.append(metrica)
        
        return resultados
        
    except Exception as e:
        logger.error(f"Error obteniendo evaluaciones: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en consulta: {str(e)}"
        )


@router.get("/ranking", response_model=list[EvaluacionProveedorRanking])
async def obtener_ranking_proveedores(
    anno: int = Query(..., ge=2000, le=2099),
    mes: int = Query(..., ge=1, le=12),
    en_riesgo: Optional[int] = Query(None, description="Filtrar solo en riesgo (1) o no (0)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Obtiene ranking de proveedores para un período.
    
    - Ordenado por puntaje general descendente
    - Muestra indicadores de riesgo
    - Filtrable por estado (en riesgo o no)
    """
    
    try:
        cursor = db.cursor()
        
        query = """
            SELECT 
                p.id, p.nombre,
                epm.puntaje_general,
                epm.puntaje_calidad,
                epm.puntaje_cumplimiento,
                epm.puntaje_respuesta_nc,
                epm.en_riesgo,
                epm.razon_riesgo,
                epm.anno,
                epm.mes
            FROM evaluacion_proveedor_metrica epm
            JOIN proveedor p ON epm.proveedor_id = p.id
            WHERE epm.anno = %s AND epm.mes = %s
        """
        params = [anno, mes]
        
        if en_riesgo is not None:
            query += " AND epm.en_riesgo = %s"
            params.append(en_riesgo)
        
        query += " ORDER BY epm.puntaje_general DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        resultados = []
        for row in rows:
            ranking = EvaluacionProveedorRanking(
                proveedor_id=row[0],
                proveedor_nombre=row[1],
                puntaje_general=row[2],
                puntaje_calidad=row[3],
                puntaje_cumplimiento=row[4],
                puntaje_respuesta_nc=row[5],
                en_riesgo=row[6],
                razon_riesgo=row[7],
                anno=row[8],
                mes=row[9],
            )
            resultados.append(ranking)
        
        return resultados
        
    except Exception as e:
        logger.error(f"Error obteniendo ranking: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en consulta: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check del módulo de recepción."""
    return {
        "status": "ok",
        "modulo": "recepcion",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# ADMIN: Sincronización automática
# ============================================================================


@router.post("/admin/sincronizacion/ejecutar")
async def ejecutar_sincronizacion_manual(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Ejecuta el ciclo completo de sincronización de forma manual.

    - Lee tabla CONTROL DE RECEPCION del archivo Access.
    - Inserta filas nuevas en recepcion_staging (idempotente por hash SHA-256).
    - Normaliza staging hacia tablas canónicas.
    - Registra resultado en sincronizacion_log.
    """
    logger.info("Usuario %s disparando sync manual", current_user["id"])

    resultado = sincronizar_ciclo_completo(db, usuario_id=int(current_user["id"]))

    if not resultado.get("exitoso"):
        raise HTTPException(
            status_code=500,
            detail=resultado.get("error", "Error desconocido en sincronización"),
        )
    return resultado


@router.get("/admin/sincronizacion/estado")
async def estado_sincronizacion(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Retorna el estado del scheduler automático y el último log registrado en BD.
    """
    # Estado del thread
    scheduler = get_scheduler_status()

    # Último registro en BD
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT
                id, fecha_inicio, fecha_fin, duracion_segundos,
                filas_leidas, filas_nuevas, filas_duplicadas, filas_errores,
                estado, mensaje_error
            FROM sincronizacion_log
            ORDER BY fecha_inicio DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        ultimo_log = None
        if row:
            ultimo_log = {
                "id": row[0],
                "fecha_inicio": row[1].isoformat() if row[1] else None,
                "fecha_fin": row[2].isoformat() if row[2] else None,
                "duracion_segundos": float(row[3]) if row[3] else 0,
                "filas_leidas": row[4],
                "filas_nuevas": row[5],
                "filas_duplicadas": row[6],
                "filas_errores": row[7],
                "estado": row[8],
                "mensaje_error": row[9],
            }
    except Exception as exc:
        logger.warning("No se pudo leer sincronizacion_log: %s", exc)
        ultimo_log = None

    return {
        "scheduler": scheduler,
        "ultimo_log_bd": ultimo_log,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/admin/sincronizacion/historial")
async def historial_sincronizaciones(
    limit: int = Query(20, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Últimos N registros de sincronizacion_log."""
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT
                id, fecha_inicio, fecha_fin, duracion_segundos,
                filas_leidas, filas_nuevas, filas_duplicadas, filas_errores,
                estado, mensaje_error, usuario_id
            FROM sincronizacion_log
            ORDER BY fecha_inicio DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "fecha_inicio": r[1].isoformat() if r[1] else None,
                "fecha_fin": r[2].isoformat() if r[2] else None,
                "duracion_segundos": float(r[3]) if r[3] else 0,
                "filas_leidas": r[4],
                "filas_nuevas": r[5],
                "filas_duplicadas": r[6],
                "filas_errores": r[7],
                "estado": r[8],
                "mensaje_error": r[9],
                "usuario_id": r[10],
            }
            for r in rows
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
