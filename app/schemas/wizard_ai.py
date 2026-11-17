from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WizardContext(StrictModel):
    anio: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)
    paso: int = Field(ge=1, le=5)
    productos_plan: int = Field(ge=0, le=1000000)
    registros_stock_pt: int = Field(ge=0, le=1000000)
    registros_deuda: int = Field(ge=0, le=1000000)
    accion_anterior: Literal[
        "ninguna",
        "excel_integral",
        "periodo",
        "cargar_plan",
        "stock_mp",
        "laf",
        "stock_pt",
        "deuda",
        "importar_mp",
        "importar_laf",
        "importar_pt",
        "importar_deuda",
        "simular",
        "revisar",
    ] = "ninguna"
    resultado_accion_anterior: Literal["sin_accion", "completada", "fallida"] = (
        "sin_accion"
    )


class ChatMessage(StrictModel):
    rol: Literal["user", "assistant"]
    texto: str = Field(min_length=1, max_length=4000)


class WizardChatIn(StrictModel):
    confirmar_envio: Literal[True]
    mensaje: str = Field(min_length=1, max_length=4000)
    historial: list[ChatMessage] = Field(default_factory=list, max_length=30)
    contexto: WizardContext


class WizardProposal(StrictModel):
    mensaje: str = Field(min_length=1, max_length=4000)
    accion: Literal[
        "preguntar",
        "excel_integral",
        "periodo",
        "cargar_plan",
        "stock_mp",
        "laf",
        "stock_pt",
        "deuda",
        "importar_mp",
        "importar_laf",
        "importar_pt",
        "importar_deuda",
        "simular",
        "revisar",
    ]
    anio: int | None = Field(ge=2000, le=2100)
    mes: int | None = Field(ge=1, le=12)
