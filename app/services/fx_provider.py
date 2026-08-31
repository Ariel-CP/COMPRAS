"""Clientes para obtener tipos de cambio oficiales."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional
from decimal import Decimal

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
    """Cliente para la API pública de Estadísticas Cambiarias del BCRA.

    Este cliente no requiere token ni autorización. Realiza una llamada
    al endpoint `/estadisticascambiarias/v1.0/Cotizaciones/USD` y mappea
    los resultados a `FxRate` usando `Decimal` para la tasa.
    """

    _ENDPOINT_USD = "/estadisticascambiarias/v1.0/Cotizaciones/USD"

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

    def _request_usd(self) -> dict:
        url = f"{self._base_url}{self._ENDPOINT_USD}"
        headers = {"Accept": "application/json", "Accept-Language": "es-AR"}
        try:
            resp = self._http_client().get(url, headers=headers)
            resp.raise_for_status()
        except httpx.RequestError as exc:
            raise FxProviderError(f"Error de conexión a BCRA {url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise FxProviderError(f"HTTP {exc.response.status_code} al consultar {url}") from exc
        try:
            data = resp.json()
        except Exception as exc:
            raise FxProviderError(f"Respuesta JSON inválida desde BCRA: {exc}") from exc
        return data

    @staticmethod
    def _map_record(record: dict) -> FxRate:
        # La estructura puede variar; intentamos mapear campos comunes
        try:
            # Buscar fecha en campos comunes
            if "d" in record:
                fecha = date.fromisoformat(record["d"])  # formato ISO
            elif "fecha" in record:
                fecha = date.fromisoformat(record["fecha"])
            else:
                raise KeyError("fecha")

            # valor puede estar en 'v' o 'valor' o 'p'; convertir a Decimal
            # Soporte estructura BCRA reciente: registro con 'detalle' -> handled upstream
            if "v" in record:
                raw = record["v"]
            elif "valor" in record:
                raw = record["valor"]
            elif "p" in record:
                raw = record["p"]
            elif "tipoCotizacion" in record:
                raw = record["tipoCotizacion"]
            else:
                raise KeyError("valor")
            tasa = Decimal(str(raw))
        except (KeyError, ValueError, TypeError) as exc:
            raise FxProviderError(f"Registro BCRA inválido: {record}") from exc

        return FxRate(
            fecha=fecha,
            moneda="USD",
            tipo="MAYORISTA",
            tasa=tasa,
            origen="BCRA_OFICIAL",
            notas=None,
        )

    def fetch_range(self, desde: date, hasta: date) -> List[FxRate]:
        if desde > hasta:
            raise ValueError("La fecha 'desde' no puede ser mayor a 'hasta'")
        data = self._request_usd()
        # La API pública puede devolver varias estructuras. Normalizamos a una lista
        records: List[dict] = []
        if isinstance(data, dict):
            # Caso: {'fecha': '2026-08-28', 'detalle': [ {codigoMoneda: 'USD', 'tipoCotizacion': 1512.0}, ... ]}
            if "detalle" in data and isinstance(data["detalle"], list):
                for item in data["detalle"]:
                    # adjuntar la fecha al item para mapearlo
                    rec = dict(item)
                    rec["fecha"] = data.get("fecha")
                    # mapear posibles campos de valor a 'tipoCotizacion'
                    if "tipoCotizacion" in item:
                        rec["tipoCotizacion"] = item.get("tipoCotizacion")
                    records.append(rec)
            elif "results" in data and isinstance(data["results"], list):
                    # Expand posibles objetos con 'detalle' dentro de results
                    tmp = data.get("results") or []
                    expanded: List[dict] = []
                    for entry in tmp:
                        if isinstance(entry, dict) and isinstance(entry.get("detalle"), list):
                            for item in entry.get("detalle", []):
                                rec = dict(item)
                                rec["fecha"] = entry.get("fecha")
                                if "tipoCotizacion" in item:
                                    rec["tipoCotizacion"] = item.get("tipoCotizacion")
                                expanded.append(rec)
                        else:
                            expanded.append(entry)
                    records = expanded
            else:
                # buscar listas en claves conocidas
                for k in ("data", "serie", "series"):
                    if isinstance(data.get(k), list):
                        records = data.get(k)
                        break
        elif isinstance(data, list):
            # Puede venir una lista de objetos con 'detalle'
            # e.g. [ { 'fecha': '2026-08-28', 'detalle': [...] } ]
            if data and isinstance(data[0], dict) and "detalle" in data[0]:
                for entry in data:
                    if isinstance(entry.get("detalle"), list):
                        for item in entry["detalle"]:
                            rec = dict(item)
                            rec["fecha"] = entry.get("fecha")
                            if "tipoCotizacion" in item:
                                rec["tipoCotizacion"] = item.get("tipoCotizacion")
                            records.append(rec)
            else:
                records = data

        if not records:
            raise FxProviderError("Respuesta BCRA: no se encontraron registros para USD")

        resultados: List[FxRate] = []
        for rec in records:
            # Filtrar por moneda si la estructura lo provee
            codigo = rec.get("codigoMoneda") or rec.get("moneda") or rec.get("codigo")
            if codigo and str(codigo).upper() != "USD":
                continue
            rate = self._map_record(rec)
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
