from datetime import date
from decimal import Decimal
from typing import Literal, cast

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api import recepcion_api
from app.schemas.recepcion import (
    RecepcionCalidadCreate,
    RecepcionCotaCreate,
    RecepcionIntentoInspeccionCreate,
    RecepcionOperativaCreate,
)
from app.services.recepcion_operativa_service import (
    actualizar_recepcion_operativa,
    crear_recepcion_operativa,
    eliminar_recepcion_operativa,
    listar_lineas_pendientes_calidad,
    listar_recepciones_operativas,
    obtener_recepcion_operativa,
    registrar_control_calidad,
    registrar_intento_inspeccion,
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
            text("CREATE TABLE usuario (id INTEGER PRIMARY KEY, nombre TEXT)")
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
                recepcion_staging_id INTEGER,
                orden_compra TEXT, remito TEXT, fecha_recepcion DATE,
                fecha_entrega_esperada DATE, fecha_control DATE, estado TEXT,
                usuario_creacion_id INTEGER, usuario_inspeccion_id INTEGER,
                notas TEXT, terminacion_superficial NUMERIC,
                control_dimensional NUMERIC, embalaje NUMERIC,
                cantidad_lineas INTEGER, cantidad_aceptadas INTEGER,
                cantidad_rechazadas INTEGER,
                estado_embalaje TEXT
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
                letra_codigo_muestreo TEXT,
                porcentaje_muestreo NUMERIC, material_utilizado TEXT
            )
            """))
        connection.execute(text("""
            CREATE TABLE recepcion_inspeccion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recepcion_linea_id INTEGER, intento_id INTEGER, criterio_nombre TEXT,
                especificacion TEXT, valor_medido TEXT, desviacion TEXT,
                resultado TEXT, observaciones TEXT, inspector_id INTEGER,
                fecha_inspeccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
        connection.execute(text("""
            CREATE TABLE recepcion_inspeccion_intento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recepcion_linea_id INTEGER NOT NULL,
                numero_intento INTEGER NOT NULL,
                tipo_intento TEXT NOT NULL,
                intento_anterior_id INTEGER,
                nivel_inspeccion TEXT,
                tamano_muestra_planificado INTEGER,
                unidades_inspeccionadas INTEGER NOT NULL,
                unidades_no_conformes INTEGER NOT NULL,
                decision TEXT NOT NULL,
                referencia_normativa TEXT,
                inspector_id INTEGER,
                fecha_inspeccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (recepcion_linea_id, numero_intento)
            )
            """))
        connection.execute(text("""
            CREATE TABLE recepcion_no_conformidad (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recepcion_linea_id INTEGER NOT NULL,
                codigo_nc TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                estado_nc TEXT
            )
            """))
        connection.execute(
            text("INSERT INTO proveedor VALUES (1, 'P1', 'Proveedor Demo', 1)")
        )
        connection.execute(text("INSERT INTO usuario VALUES (7, 'Recepcionista Demo')"))
        connection.execute(text("INSERT INTO usuario VALUES (12, 'Inspector Demo')"))
        connection.execute(text("CREATE TABLE unidad_medida (id INTEGER PRIMARY KEY, codigo TEXT, nombre TEXT)"))
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
        cantidad_recibida=Decimal("3440"),
        cantidad_lote=Decimal("20"),
        estado_embalaje="CONFORME",
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
    payload = _payload().model_copy(
        update={"lote_numero": "3440", "cantidad_lote": None}
    )
    with _session() as db:
        result = crear_recepcion_operativa(db, payload, usuario_id=7)
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
        listed_by_plan = listar_recepciones_operativas(db, q="68")
        listed_by_provider = listar_recepciones_operativas(db, proveedor_codigo="P1")
        listed_by_other_provider = listar_recepciones_operativas(
            db, proveedor_codigo="P2"
        )
        detail = obtener_recepcion_operativa(db, result["id"])
        missing_detail = obtener_recepcion_operativa(db, 999)

    assert result["estado"] == "COMPLETA"
    assert header["orden_compra"] == "OC-123"
    assert header["estado_embalaje"] == "CONFORME"
    assert header["cantidad_aceptadas"] == 1
    assert line["numero_plano"] == "68"
    assert line["tamano_muestra"] == 32
    assert line["letra_codigo_muestreo"] == "J"
    assert Decimal(str(line["porcentaje_muestreo"])) == Decimal("0.930")
    assert len(inspections) == 2
    assert inspections[0]["desviacion"] == "-0.02 mm"
    assert len(listed) == 1
    assert len(listed_by_plan) == 1
    assert len(listed_by_provider) == 1
    assert listed_by_other_provider == []
    assert listed[0]["proveedor_codigo"] == "P1"
    assert detail is not None
    assert detail["proveedor_nombre"] == "Proveedor Demo"
    assert detail["usuario_recepcion_nombre"] == "Recepcionista Demo"
    assert detail["usuario_calidad_nombre"] == "Recepcionista Demo"
    assert detail["lineas"][0]["producto_codigo"] == "10INY0477"
    assert len(detail["lineas"][0]["cotas"]) == 2
    assert detail["lineas"][0]["intentos_inspeccion"] == []
    assert missing_detail is None


