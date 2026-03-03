from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.rubro import Rubro


def listar_rubros(db: Session, only_active: bool = False) -> List[dict]:
    query = db.query(Rubro)
    if only_active:
        query = query.filter(Rubro.activo.is_(True))
    rubros = query.order_by(Rubro.nombre).all()
    return [
        {
            "id": r.id,
            "nombre": r.nombre,
            "activo": r.activo,
            "creado_en": r.creado_en,
            "actualizado_en": r.actualizado_en,
        }
        for r in rubros
    ]


def _normalize_nombre(nombre: str) -> str:
    return nombre.strip()


def crear_rubro(db: Session, nombre: str) -> Rubro:
    nombre = _normalize_nombre(nombre)
    rubro = Rubro(nombre=nombre)
    db.add(rubro)
    db.commit()
    db.refresh(rubro)
    return rubro


def obtener_rubro_por_id(db: Session, rubro_id: int) -> Optional[dict]:
    rubro = db.query(Rubro).filter(Rubro.id == rubro_id).first()
    if rubro:
        return {"id": rubro.id, "nombre": rubro.nombre}
    return None


def actualizar_rubro(db: Session, rubro_id: int, nombre: str) -> Optional[Rubro]:
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    nombre = _normalize_nombre(nombre)
    rubro = db.query(Rubro).filter(Rubro.id == rubro_id).first()
    if not rubro:
        return None
    nombre_anterior = rubro.nombre
    rubro.nombre = nombre  # type: ignore[assignment]
    try:
        db.commit()
        # Actualizar productos que tengan el nombre anterior de rubro
        db.execute(
            text("UPDATE producto SET rubro = :nuevo WHERE rubro = :anterior"),
            {"nuevo": nombre, "anterior": nombre_anterior}
        )
        db.commit()
        db.refresh(rubro)
        return rubro
    except SQLAlchemyError:
        db.rollback()

        raise


def eliminar_rubro(db: Session, rubro_id: int) -> bool:
    rubro = db.query(Rubro).filter(Rubro.id == rubro_id).first()
    if not rubro:
        return False
    db.delete(rubro)
    db.commit()
    return True


def existe_rubro_unico(db: Session, nombre: str, exclude_id: Optional[int] = None) -> bool:
    nombre = _normalize_nombre(nombre)
    query = db.query(Rubro).filter(Rubro.nombre == nombre)
    if exclude_id:
        query = query.filter(Rubro.id != exclude_id)
    return db.query(query.exists()).scalar()
