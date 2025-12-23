from typing import List, Optional

import csv
import io

import openpyxl
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.plan_produccion_service import (
    calcular_requerimientos_valorizados,
    guardar_bulk,
    importar_desde_rows,
    listar_planes,
    resumen_planes,
    resumen_rango_planes,
)

router = APIRouter(prefix="/plan-produccion-mensual", tags=["plan-produccion-mensual"])


@router.get("/", response_model=dict)
def listar(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    producto_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    items, total = listar_planes(
        db,
        limit=limit,
        offset=offset,
        mes=mes,
        anio=anio,
        producto_id=producto_id,
    )
    return {"items": items, "total": total}


@router.get("/resumen", response_model=dict)
def resumen(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    items = resumen_planes(db, mes, anio)
    total_general = sum(i.get("cantidad", 0) for i in items)
    return {"items": items, "total_general": total_general}


@router.get("/requerimientos-valuados", response_model=dict)
def requerimientos_valuados(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    persistir: bool = Query(False),
    db: Session = Depends(get_db),
):
    data = calcular_requerimientos_valorizados(db, mes, anio, persistir)
    return data


@router.get("/requerimientos-valuados.xlsx")
def requerimientos_valuados_xlsx(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    persistir: bool = Query(False),
    db: Session = Depends(get_db),
):
    data = calcular_requerimientos_valorizados(db, mes, anio, persistir)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Requerimientos"
    headers = [
        "Codigo",
        "Nombre",
        "UM",
        "Cantidad",
        "Precio unit USD",
        "Precio unit ARS",
        "Total USD",
        "Total ARS",
        "Fuente",
        "Moneda origen",
        "Fecha precio",
        "FX USDtoARS",
        "FX estimada",
    ]
    ws.append(headers)

    for it in data.get("items", []):
        ws.append(
            [
                it.get("codigo"),
                it.get("nombre"),
                it.get("um_codigo"),
                float(it.get("cantidad") or 0),
                it.get("precio_unit_usd"),
                it.get("precio_unit_ars"),
                it.get("total_usd"),
                it.get("total_ars"),
                it.get("fuente"),
                it.get("moneda_origen"),
                it.get("fecha_precio"),
                it.get("fx_tasa_usd_ars"),
                it.get("fx_es_estimativa"),
            ]
        )

    ws.append([])
    ws.append([
        "",
        "",
        "",
        "",
        "",
        "Totales:",
        data.get("total_usd"),
        data.get("total_ars"),
    ])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    fname = f"requerimientos_{anio}_{mes:02d}.xlsx"
    headers_resp = {
        "Content-Disposition": (
            f"attachment; filename={fname}; filename*=UTF-8''{fname}"
        ),
        "Content-Type": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    }
    return StreamingResponse(
        stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=headers_resp,
    )


@router.get("/resumen-rango", response_model=dict)
def resumen_rango(
    desde_mes: int = Query(..., ge=1, le=12),
    desde_anio: int = Query(..., ge=2000, le=2100),
    hasta_mes: int = Query(..., ge=1, le=12),
    hasta_anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    try:
        data = resumen_rango_planes(
            db,
            desde_mes,
            desde_anio,
            hasta_mes,
            hasta_anio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return data


@router.post("/bulk", response_model=dict)
def guardar_en_lote(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    items: List[dict] = Body(default_factory=list),
    db: Session = Depends(get_db),
):
    count = guardar_bulk(db, mes, anio, items)
    return {"procesados": count}


@router.post("/import", response_model=dict)
async def importar_archivo(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    contenido = await file.read()
    nombre = (file.filename or "").lower()
    rows: List[dict] = []

    if nombre.endswith(".csv"):
        texto = contenido.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(texto))
        for r in reader:
            rows.append(
                {
                    "codigo": r.get("Codigo") or r.get("codigo"),
                    "mes": r.get("Mes") or r.get("mes"),
                    "anio": r.get("Año") or r.get("Anio") or r.get("anio"),
                    "cantidad": r.get("Cantidad") or r.get("cantidad"),
                }
            )
    else:
        wb = openpyxl.load_workbook(io.BytesIO(contenido))
        sheet = wb.active
        headers = [str(c.value).strip() if c.value else "" for c in next(sheet.rows)]
        idx = {h.lower(): i for i, h in enumerate(headers)}

        for fila in sheet.iter_rows(min_row=2):
            def tomar(key: str):
                pos = idx.get(key)
                if pos is None:
                    return None
                return fila[pos].value

            rows.append(
                {
                    "codigo": tomar("codigo"),
                    "mes": tomar("mes"),
                    "anio": tomar("año") or tomar("anio"),
                    "cantidad": tomar("cantidad"),
                }
            )

    procesadas = importar_desde_rows(db, rows)
    return {"procesadas": procesadas}


@router.get("/plantilla.csv")
def plantilla_csv():
    return FileResponse(
        "import/plan_produccion_template.csv",
        media_type="text/csv",
        filename="plan_produccion_template.csv",
    )


@router.get("/plantilla.xlsx")
def plantilla_xlsx(db: Session = Depends(get_db)):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plan"
    headers = ["Codigo", "Nombre", "Mes", "Año", "Cantidad"]
    ws.append(headers)
    ws.append(["PT-0001", "Producto Terminado Ejemplo 1", 12, 2025, 100])
    ws.append(["PT-0002", "Producto Terminado Ejemplo 2", 12, 2025, 200])
    ws.append(["PT-0003", "Producto Terminado Ejemplo 3", 12, 2025, 0])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    headers_resp = {
        "Content-Disposition": (
            "attachment; filename=plan_produccion_template.xlsx; "
            "filename*=UTF-8''plan_produccion_template.xlsx"
        ),
        "Content-Type": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    }

    return StreamingResponse(
        stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=headers_resp,
    )
