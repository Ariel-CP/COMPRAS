from datetime import date
from decimal import Decimal

from app.services.fx_provider import BcraFxProvider, FxProviderError


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class FakeClient:
    def __init__(self, response: FakeResponse):
        self._response = response
        self.last_headers = None
        self.last_url = None

    def get(self, url, headers=None):
        self.last_headers = headers
        self.last_url = url
        return self._response

    def close(self):
        pass


def test_client_constructs_without_token():
    c = BcraFxProvider()
    assert c is not None


def test_request_has_no_authorization_header_and_parses_list():
    data = [{"d": "2026-08-31", "v": "350.12"}]
    fake_resp = FakeResponse(status_code=200, data=data)
    fake_client = FakeClient(fake_resp)
    prov = BcraFxProvider(client=fake_client)

    desde = date(2026, 8, 31)
    hasta = date(2026, 8, 31)
    tasas = prov.fetch_range(desde, hasta)

    # verify request
    assert fake_client.last_url is not None
    # no Authorization header present
    headers = fake_client.last_headers or {}
    assert 'Authorization' not in headers

    assert len(tasas) == 1
    t = tasas[0]
    assert t.fecha == desde
    assert t.moneda == 'USD'
    assert isinstance(t.tasa, Decimal)
    assert t.tasa == Decimal('350.12')


def test_missing_records_raises_error():
    fake_resp = FakeResponse(status_code=200, data={})
    fake_client = FakeClient(fake_resp)
    prov = BcraFxProvider(client=fake_client)
    try:
        prov.fetch_range(date(2026, 1, 1), date(2026, 1, 1))
        assert False, "Expected FxProviderError"
    except FxProviderError:
        pass


def test_no_matching_records_in_range_raises_error():
    data = [{"fecha": "2026-08-01", "valor": "350.12"}]
    fake_resp = FakeResponse(status_code=200, data=data)
    fake_client = FakeClient(fake_resp)
    prov = BcraFxProvider(client=fake_client)

    try:
        prov.fetch_range(date(2026, 8, 10), date(2026, 8, 12))
        assert False, "Expected FxProviderError"
    except FxProviderError:
        pass
