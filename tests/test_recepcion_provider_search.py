from app.api import recepcion_api


def test_buscar_proveedores_filtra_activos_y_devuelve_campos_minimos(monkeypatch):
    calls = {}

    def fake_listar_proveedores(_db, *, q, activo, limit, offset):
        calls.update(q=q, activo=activo, limit=limit, offset=offset)
        return [
            {
                "id": 17,
                "codigo": "P-017",
                "nombre": "Proveedor de prueba",
                "email": "contacto@example.invalid",
            }
        ]

    monkeypatch.setattr(recepcion_api, "listar_proveedores", fake_listar_proveedores)

    result = recepcion_api.buscar_proveedores_recepcion(
        q="P-01", db=object(), _current_user={}
    )

    assert calls == {"q": "P-01", "activo": True, "limit": 10, "offset": 0}
    assert result == [{"id": 17, "codigo": "P-017", "nombre": "Proveedor de prueba"}]
