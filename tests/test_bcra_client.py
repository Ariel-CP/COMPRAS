from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.services.fx_provider import BcraFxProvider, FxProviderError


def _provider(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BcraFxProvider(client=client)


def _minorista_payload(detalle):
    return {
        "status": 200,
        "metadata": {"resultset": {"count": len(detalle)}},
        "results": [{"idVariable": 4, "detalle": detalle}],
    }


def test_client_constructs_without_token():
    c = BcraFxProvider()
    assert c is not None


def test_request_uses_v4_minorista_series_and_parses_results():
    desde = date(2026, 8, 31)
    hasta = date(2026, 8, 31)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json=_minorista_payload([{"fecha": "2026-08-31", "valor": "350.12"}]),
        )

    provider = _provider(handler)
    try:
        tasas = provider.fetch_range(desde, hasta)
    finally:
        provider.close()

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/estadisticas/v4.0/monetarias/4"
    assert dict(request.url.params) == {
        "desde": "2026-08-31",
        "hasta": "2026-08-31",
    }
    assert "authorization" not in request.headers

    assert len(tasas) == 1
    tasa = tasas[0]
    assert tasa.fecha == desde
    assert tasa.moneda == "USD"
    assert tasa.tipo == "VENTA"
    assert tasa.origen == "OTRO"
    assert isinstance(tasa.tasa, Decimal)
    assert tasa.tasa == Decimal("350.12")


def test_empty_detail_raises_provider_error():
    provider = _provider(
        lambda request: httpx.Response(200, json=_minorista_payload([]))
    )
    try:
        with pytest.raises(FxProviderError, match="no se encontraron registros"):
            provider.fetch_range(date(2026, 1, 1), date(2026, 1, 31))
    finally:
        provider.close()


def test_records_outside_requested_range_are_rejected():
    provider = _provider(
        lambda request: httpx.Response(
            200,
            json=_minorista_payload([{"fecha": "2026-08-01", "valor": "350.12"}]),
        )
    )
    try:
        with pytest.raises(FxProviderError, match="en el rango"):
            provider.fetch_range(date(2026, 8, 10), date(2026, 8, 12))
    finally:
        provider.close()


def test_invalid_detail_record_raises_provider_error():
    provider = _provider(
        lambda request: httpx.Response(
            200,
            json=_minorista_payload([{"fecha": "2026-08-31"}]),
        )
    )
    try:
        with pytest.raises(FxProviderError, match="Registro BCRA inválido"):
            provider.fetch_range(date(2026, 8, 31), date(2026, 8, 31))
    finally:
        provider.close()


def test_http_error_raises_provider_error():
    provider = _provider(lambda request: httpx.Response(500, request=request))
    try:
        with pytest.raises(FxProviderError, match="HTTP 500"):
            provider.fetch_range(date(2026, 8, 31), date(2026, 8, 31))
    finally:
        provider.close()


def test_invalid_json_raises_provider_error():
    provider = _provider(
        lambda request: httpx.Response(200, content=b"not-json", request=request)
    )
    try:
        with pytest.raises(FxProviderError, match="Respuesta JSON inválida"):
            provider.fetch_range(date(2026, 8, 31), date(2026, 8, 31))
    finally:
        provider.close()
