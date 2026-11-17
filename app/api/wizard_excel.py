import io
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps_auth import require_permission, user_has_any_permission
from app.db import get_db
from app.schemas.wizard_excel import ExcelImportResult, ExcelPreview
from app.services import wizard_excel_service as service

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/plan-produccion-mensual/asistente-oc/archivo-integral",
    tags=["wizard-excel"],
)


def _content(file: UploadFile) -> bytes:
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "Seleccioná el archivo XLSX de la plantilla integral.")
    content = file.file.read(service.MAX_BYTES + 1)
    if len(content) > service.MAX_BYTES:
        raise HTTPException(413, "El archivo supera 20 MB.")
    return content


def _origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "La carga debe realizarse desde el mismo sitio.")


@router.get("/plantilla.xlsx")
def download(
    anio: int = Query(..., ge=2000, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    user=Depends(require_permission("ui_plan_asistente_oc", False)),
):
    try:
        content = service.template(db, anio, mes)
    except service.WorkbookError as exc:
        raise HTTPException(400, str(exc)) from None
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="requerimiento_materiales_{anio}_{mes:02d}.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/validar", response_model=ExcelPreview)
def validate(
    request: Request,
    response: Response,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("ui_plan_asistente_oc", False)),
):
    _origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.preview(db, _content(archivo), int(user.get("id") or 0))
    except service.WorkbookError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/importar", response_model=ExcelImportResult)
def upload(
    request: Request,
    response: Response,
    archivo: UploadFile = File(...),
    token: str = Form(..., min_length=20, max_length=3000),
    confirmar: bool = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("ui_plan_asistente_oc", True)),
):
    _origin(request)
    if not user_has_any_permission(user, ("ui_plan_mensual", "ui_plan"), True):
        raise HTTPException(
            403,
            "También necesitás permiso de escritura de Plan mensual para cargar el plan del archivo.",
        )
    if not confirmar:
        raise HTTPException(400, "Confirmá la carga de los datos antes de guardar.")
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.import_and_calculate(
            db, _content(archivo), token, int(user.get("id") or 0)
        )
    except service.PreviewExpired as exc:
        raise HTTPException(409, str(exc)) from None
    except service.WorkbookError as exc:
        raise HTTPException(400, str(exc)) from None
    except Exception:
        # No incluir consultas, parámetros ni filas comerciales en logs/respuestas.
        logger.error(
            "Falló la carga integral del Wizard; se revirtieron sus escrituras"
        )
        raise HTTPException(
            500, "No se pudo guardar y calcular. La carga se revirtió completa."
        ) from None
