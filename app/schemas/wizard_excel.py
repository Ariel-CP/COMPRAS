from pydantic import BaseModel, Field


class ExcelIssue(BaseModel):
    hoja: str
    fila: int
    campo: str
    mensaje: str


class ExcelPreview(BaseModel):
    valido: bool
    errores: list[ExcelIssue]
    total_errores: int
    anio: int | None = None
    mes: int | None = None
    anio_stock: int | None = None
    mes_stock: int | None = None
    filas: dict[str, int] = Field(default_factory=dict)
    existentes: dict[str, int] = Field(default_factory=dict)
    token: str | None = None


class ExcelImportResult(BaseModel):
    importacion: ExcelPreview
    calculo: dict
