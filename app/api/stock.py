from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.stock import StockItemOut, StockImportResult
from ..services.stock_import_service import (
    importar_stock_csv_o_excel,
    listar_stock_periodo,
    resumen_stock_periodo,
)
import os
from fastapi.responses import FileResponse

router = APIRouter()

# Endpoint para descargar plantilla XLSX de stock mensual
@router.get("/template-xlsx")
def descargar_template_xlsx():
    from openpyxl import Workbook
    file_path = "template_stock_mensual.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["producto_codigo", "stock_disponible"])
    wb.save(file_path)
    return FileResponse(file_path, filename="template_stock_mensual.xlsx")


@router.post("/{anio}/{mes}/import", response_model=StockImportResult)
def importar_stock(
    anio: int,
    mes: int,
    archivo: UploadFile = File(...),
    fecha_corte: str = Form(..., description="Fecha de corte YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    if not archivo.filename:
        raise HTTPException(status_code=400, detail="Archivo requerido")
    return importar_stock_csv_o_excel(db, anio, mes, archivo, fecha_corte)


@router.get("/{anio}/{mes}", response_model=List[StockItemOut])
def listar_stock(anio: int, mes: int, q: str | None = None, db: Session = Depends(get_db)):
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    return listar_stock_periodo(db, anio, mes, q)


@router.get("/{anio}/{mes}/resumen")
def resumen_stock(anio: int, mes: int, db: Session = Depends(get_db)):
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="mes debe estar entre 1 y 12")
    return resumen_stock_periodo(db, anio, mes)
