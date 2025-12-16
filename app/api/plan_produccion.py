from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Body
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import csv
import io
import openpyxl

from app.models.plan_produccion import PlanProduccionCreate, PlanProduccionUpdate, PlanProduccionOut
from app.services.plan_produccion_service import (
    listar_planes,
    crear_plan,
    actualizar_plan,
    eliminar_plan,
    resumen_planes,
    guardar_bulk,
    importar_desde_rows,
)
from app.api.deps import get_db

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
        db, limit=limit, offset=offset, mes=mes, anio=anio, producto_id=producto_id
    )
    return {"items": items, "total": total}


@router.get("/resumen", response_model=dict)
def resumen(mes: int = Query(..., ge=1, le=12), anio: int = Query(..., ge=2000, le=2100), db: Session = Depends(get_db)):
    items = resumen_planes(db, mes, anio)
    total_general = sum(i.get("cantidad", 0) for i in items)
    return {"items": items, "total_general": total_general}


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
async def importar_archivo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contenido = await file.read()
    nombre = file.filename.lower()
    rows = []
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
        for row in sheet.iter_rows(min_row=2):
            def val(key):
                pos = idx.get(key)
                if pos is None:
                    return None
                cell = row[pos]
                return cell.value

            rows.append(
                {
                    "codigo": val("codigo"),
                    "mes": val("mes"),
                    "anio": val("año") or val("anio"),
                    "cantidad": val("cantidad"),
                }
            )
    procesadas = importar_desde_rows(db, rows)
    return {"procesadas": procesadas}


@router.get("/plantilla.csv")
def plantilla_csv():
    return FileResponse("import/plan_produccion_template.csv", media_type="text/csv", filename="plan_produccion_template.csv")


@router.get("/plantilla.xlsx")
def plantilla_xlsx(db: Session = Depends(get_db)):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plan"
    headers = ["Codigo", "Nombre", "Mes", "Año", "Cantidad"]
    ws.append(headers)
    # filas de ejemplo
    ws.append(["PT-0001", "Producto Terminado Ejemplo 1", 12, 2025, 100])
    ws.append(["PT-0002", "Producto Terminado Ejemplo 2", 12, 2025, 200])
    ws.append(["PT-0003", "Producto Terminado Ejemplo 3", 12, 2025, 0])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    headers_resp = {
        "Content-Disposition": "attachment; filename=plan_produccion_template.xlsx"
    }
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers_resp)
