from app.api import recepcion_api


def test_buscar_articulos_filtra_activos_y_devuelve_campos_minimos(monkeypatch):
    calls = {}

    def fake_listar_productos(_db, *, q, activo, limit, offset):
        calls.update(q=q, activo=activo, limit=limit, offset=offset)
        return [
            {
                "id": 42,
                "codigo": "ART-042",
                "nombre": "Artículo de prueba",
                "activo": True,
            }
        ]

    monkeypatch.setattr(recepcion_api, "listar_productos", fake_listar_productos)

    result = recepcion_api.buscar_articulos_recepcion(
        q="ART", db=object(), _current_user={}
    )

    assert calls == {"q": "ART", "activo": True, "limit": 10, "offset": 0}
    assert result == [
        {"id": 42, "codigo": "ART-042", "nombre": "Artículo de prueba"}
    ]
