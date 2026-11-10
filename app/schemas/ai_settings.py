from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AISettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proveedor: Literal["openai"] = "openai"
    modelo: str = Field(default="", max_length=100, pattern=r"^[a-zA-Z0-9._:-]*$")
    timeout_segundos: int = Field(default=30, ge=5, le=120)
    max_tokens_salida: int = Field(default=1500, ge=128, le=8192)
    max_caracteres_envio: int = Field(default=12000, ge=1000, le=50000)
    solicitudes_por_minuto: int = Field(default=3, ge=1, le=60)
    presupuesto_diario_usd: Decimal = Field(default=Decimal("1.00"), gt=0, le=1000)
    api_key: SecretStr | None = None
    eliminar_clave_local: bool = False


class ConnectionTestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmar_envio: Literal[True]
