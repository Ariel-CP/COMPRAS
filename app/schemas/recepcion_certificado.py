from datetime import datetime

from pydantic import BaseModel, Field


class CertificadoDocumentoOut(BaseModel):
    id: int
    nombre: str
    tipo_mime: str
    tamano: int
    sha256: str
    fecha_creacion: datetime
    usuario_nombre: str | None = None


class RecepcionCertificadoOut(BaseModel):
    linea_id: int
    recepcion_id: int
    recibido: bool
    fecha_actualizacion: datetime | None = None
    usuario_nombre: str | None = None
    documentos: list[CertificadoDocumentoOut] = Field(default_factory=list)
