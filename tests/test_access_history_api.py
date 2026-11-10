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


def test_listar_recepciones_operativas_delega_en_servicio_local(monkeypatch):
    calls = {}

    def fake_listar(db, *, q, proveedor_codigo, limit):
        calls.update(db=db, q=q, proveedor_codigo=proveedor_codigo, limit=limit)
        return [{"id": 1001, "proveedor_codigo": "P-100"}]

    monkeypatch.setattr(recepcion_api, "listar_recepciones_operativas", fake_listar)

    result = recepcion_api.listar_recepciones(
        q="remito",
        proveedor_codigo="P-100",
        limit=25,
        db="session",
        _current_user={},
    )

    assert calls == {
        "db": "session",
        "q": "remito",
        "proveedor_codigo": "P-100",
        "limit": 25,
    }
    assert result == [{"id": 1001, "proveedor_codigo": "P-100"}]


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


def test_recomendacion_control_proveedor_delega_a_servicio(monkeypatch):
    expected = {"estado": "CALCULADO", "nivel_recomendado": "Normal"}
    calls = {}

    def fake_recomendar(db, proveedor_id):
        calls.update(db=db, proveedor_id=proveedor_id)
        return expected

    monkeypatch.setattr(recepcion_api, "recomendar_nivel_inspeccion", fake_recomendar)

    result = recepcion_api.obtener_recomendacion_control_proveedor(
        42, db="session", _current_user={}
    )

    assert calls == {"db": "session", "proveedor_id": 42}
    assert result == expected


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


def test_actualizar_recepcion_operativa_delega_en_servicio(monkeypatch):
    from app.schemas.recepcion import RecepcionOperativaCreate

    calls = {}
    expected = {"id": 23, "estado": "ACTUALIZADA"}

    def fake_actualizar(db, recepcion_id, payload, *, usuario_id):
        calls.update(
            db=db,
            recepcion_id=recepcion_id,
            payload=payload,
            usuario_id=usuario_id,
        )
        return expected

    monkeypatch.setattr(
        recepcion_api, "actualizar_recepcion_operativa", fake_actualizar
    )
    payload = RecepcionOperativaCreate(
        proveedor_id=1,
        producto_id=2,
        fecha_recepcion=date(2026, 10, 20),
        orden_compra="OC-23",
        cantidad_solicitada=10,
        cantidad_recibida=10,
        cantidad_lote=10,
        estado_embalaje="CONFORME",
    )

    result = recepcion_api.actualizar_recepcion(
        23, payload, db="session", current_user={"id": 9}
    )

    assert calls == {
        "db": "session",
        "recepcion_id": 23,
        "payload": payload,
        "usuario_id": 9,
    }
    assert result == expected


def test_borrar_recepcion_operativa_delega_en_servicio(monkeypatch):
    calls = {}

    def fake_eliminar(db, recepcion_id):
        calls.update(db=db, recepcion_id=recepcion_id)

    monkeypatch.setattr(recepcion_api, "eliminar_recepcion_operativa", fake_eliminar)

    result = recepcion_api.borrar_recepcion(23, db="session", _current_user={"id": 9})

    assert calls == {"db": "session", "recepcion_id": 23}
    assert result is None
