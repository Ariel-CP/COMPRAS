from sqlalchemy.exc import SQLAlchemyError

from app.services import access_read_service as service
from app.services import articulo_plano_service as planos_service


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_historial_reutiliza_asociaciones_y_conserva_observaciones(monkeypatch):
    asociaciones = [
        {
            "articulo_codigo": "10INY0539",
            "articulo_nombre": "Inyector",
            "descripcion": "Detalle",
        },
        {
            "articulo_codigo": "WIP-0539",
            "articulo_nombre": "Otro inyector",
            "descripcion": None,
        },
    ]
    monkeypatch.setattr(service, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        service,
        "obtener_asociaciones_por_plano",
        lambda db, numeros: {"0539": asociaciones},
    )
    rows = [{"PLANO": 539, "NOTA": "Observacion"}, {"PLANO": 99999}]
    service._agregar_nombres_articulos(rows)
    assert rows[0]["articulo_asociaciones"] == asociaciones
    assert rows[0]["articulo_codigo"] == "10INY0539, WIP-0539"
    assert rows[0]["articulo_nombre"] == "Inyector, Otro inyector"
    assert rows[0]["NOTA"] == "Observacion"
    assert rows[1]["articulo_asociaciones"] == []
    assert rows[1]["articulo_nombre"] is None


def test_asociaciones_por_plano_no_duplica_revisiones(monkeypatch):
    asociaciones = [{"articulo_codigo": "10INY0539", "articulo_nombre": "Inyector"}]
    monkeypatch.setattr(
        planos_service,
        "listar_articulos_con_planos",
        lambda db: [
            {"numero_base": "0539", "revision": "A", "asociaciones": asociaciones},
            {"numero_base": "0539", "revision": "B", "asociaciones": asociaciones},
            {
                "numero_base": "1006",
                "asociaciones": [{"articulo_nombre": "Otro articulo"}],
            },
        ],
    )
    result = planos_service.obtener_asociaciones_por_plano(
        FakeSession(), ["539", "0539", "10006"]
    )
    assert result == {"0539": asociaciones}


def test_catalogo_no_disponible_conserva_historial(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", FakeSession)

    def missing(db, numeros):
        raise SQLAlchemyError("No disponible")

    monkeypatch.setattr(service, "obtener_asociaciones_por_plano", missing)
    rows = [{"PLANO": 539, "NOTA": "Observacion"}]
    service._agregar_nombres_articulos(rows)
    assert rows[0]["NOTA"] == "Observacion"
    assert rows[0]["articulo_nombre"] is None


def test_historial_no_inventa_asociacion_para_plano_fuera_del_listado(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        service, "obtener_asociaciones_por_plano", lambda db, numeros: {}
    )
    rows = [{"ID_INT": 21548, "PLANO": 10006}]
    service._agregar_nombres_articulos(rows)
    assert rows[0]["articulo_asociaciones"] == []
    assert rows[0]["articulo_codigo"] is None
    assert rows[0]["articulo_nombre"] is None


def test_historial_coincide_con_listado_real_de_planos(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://")

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def adapt_current_date(conn, cursor, statement, parameters, context, executemany):
        return statement.replace("CURRENT_DATE()", "CURRENT_DATE"), parameters

    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        db.execute(
            text(
                "CREATE TABLE producto (id INTEGER, codigo TEXT, nombre TEXT, tipo_producto TEXT, activo INTEGER DEFAULT 1)"
            )
        )
        db.execute(
            text("CREATE TABLE recepcion_linea (producto_id INTEGER, designacion TEXT)")
        )
        db.execute(
            text(
                "CREATE TABLE mbom_cabecera (id INTEGER, producto_padre_id INTEGER, estado TEXT, vigencia_desde DATE, vigencia_hasta DATE)"
            )
        )
        db.execute(
            text(
                "CREATE TABLE mbom_detalle (mbom_id INTEGER, componente_producto_id INTEGER)"
            )
        )
        db.execute(
            text(
                "INSERT INTO producto (id, codigo, nombre, tipo_producto) VALUES (1, '10INY0539', 'Inyector', 'MP'), (2, 'WIP0539', 'Pieza', 'WIP')"
            )
        )
        db.execute(
            text("INSERT INTO recepcion_linea VALUES (1, 'Detalle del inyector')")
        )
        db.commit()
    monkeypatch.setattr(service, "SessionLocal", session_factory)
    monkeypatch.setattr(
        planos_service,
        "catalogar_planos_pdf",
        lambda directorio: {
            "0539": {"A": tmp_path / "0539-A.pdf", "B": tmp_path / "0539-B.pdf"}
        },
    )
    with session_factory() as db:
        listado = planos_service.listar_articulos_con_planos(db)
    rows = [{"PLANO": 539}, {"PLANO": "0539"}, {"PLANO": 10006}]
    service._agregar_nombres_articulos(rows)
    for row in rows[:2]:
        assert row["articulo_asociaciones"] == listado[0]["asociaciones"]
        assert row["articulo_codigo"] == ", ".join(listado[0]["codigos_articulo"])
        assert row["articulo_nombre"] == ", ".join(listado[0]["nombres_articulo"])
    assert rows[2]["articulo_asociaciones"] == []
    engine.dispose()
