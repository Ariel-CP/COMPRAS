from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.unidad import UnidadMedidaOut
from ..services.unidad_service import listar_unidades


router = APIRouter()


@router.get("/", response_model=list[UnidadMedidaOut])
def api_listar_unidades(db: Session = Depends(get_db)):
    try:
        return listar_unidades(db)
    except SQLAlchemyError as ex:
        raise HTTPException(
            status_code=500, detail=str(getattr(ex, "orig", ex))
        ) from ex