def test_lista_lineas_pendientes_calidad_solo_incluye_ingresos_sin_control():
    payload = _payload().model_copy(update={"cotas": []})
    with _session() as db:
        recepcion = crear_recepcion_operativa(db, payload, usuario_id=7)
        line = db.execute(text("SELECT * FROM recepcion_linea")).mappings().one()
        pending = listar_lineas_pendientes_calidad(db, q="OC-123")

    assert len(pending) == 1
    assert pending[0]["linea_id"] == line["id"]
    assert pending[0]["recepcion_id"] == recepcion["id"]
    assert pending[0]["producto_codigo"] == "10INY0477"
    assert pending[0]["cantidad_lote"] == Decimal("3440")
    assert pending[0]["tamano_muestra"] == 32
    assert pending[0]["letra_codigo_muestreo"] == "J"
    assert pending[0]["ultimo_intento_id"] is None


def test_muestreo_usa_cantidad_recibida_y_no_identificador_lote():
    payload = _payload().model_copy(
        update={
            "cantidad_recibida": Decimal("20"),
            "cantidad_lote": Decimal("3440"),
            "lote_numero": "LOTE-A",
            "cotas": [],
        }
    )

    with _session() as db:
        result = crear_recepcion_operativa(db, payload, usuario_id=7)
        line = db.execute(
            text("""
                  SELECT cantidad_solicitada, cantidad_recibida, cantidad_lote,
                       tamano_muestra, porcentaje_muestreo
                FROM recepcion_linea
                """)
        ).mappings().one()

    assert result["id"] > 0
    assert line["cantidad_solicitada"] == Decimal("20")
    assert line["cantidad_recibida"] == Decimal("20")
    assert line["cantidad_lote"] == Decimal("20")
    assert line["tamano_muestra"] == 2
    assert Decimal(str(line["porcentaje_muestreo"])) == Decimal("10.000")


def test_numero_lote_no_numerico_requiere_cantidad_legacy():
    from app.services.recepcion_operativa_service import _resolver_cantidad_lote

    with pytest.raises(
        ValueError, match="Número de lote debe ser una cantidad numérica"
    ):
        _resolver_cantidad_lote("LOTE-A", None)


def test_cota_no_conforme_rechaza_cabecera():
    with _session() as db:
        result = crear_recepcion_operativa(db, _payload("NO_CONFORME"), usuario_id=7)

    assert result["estado"] == "RECHAZADA"


def test_recepcion_y_control_calidad_guardan_usuarios_distintos():
    payload_recepcion = _payload().model_copy(update={"cotas": []})
    cotas_calidad = RecepcionCalidadCreate(
        cotas=[
            RecepcionCotaCreate(
                criterio_nombre="Dimensión",
                valor_medido="10 mm",
                resultado="OK",
            )
        ],
        terminacion_superficial=Decimal("98.5"),
        control_dimensional=Decimal("100"),
        embalaje=Decimal("90"),
    )
    with _session() as db:
        recepcion = crear_recepcion_operativa(db, payload_recepcion, usuario_id=7)
        inicial = db.execute(
            text("SELECT usuario_creacion_id, usuario_inspeccion_id FROM recepcion_cabecera WHERE id = :id"),
            {"id": recepcion["id"]},
        ).one()
        resultado = registrar_control_calidad(
            db, recepcion["id"], cotas_calidad, usuario_id=12
        )
        with pytest.raises(ValueError, match="ya fue registrado"):
            registrar_control_calidad(
                db, recepcion["id"], cotas_calidad, usuario_id=12
            )
        final = db.execute(
            text("SELECT usuario_creacion_id, usuario_inspeccion_id FROM recepcion_cabecera WHERE id = :id"),
            {"id": recepcion["id"]},
        ).one()
        inspector_cota = db.execute(
            text("SELECT inspector_id FROM recepcion_inspeccion")
        ).scalar_one()
        detail = obtener_recepcion_operativa(db, recepcion["id"])

    assert inicial == (7, None)
    assert final == (7, 12)
    assert inspector_cota == 12
    assert detail is not None
    assert detail["usuario_recepcion_nombre"] == "Recepcionista Demo"
    assert detail["usuario_calidad_nombre"] == "Inspector Demo"
    assert detail["fecha_control"] is not None
    assert detail["terminacion_superficial"] == Decimal("98.5")
    assert detail["control_dimensional"] == Decimal("100")
    assert detail["embalaje"] == Decimal("90")
    assert resultado == {"estado": "COMPLETA", "estado_inspeccion": "APROBADO"}


