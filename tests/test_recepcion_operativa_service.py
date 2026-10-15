from datetime import date
from decimal import Decimal
from typing import Literal, cast

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.schemas.recepcion import RecepcionCotaCreate, RecepcionOperativaCreate
from app.services.recepcion_operativa_service import (
    crear_recepcion_operativa,
    listar_recepciones_operativas,
    obtener_recepcion_operativa,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE proveedor (id INTEGER PRIMARY KEY, codigo TEXT, nombre TEXT, activo INTEGER)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE producto (id INTEGER PRIMARY KEY, codigo TEXT, "
                "nombre TEXT, unidad_medida_id INTEGER, activo INTEGER)"
            )
        )
        connection.execute(text("""
            CREATE TABLE recepcion_cabecera (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_recepcion TEXT UNIQUE, proveedor_id INTEGER,
                orden_compra TEXT, remito TEXT, fecha_recepcion DATE,
                fecha_entrega_esperada DATE, fecha_control DATE, estado TEXT,
                usuario_creacion_id INTEGER, usuario_inspeccion_id INTEGER,
                notas TEXT, terminacion_superficial NUMERIC,
                control_dimensional NUMERIC, embalaje NUMERIC,
                cantidad_lineas INTEGER, cantidad_aceptadas INTEGER,
                cantidad_rechazadas INTEGER
            )
            """))
        connection.execute(text("""
            CREATE TABLE recepcion_linea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recepcion_cabecera_id INTEGER, numero_linea INTEGER,
                producto_id INTEGER, numero_plano TEXT, designacion TEXT,
                cantidad_solicitada NUMERIC, cantidad_recibida NUMERIC,
                cantidad_lote NUMERIC, unidad_medida_id INTEGER,
                lote_numero TEXT, estado_inspeccion TEXT, observaciones TEXT,
                nivel_inspeccion TEXT, tamano_muestra INTEGER,
                porcentaje_muestreo NUMERIC, material_utilizado TEXT
            )
            """))
        connection.execute(text("""
            CREATE TABLE recepcion_inspeccion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recepcion_linea_id INTEGER, criterio_nombre TEXT,
                especificacion TEXT, valor_medido TEXT, desviacion TEXT,
                resultado TEXT, observaciones TEXT, inspector_id INTEGER,
                fecha_inspeccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
        connection.execute(
            text("INSERT INTO proveedor VALUES (1, 'P1', 'Proveedor Demo', 1)")
        )
        connection.execute(
            text("INSERT INTO producto VALUES (2, '10INY0477', 'Artículo demo', 3, 1)")
        )
    return Session(engine)


def _payload(
    resultado: Literal["OK", "NO_CONFORME", "PENDIENTE", "NO_APLICA"] = "OK",
) -> RecepcionOperativaCreate:
    return RecepcionOperativaCreate(
        proveedor_id=1,
        producto_id=2,
        fecha_recepcion=date(2026, 10, 15),
        fecha_control=date(2026, 10, 15),
        orden_compra="OC-123",
        remito="R-456",
        cantidad_solicitada=Decimal("20"),
        cantidad_recibida=Decimal("20"),
        cantidad_lote=Decimal("3440"),
        numero_plano="68",
        designacion="Caño ingreso de agua",
        nivel_inspeccion="Simplificada",
        tamano_muestra=32,
        porcentaje_muestreo=Decimal("0.93"),
        cotas=[
            RecepcionCotaCreate(
                criterio_nombre="Espesor caño",
                especificacion="1.65 mm ± 0.2 mm",
                valor_medido="1.63 mm",
                desviacion="-0.02 mm",
                resultado=cast(
                    Literal["OK", "NO_CONFORME", "PENDIENTE", "NO_APLICA"],
                    resultado,
                ),
            ),
            RecepcionCotaCreate(
                criterio_nombre="Control funcional",
                valor_medido="OK",
                resultado="OK",
            ),
        ],
    )


def test_crear_recepcion_guarda_datos_y_cotas_y_lista():
    with _session() as db:
        result = crear_recepcion_operativa(db, _payload(), usuario_id=7)
        db.commit()

        header = (
            db.execute(
                text("SELECT * FROM recepcion_cabecera WHERE id = :id"),
                {"id": result["id"]},
            )
            .mappings()
            .one()
        )
        line = db.execute(text("SELECT * FROM recepcion_linea")).mappings().one()
        inspections = (
            db.execute(text("SELECT * FROM recepcion_inspeccion")).mappings().all()
        )
        listed = listar_recepciones_operativas(db, q="OC-123")
        listed_by_plan = listar_recepciones_operativas(db, q="0477")
        detail = obtener_recepcion_operativa(db, result["id"])
        missing_detail = obtener_recepcion_operativa(db, 999)

    assert result["estado"] == "COMPLETA"
    assert header["orden_compra"] == "OC-123"
    assert header["cantidad_aceptadas"] == 1
    assert line["numero_plano"] == "0477"
    assert line["tamano_muestra"] == 32
    assert len(inspections) == 2
    assert inspections[0]["desviacion"] == "-0.02 mm"
    assert len(listed) == 1
    assert len(listed_by_plan) == 1
    assert detail is not None
    assert detail["proveedor_nombre"] == "Proveedor Demo"
    assert detail["lineas"][0]["producto_codigo"] == "10INY0477"
    assert len(detail["lineas"][0]["cotas"]) == 2
    assert missing_detail is None


def test_cota_no_conforme_rechaza_cabecera():
    with _session() as db:
        result = crear_recepcion_operativa(db, _payload("NO_CONFORME"), usuario_id=7)

    assert result["estado"] == "RECHAZADA"


def test_no_crea_recepcion_si_proveedor_no_existe():
    payload = _payload().model_copy(update={"proveedor_id": 999})
    with _session() as db:
        with pytest.raises(ValueError, match="proveedor no existe"):
            crear_recepcion_operativa(db, payload, usuario_id=7)
        count = db.execute(text("SELECT COUNT(*) FROM recepcion_cabecera")).scalar_one()
        assert count == 0
