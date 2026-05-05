"""
API endpoints para evaluación formal de proveedores (ISO 9001 — PG-4.06.02).
"""
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_db
from app.api.deps_auth import get_current_user
from app.schemas.evaluacion import EvaluacionCreate, EvaluacionOut, EvaluacionListItem
from app.services.evaluacion_service import (
    crear_evaluacion,
    obtener_evaluacion,
    listar_evaluaciones,
    eliminar_evaluacion,
    historial_proveedor,
)
from app.services.evaluacion_access_import_service import importar_historial_desde_access
from app.services.evaluacion_csv_recepcion_service import importar_desde_csv

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/evaluaciones",
    tags=["evaluaciones"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/", response_model=EvaluacionOut, status_code=201)
def api_crear_evaluacion(
    payload: EvaluacionCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Registra una evaluación formal ISO de un proveedor.

    El puntaje_total se calcula automáticamente como la suma de los tres
    puntajes parciales. El resultado (APROBADO / APROB_CONDICIONAL / NO_APTO)
    se asigna según PG-4.06.02: ≥70 / ≥55 / <55.
    """
    datos = payload.model_dump()
    datos["usuario_id"] = current_user.id
    try:
        return crear_evaluacion(db, datos)
    except Exception as exc:
        logger.error("Error creando evaluación: %s", exc)
        msg = str(exc)
        if "Duplicate entry" in msg or "uq_eval_anual" in msg:
            raise HTTPException(
                status_code=409,
                detail="Ya existe una evaluación para ese proveedor/año/período.",
            ) from exc
        raise HTTPException(status_code=500, detail=msg) from exc


@router.get("/", response_model=list[EvaluacionListItem])
def api_listar_evaluaciones(
    proveedor_id: Optional[int] = Query(default=None),
    anno: Optional[int] = Query(default=None, ge=2000, le=2099),
    resultado: Optional[str] = Query(
        default=None,
        pattern=r"^(APROBADO|APROB_CONDICIONAL|NO_APTO)$",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
):
    """Lista evaluaciones con filtros opcionales."""
    return listar_evaluaciones(db, proveedor_id, anno, resultado, limit, offset)


@router.get("/proveedor/{proveedor_id}/historial")
def api_historial_proveedor(proveedor_id: int, db=Depends(get_db)):
    """Historial completo de evaluaciones de un proveedor."""
    return historial_proveedor(db, proveedor_id)


@router.get("/exportar")
def api_exportar_evaluaciones(
    proveedor_id: Optional[int] = Query(default=None),
    anno: Optional[int] = Query(default=None, ge=2000, le=2099),
    resultado: Optional[str] = Query(
        default=None,
        pattern=r"^(APROBADO|APROB_CONDICIONAL|NO_APTO)$",
    ),
    db=Depends(get_db),
):
    """Exporta evaluaciones a CSV con los mismos filtros que el listado."""
    PERIODO_LABELS = {
        0: "Anual", 1: "1er Cuatrimestre",
        2: "2do Cuatrimestre", 3: "3er Cuatrimestre",
    }
    datos = listar_evaluaciones(db, proveedor_id, anno, resultado, limit=10000, offset=0)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Código Proveedor", "Proveedor", "Año", "Período", "Tipo",
        "Puntaje Calidad", "Puntaje Servicio", "Puntaje Embalaje", "Puntaje Total",
        "Resultado", "Evaluador", "Sector", "Fecha Evaluación",
        "Próxima Evaluación", "Observaciones", "Fecha Registro",
    ])
    for e in datos:
        writer.writerow([
            e.get("proveedor_codigo", ""),
            e.get("proveedor_nombre", ""),
            e.get("anno", ""),
            PERIODO_LABELS.get(e.get("periodo", 0), ""),
            e.get("tipo_evaluacion", ""),
            e.get("puntaje_calidad", ""),
            e.get("puntaje_servicio", ""),
            e.get("puntaje_embalaje", ""),
            e.get("puntaje_total", ""),
            e.get("resultado", ""),
            e.get("evaluador_nombre", ""),
            e.get("sector_evaluador", ""),
            e.get("fecha_evaluacion", ""),
            e.get("proxima_evaluacion", ""),
            e.get("observaciones", ""),
            e.get("fecha_creacion", ""),
        ])

    filename = f"evaluaciones{'_' + str(anno) if anno else ''}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{evaluacion_id}", response_model=EvaluacionOut)
def api_obtener_evaluacion(evaluacion_id: int, db=Depends(get_db)):
    """Obtiene una evaluación con sus criterios de detalle."""
    ev = obtener_evaluacion(db, evaluacion_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    return ev


@router.delete("/{evaluacion_id}", status_code=204)
def api_eliminar_evaluacion(
    evaluacion_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Elimina una evaluación (y sus criterios, por CASCADE)."""
    ok = eliminar_evaluacion(db, evaluacion_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")


@router.post("/importar-historial")
def api_importar_historial(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Importa el historial completo de evaluaciones desde el Access (tabla avaprov).

    Idempotente: registros ya existentes (proveedor+año+período) son saltados.
    """
    try:
        resultado = importar_historial_desde_access(db)
    except Exception as exc:
        logger.error("Error importando historial avaprov: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return resultado


@router.post("/importar-csv")
async def api_importar_csv(
    archivo: UploadFile = File(..., description="CSV exportado de Power BI (sep=; decimal=,)"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Importa evaluaciones anuales por proveedor desde el CSV exportado de Power BI
    (tabla CONTROL DE RECEPCION).

    El CSV debe tener columnas: Codigo Proveedor, Año, PuntajeCalidadPonderado,
    PuntajeEntregaPonderado, PuntajeCertificadoPonderado, PuntajeTotalProveedor,
    ClasificacionProveedor, Controlo.

    Idempotente: si ya existe evaluación para proveedor+año, la salta.
    """
    nombre = archivo.filename or ""
    if not nombre.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .csv")
    try:
        contenido = await archivo.read()
        resultado = importar_desde_csv(db, contenido, usuario_id=current_user.id)
    except Exception as exc:
        logger.error("Error importando CSV: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return resultado