def test_actualizar_recepcion_local_actualiza_datos_y_cotas():
    with _session() as db:
        recepcion = crear_recepcion_operativa(db, _payload(), usuario_id=7)
        actualizado = _payload("NO_CONFORME").model_copy(
            update={"orden_compra": "OC-EDITADA", "remito": "R-EDITADO"}
        )

        result = actualizar_recepcion_operativa(
            db, recepcion["id"], actualizado, usuario_id=12
        )
        detalle = obtener_recepcion_operativa(db, recepcion["id"])

    assert result == {"id": recepcion["id"], "estado": "ACTUALIZADA"}
    assert detalle is not None
    assert detalle["orden_compra"] == "OC-EDITADA"
    assert detalle["remito"] == "R-EDITADO"
    assert detalle["estado"] == "RECHAZADA"
    assert detalle["lineas"][0]["estado_inspeccion"] == "RECHAZADO"
    assert detalle["lineas"][0]["cotas"][0]["resultado"] == "NO_CONFORME"
    assert detalle["lineas"][0]["cotas"][0]["inspector_id"] == 12


def test_edicion_y_borrado_bloqueados_para_recepcion_importada():
    with _session() as db:
        recepcion = crear_recepcion_operativa(
            db, _payload().model_copy(update={"cotas": []}), usuario_id=7
        )
        db.execute(
            text(
                "UPDATE recepcion_cabecera SET recepcion_staging_id = 42 WHERE id = :id"
            ),
            {"id": recepcion["id"]},
        )

        with pytest.raises(ValueError, match="históricas importadas"):
            actualizar_recepcion_operativa(
                db, recepcion["id"], _payload(), usuario_id=12
            )
        with pytest.raises(ValueError, match="históricas importadas"):
            eliminar_recepcion_operativa(db, recepcion["id"])


def test_eliminar_recepcion_local_y_bloquear_si_tiene_nc():
    with _session() as db:
        recepcion = crear_recepcion_operativa(db, _payload(), usuario_id=7)
        eliminar_recepcion_operativa(db, recepcion["id"])
        assert obtener_recepcion_operativa(db, recepcion["id"]) is None

        recepcion_con_nc = crear_recepcion_operativa(db, _payload(), usuario_id=7)
        linea_id = db.execute(
            text("SELECT id FROM recepcion_linea WHERE recepcion_cabecera_id = :id"),
            {"id": recepcion_con_nc["id"]},
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO recepcion_no_conformidad "
                "(recepcion_linea_id, codigo_nc, descripcion) "
                "VALUES (:linea_id, 'NC-1', 'Prueba')"
            ),
            {"linea_id": linea_id},
        )

        with pytest.raises(ValueError, match="no conformidades"):
            eliminar_recepcion_operativa(db, recepcion_con_nc["id"])


def test_control_calidad_no_conforme_guarda_inspector_y_rechazo():
    payload_recepcion = _payload().model_copy(update={"cotas": []})
    payload_calidad = RecepcionCalidadCreate(
        cotas=[
            RecepcionCotaCreate(
                criterio_nombre="Dimensión",
                valor_medido="Fuera de tolerancia",
                resultado="NO_CONFORME",
            )
        ]
    )
    with _session() as db:
        recepcion = crear_recepcion_operativa(db, payload_recepcion, usuario_id=7)
        resultado = registrar_control_calidad(
            db, recepcion["id"], payload_calidad, usuario_id=12
        )
        detalle = obtener_recepcion_operativa(db, recepcion["id"])

    assert resultado == {"estado": "RECHAZADA", "estado_inspeccion": "RECHAZADO"}
    assert detalle is not None
    assert detalle["usuario_recepcion_nombre"] == "Recepcionista Demo"
    assert detalle["usuario_calidad_nombre"] == "Inspector Demo"
    assert detalle["lineas"][0]["estado_inspeccion"] == "RECHAZADO"


