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
    assert result == [{"id": 42, "codigo": "ART-042", "nombre": "Artículo de prueba"}]


def test_buscar_articulos_incluye_codigo_de_unidad_si_esta_configurada(monkeypatch):
    class FakeResult:
        def __iter__(self):
            return iter([type("Unit", (), {"id": 3, "codigo": "KG"})()])

    class FakeDb:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    monkeypatch.setattr(
        recepcion_api,
        "listar_productos",
        lambda *_args, **_kwargs: [
            {
                "id": 42,
                "codigo": "ART-042",
                "nombre": "Artículo de prueba",
                "unidad_medida_id": 3,
            }
        ],
    )

    result = recepcion_api.buscar_articulos_recepcion(
        q="ART", db=FakeDb(), _current_user={}
    )

    assert result[0]["unidad_medida"] == "KG"
