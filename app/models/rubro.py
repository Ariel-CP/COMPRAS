from sqlalchemy import Boolean, Column, DateTime, Integer, String, text

from app.db import Base


class Rubro(Base):
    __tablename__ = "rubro"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(64), unique=True, nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    actualizado_en = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