def test_control_calidad_reemplaza_inspector_legacy_si_no_hay_cotas():
    payload_recepcion = _payload().model_copy(update={"cotas": []})
    payload_calidad = RecepcionCalidadCreate(
        cotas=[RecepcionCotaCreate(criterio_nombre="Dimensión", resultado="OK")]
    )
    with _session() as db:
        recepcion = crear_recepcion_operativa(db, payload_recepcion, usuario_id=7)
        db.execute(
            text("UPDATE recepcion_cabecera SET usuario_inspeccion_id = 7 WHERE id = :id"),
            {"id": recepcion["id"]},
        )

        resultado = registrar_control_calidad(
            db, recepcion["id"], payload_calidad, usuario_id=12
        )
        detalle = obtener_recepcion_operativa(db, recepcion["id"])

    assert resultado["estado"] == "COMPLETA"
    assert detalle is not None
    assert detalle["usuario_recepcion_nombre"] == "Recepcionista Demo"
    assert detalle["usuario_calidad_nombre"] == "Inspector Demo"


def test_endpoint_control_calidad_usa_usuario_autenticado(monkeypatch):
    calls = {}

    def fake_registrar(_db, recepcion_id, payload, *, usuario_id):
        calls.update(
            recepcion_id=recepcion_id,
            cotas=len(payload.cotas),
            usuario_id=usuario_id,
        )
        return {"estado": "COMPLETA"}

    monkeypatch.setattr(
        recepcion_api, "registrar_control_calidad", fake_registrar
    )
    payload = RecepcionCalidadCreate(
        cotas=[RecepcionCotaCreate(criterio_nombre="Medida", resultado="OK")]
    )

    result = recepcion_api.guardar_control_calidad(
        31, payload, db=object(), current_user={"id": 12}
    )

    assert calls == {"recepcion_id": 31, "cotas": 1, "usuario_id": 12}
    assert result == {"estado": "COMPLETA"}


def test_endpoint_intento_inspeccion_usa_usuario_autenticado(monkeypatch):
    calls = {}

    def fake_registrar(_db, linea_id, payload, *, usuario_id):
        calls.update(
            linea_id=linea_id,
            tipo=payload.tipo_intento,
            usuario_id=usuario_id,
        )
        return {"id": 41, "numero_intento": 1}

    monkeypatch.setattr(recepcion_api, "registrar_intento_inspeccion", fake_registrar)
    payload = RecepcionIntentoInspeccionCreate(
        tipo_intento="INICIAL",
        unidades_inspeccionadas=2,
        unidades_no_conformes=0,
        decision="ACEPTADO",
    )

    result = recepcion_api.guardar_intento_inspeccion(
        31, payload, db=object(), current_user={"id": 12}
    )

    assert calls == {"linea_id": 31, "tipo": "INICIAL", "usuario_id": 12}
    assert result == {"id": 41, "numero_intento": 1}


def test_endpoint_lista_lineas_pendientes_delega_filtros_y_limite(monkeypatch):
    calls = {}

    def fake_listar(_db, *, q, limit):
        calls.update(q=q, limit=limit)
        return [{"linea_id": 9}]

    monkeypatch.setattr(recepcion_api, "listar_lineas_pendientes_calidad", fake_listar)

    result = recepcion_api.listar_lineas_pendientes_control_calidad(
        q="OC-123", limit=45, db=object(), _current_user={}
    )

    assert calls == {"q": "OC-123", "limit": 45}
    assert result == [{"linea_id": 9}]


def test_no_crea_recepcion_si_proveedor_no_existe():
    payload = _payload().model_copy(update={"proveedor_id": 999})
    with _session() as db:
        with pytest.raises(ValueError, match="proveedor no existe"):
            crear_recepcion_operativa(db, payload, usuario_id=7)
        count = db.execute(text("SELECT COUNT(*) FROM recepcion_cabecera")).scalar_one()
        assert count == 0


