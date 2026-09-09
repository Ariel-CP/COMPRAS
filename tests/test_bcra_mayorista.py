from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.bcra_monetarias_provider import BcraMonetariasProvider
from app.services.tipo_cambio_sync_service import sync_bcra_mayorista_historico


def _provider(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BcraMonetariasProvider(client=client)


def test_provider_descubre_a3500_y_normaliza_decimal():
    def handler(request):
        if request.url.path.endswith("/monetarias"):
            return httpx.Response(
                200,
                json={
                    "metadata": {"resultset": {"count": 1, "offset": 0, "limit": 1000}},
                    "results": [
                        {
                            "idVariable": 5,
                            "descripcion": "Tipo de cambio mayorista de referencia",
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "idVariable": 5,
                        "detalle": [
                            {"fecha": "2026-05-29", "valor": 1410.2904},
                            {"fecha": "2026-05-30", "valor": 1411.0},
                        ],
                    }
                ]
            },
        )

    rates = _provider(handler).fetch_range(date(2026, 5, 1), date(2026, 5, 31))

    assert [(rate.fecha, rate.tasa) for rate in rates] == [
        (date(2026, 5, 29), Decimal("1410.2904")),
        (date(2026, 5, 30), Decimal("1411.0")),
    ]
    assert all(rate.moneda == "USD" for rate in rates)
    assert all(rate.tipo == "MAYORISTA" for rate in rates)
    assert all(rate.origen == "BCRA_A3500" for rate in rates)


def test_provider_rechaza_catalogo_sin_variable_a3500():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "metadata": {"resultset": {"count": 1, "offset": 0, "limit": 1000}},
                "results": [
                    {"idVariable": 4, "descripcion": "Tipo de cambio minorista"}
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = BcraMonetariasProvider(client=client)
        try:
            provider.encontrar_variable_mayorista()
        except Exception as exc:  # noqa: BLE001
            assert "No se encontró" in str(exc)
        else:
            raise AssertionError("Se aceptó una variable que no es A3500")


def test_sync_mayorista_es_idempotente_y_no_mezcla_minorista():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
                CREATE TABLE tipo_cambio_hist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha DATE NOT NULL,
                    moneda TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    tasa DECIMAL(18,6) NOT NULL,
                    origen TEXT NOT NULL,
                    notas TEXT
                )
                """))
        conn.execute(text("""
                INSERT INTO tipo_cambio_hist
                    (fecha, moneda, tipo, tasa, origen)
                VALUES ('2026-05-29', 'USD_MAY', 'VENTA', 1400.0, 'MANUAL')
                """))

    def handler(request):
        if request.url.path.endswith("/monetarias"):
            return httpx.Response(
                200,
                json={
                    "metadata": {"resultset": {"count": 1, "offset": 0, "limit": 1000}},
                    "results": [
                        {
                            "idVariable": 5,
                            "descripcion": "Tipo de cambio mayorista de referencia",
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "idVariable": 5,
                        "detalle": [{"fecha": "2026-05-29", "valor": 1410.2904}],
                    }
                ]
            },
        )

    with Session(engine) as db:
        provider = _provider(handler)
        first = sync_bcra_mayorista_historico(
            db, desde=date(2026, 5, 29), hasta=date(2026, 5, 31), provider=provider
        )
        db.commit()
        second = sync_bcra_mayorista_historico(
            db, desde=date(2026, 5, 29), hasta=date(2026, 5, 31), provider=provider
        )
        rows = (
            db.execute(
                text(
                    "SELECT moneda, tipo, tasa, origen FROM tipo_cambio_hist ORDER BY id"
                )
            )
            .mappings()
            .all()
        )

    assert first.insertados == 1
    assert second.insertados == 0
    assert len(rows) == 2
    assert rows[0]["moneda"] == "USD_MAY"
    assert rows[1]["moneda"] == "USD"
    assert rows[1]["tipo"] == "MAYORISTA"
    assert rows[1]["origen"] == "BCRA_A3500"
