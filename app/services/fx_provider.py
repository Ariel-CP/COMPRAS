"""Clientes para obtener tipos de cambio oficiales."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

import httpx


@dataclass(slots=True)
class FxRate:
    fecha: date
    moneda: str
    tipo: str
    tasa: Decimal
    origen: str
    notas: Optional[str] = None


class FxProviderError(RuntimeError):
    """Errores al consultar proveedores de FX."""


class BcraFxProvider:
    """Cliente para la serie minorista de Estadísticas Monetarias v4 del BCRA.

    Este cliente no requiere token ni autorización. Realiza una llamada
    a la variable 4 (promedio vendedor minorista) y mapea los resultados
    a `FxRate` usando `Decimal` para la tasa.
    """

    _ENDPOINT_USD = "/estadisticas/v4.0/monetarias/4"

    def __init__(
        self,
        base_url: str = "https://api.bcra.gob.ar",
        *,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    def _http_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _request_usd(
        self, desde: Optional[date] = None, hasta: Optional[date] = None
    ) -> dict:
        """Obtiene cotizaciones minoristas USD del BCRA.

        Si desde/hasta se omiten, el BCRA aplica sus valores predeterminados.
        """

        url = f"{self._base_url}{self._ENDPOINT_USD}"
        headers = {"Accept": "application/json", "Accept-Language": "es-AR"}
        params: dict[str, str] = {}
        if desde is not None:
            params["desde"] = desde.isoformat()
        if hasta is not None:
            params["hasta"] = hasta.isoformat()
        try:
            resp = self._http_client().get(
                url, headers=headers, params=params if params else None
            )
            resp.raise_for_status()
        except httpx.RequestError as exc:
            raise FxProviderError(f"Error de conexión a BCRA {url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            msg = f"HTTP {exc.response.status_code} al consultar {url}"
            raise FxProviderError(msg) from exc
        try:
            data = resp.json()
        except Exception as exc:
            raise FxProviderError(f"Respuesta JSON inválida desde BCRA: {exc}") from exc
        return data

    @staticmethod
    def _map_record(record: dict) -> FxRate:
        try:
            fecha = date.fromisoformat(str(record["fecha"]))
            tasa = Decimal(str(record["valor"]))
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            raise FxProviderError(f"Registro BCRA inválido: {record}") from exc

        return FxRate(
            fecha=fecha,
            moneda="USD",
            tipo="VENTA",
            tasa=tasa,
            origen="OTRO",
            notas=None,
        )

    def fetch_range(self, desde: date, hasta: date) -> List[FxRate]:
        if desde > hasta:
            raise ValueError("La fecha 'desde' no puede ser mayor a 'hasta'")
        data = self._request_usd(desde=desde, hasta=hasta)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise FxProviderError("Respuesta BCRA minorista sin resultados válidos")

        records: List[dict] = []
        for result in data["results"]:
            if not isinstance(result, dict):
                raise FxProviderError(
                    "Respuesta BCRA minorista contiene una serie inválida"
                )
            detalle = result.get("detalle")
            if not isinstance(detalle, list):
                raise FxProviderError("Respuesta BCRA minorista sin detalle válido")
            records.extend(item for item in detalle if isinstance(item, dict))

        if not records:
            raise FxProviderError("Respuesta BCRA: no se encontraron registros para USD")

        resultados: List[FxRate] = []
        for rec in records:
            rate = self._map_record(rec)
            if desde <= rate.fecha <= hasta:
                resultados.append(rate)

        if not resultados:
            raise FxProviderError(
                "Respuesta BCRA: no se encontraron registros para USD en el rango "
                f"{desde.isoformat()} a {hasta.isoformat()}"
            )
        return resultados

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> "BcraFxProvider":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
