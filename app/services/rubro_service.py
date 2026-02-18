from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.rubro import Rubro


def listar_rubros(db: Session, only_active: bool = False) -> List[dict]:
    query = db.query(Rubro)
    if only_active:
        query = query.filter(Rubro.activo.is_(True))
    rubros = query.order_by(Rubro.nombre).all()
    return [
        {"id": r.id, "nombre": r.nombre, "activo": r.activo}
        for r in rubros
    ]

<<<<<<< HEAD

def _normalize_nombre(nombre: str) -> str:
    return nombre.strip()


=======
def _normalize_nombre(nombre: str) -> str:
    return nombre.strip()

>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54
def crear_rubro(db: Session, nombre: str) -> Rubro:
    nombre = _normalize_nombre(nombre)
    rubro = Rubro(nombre=nombre)
    db.add(rubro)
    db.commit()
    db.refresh(rubro)
    return rubro

<<<<<<< HEAD

=======
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54
def obtener_rubro_por_id(db: Session, rubro_id: int) -> Optional[dict]:
    rubro = db.query(Rubro).filter(Rubro.id == rubro_id).first()
    if rubro:
        return {"id": rubro.id, "nombre": rubro.nombre}
    return None

<<<<<<< HEAD

def actualizar_rubro(db: Session, rubro_id: int, nombre: str) -> Optional[Rubro]:
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy import text
=======
def actualizar_rubro(db: Session, rubro_id: int, nombre: str) -> Optional[Rubro]:
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54
    nombre = _normalize_nombre(nombre)
    rubro = db.query(Rubro).filter(Rubro.id == rubro_id).first()
    if not rubro:
        return None
<<<<<<< HEAD
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
    except SQLAlchemyError as ex:
        db.rollback()
        # Loguear el error en consola para depuración
        print("[ERROR actualizar_rubro]", ex)
        raise

=======
    rubro.nombre = nombre
    db.commit()
    db.refresh(rubro)
    return rubro
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54

def eliminar_rubro(db: Session, rubro_id: int) -> bool:
    rubro = db.query(Rubro).filter(Rubro.id == rubro_id).first()
    if not rubro:
        return False
    db.delete(rubro)
    db.commit()
    return True

<<<<<<< HEAD

=======
>>>>>>> e0cbf5e965dc7e466c7150be8761ee1658919b54
def existe_rubro_unico(db: Session, nombre: str, exclude_id: Optional[int] = None) -> bool:
    nombre = _normalize_nombre(nombre)
    query = db.query(Rubro).filter(Rubro.nombre == nombre)
    if exclude_id:
        query = query.filter(Rubro.id != exclude_id)
    return db.query(query.exists()).scalar()
