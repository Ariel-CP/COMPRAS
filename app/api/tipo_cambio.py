from datetime import date
from io import StringIO, BytesIO
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Body,
    UploadFile,
    File,
    Form,
    Header,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import get_settings
from ..db import get_db
from ..schemas.tipo_cambio import (
    TipoCambioCreate,
    TipoCambioUpdate,
    TipoCambioOut,
    TipoCambioFiltro,
    BulkImportResult,
    TipoCambioSyncResponse,
)
from ..services.tipo_cambio_service import (
    listar_tipos_cambio,
    upsert_tipo_cambio,
    actualizar_tipo_cambio,
    obtener_por_id,
    bulk_import_csv,
    bulk_import_xlsx,
)
from ..services.tipo_cambio_sync_service import (
    TipoCambioSyncError,
    sync_bcra_tipos_cambio,
)

router = APIRouter()
settings = get_settings()


@router.get("/", response_model=list[TipoCambioOut])
def api_listar_tipos_cambio(
    moneda: str | None = Query(
        default=None, description="Moneda"
    ),
    tipo: str | None = Query(
        default=None, description="COMPRA/VENTA/PROMEDIO"
    ),
    desde: str | None = Query(
        default=None, description="Fecha desde (YYYY-MM-DD)"
    ),
    hasta: str | None = Query(
        default=None, description="Fecha hasta (YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
):
    desde_dt = date.fromisoformat(desde) if desde else None
    hasta_dt = date.fromisoformat(hasta) if hasta else None
    filtro = TipoCambioFiltro(
        moneda=moneda, tipo=tipo, desde=desde_dt, hasta=hasta_dt
    )
    try:
        return listar_tipos_cambio(db, filtro)
    except SQLAlchemyError as ex:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.post("/", response_model=TipoCambioOut)
def api_upsert_tipo_cambio(
    data: TipoCambioCreate, db: Session = Depends(get_db)
):
    try:
        creado, id_ = upsert_tipo_cambio(db, data)
        obj = obtener_por_id(db, id_)
        if not obj:
            raise HTTPException(
                status_code=500, detail="No se pudo obtener el registro"
            )
        return obj
    except SQLAlchemyError as ex:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.put("/{id}", response_model=TipoCambioOut)
def api_actualizar_tipo_cambio(
    id: int, data: TipoCambioUpdate, db: Session = Depends(get_db)
):
    try:
        ok = actualizar_tipo_cambio(db, id, data)
        if not ok:
            raise HTTPException(
                status_code=404, detail="Registro no encontrado o sin cambios"
            )
        obj = obtener_por_id(db, id)
        if not obj:
            raise HTTPException(
                status_code=404,
                detail="Registro no encontrado tras actualizar",
            )
        return obj
    except SQLAlchemyError as ex:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.post("/import", response_model=BulkImportResult)
def api_importar_csv(
    csv_contenido: str = Body(
        ..., embed=True, description="Contenido CSV fecha,tasa"
    ),
    moneda: str = Body("USD", embed=True),
    tipo: str = Body("VENTA", embed=True),
    origen: str = Body("MANUAL", embed=True),
    db: Session = Depends(get_db),
):
    try:
        insertados, actualizados, errores = bulk_import_csv(
            db, csv_contenido, moneda=moneda, tipo=tipo, origen=origen
        )
        return BulkImportResult(
            insertados=insertados,
            actualizados=actualizados,
            errores=len(errores),
            detalle_errores=errores,
        )
    except SQLAlchemyError as ex:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.post("/import-xlsx", response_model=BulkImportResult)
async def api_importar_xlsx(
    file: UploadFile = File(...),
    moneda: str = Form("USD"),
    tipo: str = Form("VENTA"),
    origen: str = Form("MANUAL"),
    sheet_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        contenido = await file.read()
        insertados, actualizados, errores = bulk_import_xlsx(
            db,
            contenido,
            moneda=moneda,
            tipo=tipo,
            origen=origen,
            sheet_name=sheet_name,
        )
        return BulkImportResult(
            insertados=insertados,
            actualizados=actualizados,
            errores=len(errores),
            detalle_errores=errores,
        )
    except SQLAlchemyError as ex:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex


@router.get("/plantilla-csv")
def descargar_plantilla_csv():
    """Descarga plantilla CSV vacía con encabezados."""
    contenido = "fecha,tasa\n2025-01-15,1250.50\n2025-01-16,1255.00\n"
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=plantilla_tipo_cambio.csv"
            )
        },
    )


@router.get("/plantilla-xlsx")
def descargar_plantilla_xlsx():
    """Descarga plantilla Excel vacía con encabezados."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Tipo de Cambio"
    ws.append(["fecha", "tasa"])
    ws.append(["2025-01-15", 1250.50])
    ws.append(["2025-01-16", 1255.00])

    # Ajustar ancho de columnas
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 15

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                "attachment; filename=plantilla_tipo_cambio.xlsx"
            )
        },
    )


@router.post("/sync-oficial", response_model=TipoCambioSyncResponse)
def api_sync_oficial(
    desde: str | None = Query(
        default=None, description="Fecha desde (YYYY-MM-DD)"
    ),
    hasta: str | None = Query(
        default=None, description="Fecha hasta (YYYY-MM-DD)"
    ),
    x_sync_token: str | None = Header(
        default=None,
        alias="X-Sync-Token",
        description="Token simple para autorizar la sincronización",
    ),
    db: Session = Depends(get_db),
):
    if settings.sync_job_token and x_sync_token != settings.sync_job_token:
        raise HTTPException(status_code=401, detail="Token inválido")

    desde_dt = date.fromisoformat(desde) if desde else None
    hasta_dt = date.fromisoformat(hasta) if hasta else None

    try:
        resumen = sync_bcra_tipos_cambio(
            db,
            desde=desde_dt,
            hasta=hasta_dt,
        )
    except TipoCambioSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TipoCambioSyncResponse(
        insertados=resumen.insertados,
        actualizados=resumen.actualizados,
        procesados=resumen.procesados,
        desde=resumen.desde,
        hasta=resumen.hasta,
    )
