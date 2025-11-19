from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils.health import db_status


router = APIRouter()


@router.get("/db", response_class=JSONResponse, tags=["health"])
def health_db(db: Session = Depends(get_db)):
    """Devuelve el estado actual de la conexión a la base de datos."""
    return db_status(db)