def test_registra_inspeccion_inicial_y_reinspeccion_en_secuencia():
    with _session() as db:
        recepcion = crear_recepcion_operativa(
            db, _payload().model_copy(update={"cotas": []}), usuario_id=7
        )
        linea_id = db.execute(text("SELECT id FROM recepcion_linea")).scalar_one()
        inicial = registrar_intento_inspeccion(
            db,
            linea_id,
            RecepcionIntentoInspeccionCreate(
                tipo_intento="INICIAL",
                nivel_inspeccion="Simplificada",
                tamano_muestra_planificado=32,
                unidades_inspeccionadas=32,
                unidades_no_conformes=1,
                decision="RECHAZADO",
                referencia_normativa="Pendiente de validar por Calidad",
                cotas=[
                    RecepcionCotaCreate(
                        criterio_nombre="Visual",
                        resultado="NO_CONFORME",
                    )
                ],
            ),
            usuario_id=12,
        )
        reinspeccion = registrar_intento_inspeccion(
            db,
            linea_id,
            RecepcionIntentoInspeccionCreate(
                tipo_intento="REINSPECCION",
                intento_anterior_id=inicial["id"],
                nivel_inspeccion="Simplificada",
                tamano_muestra_planificado=32,
                unidades_inspeccionadas=4,
                unidades_no_conformes=0,
                decision="ACEPTADO",
            ),
            usuario_id=12,
        )
        detalle = obtener_recepcion_operativa(db, recepcion["id"])
        cota_intento_id = db.execute(
            text("SELECT intento_id FROM recepcion_inspeccion")
        ).scalar_one()
        estado_linea = db.execute(
            text("SELECT estado_inspeccion FROM recepcion_linea")
        ).scalar_one()
        estado_cabecera = db.execute(
            text("SELECT estado FROM recepcion_cabecera")
        ).scalar_one()

    assert inicial["numero_intento"] == 1
    assert reinspeccion["numero_intento"] == 2
    assert cota_intento_id == inicial["id"]
    assert estado_linea == "APROBADO"
    assert estado_cabecera == "COMPLETA"
    assert detalle is not None
    assert [
        intento["tipo_intento"]
        for intento in detalle["lineas"][0]["intentos_inspeccion"]
    ] == ["INICIAL", "REINSPECCION"]


def test_rechaza_reinspeccion_que_no_encadena_al_ultimo_intento():
    with _session() as db:
        crear_recepcion_operativa(
            db, _payload().model_copy(update={"cotas": []}), usuario_id=7
        )
        linea_id = db.execute(text("SELECT id FROM recepcion_linea")).scalar_one()
        payload = RecepcionIntentoInspeccionCreate(
            tipo_intento="REINSPECCION",
            intento_anterior_id=999,
            unidades_inspeccionadas=1,
            unidades_no_conformes=0,
            decision="PENDIENTE",
        )

        with pytest.raises(ValueError, match="más reciente"):
            registrar_intento_inspeccion(db, linea_id, payload, usuario_id=12)


def test_rechaza_mas_no_conformes_que_unidades_inspeccionadas():
    with _session() as db:
        crear_recepcion_operativa(
            db, _payload().model_copy(update={"cotas": []}), usuario_id=7
        )
        linea_id = db.execute(text("SELECT id FROM recepcion_linea")).scalar_one()
        payload = RecepcionIntentoInspeccionCreate(
            tipo_intento="INICIAL",
            nivel_inspeccion="Simplificada",
            tamano_muestra_planificado=32,
            unidades_inspeccionadas=2,
            unidades_no_conformes=3,
            decision="RECHAZADO",
        )

        with pytest.raises(ValueError, match="no conformes"):
            registrar_intento_inspeccion(db, linea_id, payload, usuario_id=12)


def test_rechaza_inspeccion_mayor_a_cantidad_recibida():
    with _session() as db:
        crear_recepcion_operativa(
            db,
            _payload().model_copy(
                update={
                    "cantidad_recibida": Decimal("20"),
                    "cantidad_lote": Decimal("20"),
                    "tamano_muestra": 2,
                    "cotas": [],
                }
            ),
            usuario_id=7,
        )
        linea_id = db.execute(text("SELECT id FROM recepcion_linea")).scalar_one()
        payload = RecepcionIntentoInspeccionCreate(
            tipo_intento="INICIAL",
            nivel_inspeccion="Simplificada",
            tamano_muestra_planificado=2,
            unidades_inspeccionadas=21,
            unidades_no_conformes=0,
            decision="PENDIENTE",
        )

        with pytest.raises(ValueError, match="cantidad recibida"):
            registrar_intento_inspeccion(db, linea_id, payload, usuario_id=12)


def test_no_permite_intento_sobre_recepcion_historica_importada():
    with _session() as db:
        recepcion = crear_recepcion_operativa(
            db, _payload().model_copy(update={"cotas": []}), usuario_id=7
        )
        linea_id = db.execute(text("SELECT id FROM recepcion_linea")).scalar_one()
        db.execute(
            text("UPDATE recepcion_cabecera SET recepcion_staging_id = 42 WHERE id = :id"),
            {"id": recepcion["id"]},
        )
        payload = RecepcionIntentoInspeccionCreate(
            tipo_intento="INICIAL",
            unidades_inspeccionadas=1,
            unidades_no_conformes=0,
            decision="PENDIENTE",
        )

        with pytest.raises(ValueError, match="históricas importadas"):
            registrar_intento_inspeccion(db, linea_id, payload, usuario_id=12)
