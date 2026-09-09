"""Cliente BCRA Estadisticas Monetarias v4.0 para la serie A3500."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx

from app.services.fx_provider import FxProviderError, FxRate


class BcraMonetariasProvider:
    """Obtiene la serie oficial de tipo de cambio mayorista del BCRA."""

    _CATALOG_ENDPOINT = "/estadisticas/v4.0/monetarias"
    _A3500_DESCRIPTION = "Tipo de cambio mayorista de referencia"
    _A3500_DESCRIPTION_REQUESTED = (
        "Tipo de Cambio Mayorista ($ por USD) Comunicación A 3500 - Referencia"
    )

    def __init__(
        self,
        base_url: str = "https://api.bcra.gob.ar",
        *,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
        catalog_page_size: int = 1000,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._catalog_page_size = catalog_page_size

    def _http_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _get_json(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict:
        url = f"{self._base_url}{endpoint}"
        try:
            response = self._http_client().get(
                url,
                headers={"Accept": "application/json", "Accept-Language": "es-AR"},
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise FxProviderError(f"Timeout al consultar BCRA {url}") from exc
        except httpx.RequestError as exc:
            raise FxProviderError(f"Error de conexión a BCRA {url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise FxProviderError(
                f"HTTP {exc.response.status_code} al consultar BCRA {url}"
            ) from exc
        except (ValueError, TypeError) as exc:
            raise FxProviderError(f"Respuesta JSON inválida desde BCRA {url}") from exc

        if not isinstance(payload, dict):
            raise FxProviderError(f"Respuesta JSON inválida desde BCRA {url}")
        return payload

    @staticmethod
    def _descripcion_normalizada(value: Any) -> str:
        return " ".join(str(value or "").split())

    def encontrar_variable_mayorista(self) -> tuple[int, str]:
        """Descubre y valida la variable oficial de la serie A3500."""
        offset = 0
        while True:
            payload = self._get_json(
                self._CATALOG_ENDPOINT,
                {"offset": offset, "limit": self._catalog_page_size},
            )
            variables = payload.get("results")
            if not isinstance(variables, list):
                raise FxProviderError("Catálogo BCRA sin variables disponibles")

            for variable in variables:
                if not isinstance(variable, dict):
                    continue
                descripcion = self._descripcion_normalizada(variable.get("descripcion"))
                if descripcion in {
                    self._A3500_DESCRIPTION,
                    self._A3500_DESCRIPTION_REQUESTED,
                }:
                    try:
                        return int(variable["idVariable"]), descripcion
                    except (KeyError, TypeError, ValueError) as exc:
                        raise FxProviderError(
                            "La variable mayorista del BCRA no tiene idVariable válido"
                        ) from exc

            metadata = payload.get("metadata", {}).get("resultset", {})
            count = metadata.get("count")
            page_limit = metadata.get("limit") or self._catalog_page_size
            if not variables or not isinstance(count, int):
                break
            offset += int(page_limit)
            if offset >= count:
                break

        raise FxProviderError(
            "No se encontró en BCRA la variable oficial de tipo de cambio mayorista"
        )

    def fetch_range(self, desde: date, hasta: date) -> list[FxRate]:
        """Obtiene solo las fechas y valores publicados por BCRA para A3500."""
        if desde > hasta:
            raise ValueError("La fecha 'desde' no puede ser mayor a 'hasta'")

        id_variable, descripcion = self.encontrar_variable_mayorista()
        payload = self._get_json(
            f"{self._CATALOG_ENDPOINT}/{id_variable}",
            {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise FxProviderError("Respuesta BCRA mayorista sin resultados")

        rates: list[FxRate] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            for item in result.get("detalle", []):
                if not isinstance(item, dict):
                    continue
                try:
                    fecha = date.fromisoformat(str(item["fecha"]))
                    tasa = Decimal(str(item["valor"]))
                except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                    raise FxProviderError(
                        f"Registro mayorista BCRA inválido: {item}"
                    ) from exc
                if tasa <= 0 or not desde <= fecha <= hasta:
                    continue
                rates.append(
                    FxRate(
                        fecha=fecha,
                        moneda="USD",
                        tipo="MAYORISTA",
                        tasa=tasa,
                        origen="BCRA_A3500",
                        notas=f"idVariable={id_variable}; {descripcion}",
                    )
                )

        if not rates:
            raise FxProviderError(
                f"BCRA no devolvió cotizaciones mayoristas entre {desde} y {hasta}"
            )
        return rates

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> "BcraMonetariasProvider":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
