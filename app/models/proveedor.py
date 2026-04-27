from sqlalchemy import Boolean, Column, DateTime, Integer, String, text

from app.db import Base


class Proveedor(Base):
    __tablename__ = "proveedor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(64), unique=True, nullable=False)
    nombre = Column(String(160), nullable=False)
    contacto_nombre = Column(String(128), nullable=True)
    email = Column(String(128), nullable=True)
    telefono = Column(String(64), nullable=True)
    cuit = Column(String(20), nullable=True)
    direccion = Column(String(255), nullable=True)
    localidad = Column(String(128), nullable=True)
    provincia = Column(String(128), nullable=True)
    notas = Column(String(255), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    fecha_actualizacion = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
