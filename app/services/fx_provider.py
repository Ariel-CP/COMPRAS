"""Clientes para obtener tipos de cambio oficiales."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

import httpx


@dataclass(slots=True)
class FxRate:
    fecha: date
    moneda: str
    tipo: str
    tasa: float
    origen: str
    notas: Optional[str] = None


class FxProviderError(RuntimeError):
    """Errores al consultar proveedores de FX."""


class BcraFxProvider:
    """Cliente mínimo para el API oficial del BCRA (estadisticasbcra).

    La API expone series identificadas por endpoints como ``usd_of``
    (dólar oficial) y ``usd_mayorista``. Cada serie devuelve registros
    con claves ``d`` (fecha) y ``v`` (valor). Este cliente obtiene ambas
    series y normaliza el resultado a ``FxRate``.
    """

    _SERIES_DEF = (
        {
            "endpoint": "usd_of",
            "moneda": "USD",
            "tipo": "VENTA",
            "notas": "Serie oficial BCRA usd_of",
        },
        {
            "endpoint": "usd_mayorista",
            "moneda": "USD_MAY",
            "tipo": "PROMEDIO",
            "notas": "Serie mayorista BCRA usd_mayorista",
        },
    )

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not token:
            raise ValueError(
                "Se requiere token BCRA para inicializar el cliente"
            )
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client = client

    def _http_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _request_series(self, endpoint: str) -> Iterable[dict]:
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"BEARER {self._token}"}
        try:
            resp = self._http_client().get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - requests path
            raise FxProviderError(f"Error consultando {url}: {exc}") from exc
        data = resp.json()
        if not isinstance(data, list):
            raise FxProviderError(
                f"Respuesta inesperada en {endpoint}: se esperaba lista"
            )
        return data

    @staticmethod
    def _map_item(
        item: dict,
        *,
        moneda: str,
        tipo: str,
        notas: Optional[str],
    ) -> FxRate:
        try:
            fecha = date.fromisoformat(item["d"])
            tasa = float(item["v"])
        except (KeyError, ValueError, TypeError) as exc:
            raise FxProviderError(
                f"Registro BCRA inválido para {moneda}: {item}"
            ) from exc
        return FxRate(
            fecha=fecha,
            moneda=moneda,
            tipo=tipo,
            tasa=tasa,
            origen="OTRO",
            notas=notas,
        )

    def fetch_range(self, desde: date, hasta: date) -> List[FxRate]:
        if desde > hasta:
            raise ValueError("La fecha 'desde' no puede ser mayor a 'hasta'")
        resultados: List[FxRate] = []
        for serie in self._SERIES_DEF:
            items = self._request_series(serie["endpoint"])
            for item in items:
                rate = self._map_item(
                    item,
                    moneda=serie["moneda"],
                    tipo=serie["tipo"],
                    notas=serie.get("notas"),
                )
                if desde <= rate.fecha <= hasta:
                    resultados.append(rate)
        return resultados

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> "BcraFxProvider":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
