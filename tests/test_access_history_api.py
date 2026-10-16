from datetime import date

from fastapi import HTTPException

from app.api import recepcion_api


def test_listar_controles_historicos_delega_filtros(monkeypatch):
    calls = {}

    def fake_listar(*, q, proveedor_codigo, desde, hasta, before_id, limit):
        calls.update(
            q=q,
            proveedor_codigo=proveedor_codigo,
            desde=desde,
            hasta=hasta,
            before_id=before_id,
            limit=limit,
        )
        return [{"ID_INT": 21485}]

    monkeypatch.setattr(recepcion_api, "listar_controles_access", fake_listar)

    result = recepcion_api.listar_controles_historicos_access(
        q="plano 476",
        proveedor_codigo="P-100",
        desde=date(2026, 10, 1),
        hasta=date(2026, 10, 31),
        before_id=22000,
        limit=25,
        _current_user={},
    )

    assert calls == {
        "q": "plano 476",
        "proveedor_codigo": "P-100",
        "desde": date(2026, 10, 1),
        "hasta": date(2026, 10, 31),
        "before_id": 22000,
        "limit": 25,
    }
    assert result == [{"ID_INT": 21485}]


def test_listar_recepciones_recientes_filtra_por_codigo_proveedor(monkeypatch):
    calls = {}

    def fake_listar(*, q, proveedor_codigo, limit):
        calls.update(q=q, proveedor_codigo=proveedor_codigo, limit=limit)
        return [{"ID_INT": 1001, "Codigo Proveedor": "P-100"}]

    monkeypatch.setattr(
        recepcion_api, "listar_recepciones_recientes_access", fake_listar
    )

    result = recepcion_api.listar_recepciones(
        q="remito", proveedor_codigo="P-100", limit=25, _current_user={}
    )

    assert calls == {"q": "remito", "proveedor_codigo": "P-100", "limit": 25}
    assert result == [{"ID_INT": 1001, "Codigo Proveedor": "P-100"}]


def test_detalle_control_historico_404_si_no_existe(monkeypatch):
    def fake_obtener(_access_id):
        return None

    monkeypatch.setattr(recepcion_api, "obtener_control_access", fake_obtener)

    try:
        recepcion_api.obtener_control_historico_access(999999, _current_user={})
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Se esperaba 404 para el ID Access inexistente")


def test_listar_controles_historicos_rechaza_rango_invertido(monkeypatch):
    def fake_listar(**_kwargs):
        raise ValueError("La fecha Desde no puede ser posterior a la fecha Hasta")

    monkeypatch.setattr(recepcion_api, "listar_controles_access", fake_listar)

    try:
        recepcion_api.listar_controles_historicos_access(
            desde=date(2026, 11, 1),
            hasta=date(2026, 10, 1),
            _current_user={},
        )
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("Se esperaba HTTP 422 para el rango invertido")
