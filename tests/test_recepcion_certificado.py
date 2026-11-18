import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps_auth import get_current_user
from app.api.recepcion_api import router
from app.db import get_db
from app.services import recepcion_certificado_service as service

PDF = b"%PDF-1.4\ncertificado de prueba\n%%EOF"
URL = "/api/recepcion/calidad/lineas/11/certificado"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        for sql in [
            "CREATE TABLE usuario (id INTEGER PRIMARY KEY, nombre TEXT)",
            "CREATE TABLE recepcion_cabecera (id INTEGER PRIMARY KEY, recepcion_staging_id INTEGER)",
            "CREATE TABLE recepcion_linea (id INTEGER PRIMARY KEY, recepcion_cabecera_id INTEGER)",
            "CREATE TABLE recepcion_certificado_calidad (recepcion_linea_id INTEGER PRIMARY KEY, recibido INTEGER, usuario_id INTEGER, fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE recepcion_certificado_documento (id INTEGER PRIMARY KEY AUTOINCREMENT, recepcion_linea_id INTEGER, nombre TEXT, tipo_mime TEXT, tamano INTEGER, sha256 TEXT, contenido BLOB, usuario_id INTEGER, fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(recepcion_linea_id, sha256))",
            "INSERT INTO usuario VALUES (7, 'Inspectora')",
            "INSERT INTO recepcion_cabecera VALUES (1, NULL), (2, 99), (3, NULL)",
            "INSERT INTO recepcion_linea VALUES (11, 1), (22, 2), (33, 3)",
        ]:
            connection.execute(text(sql))
    with Session(engine) as session:
        yield session
    engine.dispose()


def client(db, permissions=None):
    app = FastAPI()
    app.include_router(router, prefix="/api")

    def transaction():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = transaction
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 7,
        "roles": [],
        "permissions": (
            permissions
            if permissions is not None
            else {"ui_recepcion_calidad": (True, True)}
        ),
    }
    return TestClient(app)


def test_tilde_sin_archivo_persiste_y_puede_corregirse(db):
    api = client(db)
    assert api.get(URL).json()["recibido"] is False
    response = api.put(URL, data={"recibido": "true"})
    assert response.status_code == 200
    assert response.json()["usuario_nombre"] == "Inspectora"
    assert api.get(URL).json()["recibido"] is True
    assert api.put(URL, data={"recibido": "false"}).json()["recibido"] is False


def test_adjunto_marca_recibido_descarga_exacta_y_reintento_no_duplica(db):
    api = client(db)
    for _ in range(2):
        response = api.put(
            URL,
            data={"recibido": "false"},
            files={"archivo": ("calidad.pdf", PDF, "application/pdf")},
        )
        assert response.status_code == 200
    data = response.json()
    assert data["recibido"] is True
    assert len(data["documentos"]) == 1
    document = data["documentos"][0]
    assert "contenido" not in document
    assert document["sha256"] == hashlib.sha256(PDF).hexdigest()
    downloaded = api.get(URL + f"/documentos/{document['id']}")
    assert downloaded.content == PDF
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert api.put(URL, data={"recibido": "false"}).status_code == 400
    assert api.get(URL).json()["recibido"] is True


def test_nuevo_documento_conserva_el_anterior_y_no_se_descarga_en_otra_linea(db):
    service.guardar_certificado(
        db, 11, recibido=True, usuario_id=7, nombre="a.pdf", contenido=PDF
    )
    state = service.guardar_certificado(
        db, 11, recibido=True, usuario_id=7, nombre="b.pdf", contenido=PDF + b"2"
    )
    assert len(state["documentos"]) == 2
    assert (
        service.obtener_documento(db, 11, state["documentos"][0]["id"])["contenido"]
        == PDF
    )
    with pytest.raises(LookupError):
        service.obtener_documento(db, 33, state["documentos"][0]["id"])


@pytest.mark.parametrize(
    "name,content",
    [
        ("a.pdf", b""),
        ("a.pdf", b"<html>no es PDF</html>"),
        ("a.exe", PDF),
        ("a.svg", b"<svg/>"),
        ("a.pdf", b"%PDF-" + b"0" * service.MAX_ARCHIVO_BYTES),
    ],
    ids=["vacio", "contenido-invalido", "extension-ejecutable", "svg", "mayor-10mb"],
)
def test_archivo_invalido_no_guarda_tilde_ni_documento(db, name, content):
    response = client(db).put(
        URL, data={"recibido": "true"}, files={"archivo": (name, content)}
    )
    assert response.status_code == 400
    assert (
        db.execute(text("SELECT COUNT(*) FROM recepcion_certificado_calidad")).scalar()
        == 0
    )
    assert (
        db.execute(
            text("SELECT COUNT(*) FROM recepcion_certificado_documento")
        ).scalar()
        == 0
    )


@pytest.mark.parametrize(
    "nombre,contenido,mime",
    [
        ("C:\\fakepath\\calidad.pdf", PDF, "application/pdf"),
        ("../foto.JPG", b"\xff\xd8\xfffoto", "image/jpeg"),
        ("foto.png", b"\x89PNG\r\n\x1a\nimagen", "image/png"),
    ],
)
def test_formatos_y_nombre_seguro(nombre, contenido, mime):
    limpio, tipo = service.validar_documento(nombre, contenido)
    assert tipo == mime and "/" not in limpio and "\\" not in limpio


def test_historicos_solo_lectura_e_id_inexistente(db):
    api = client(db)
    assert (
        api.put(URL.replace("/11/", "/22/"), data={"recibido": "true"}).status_code
        == 400
    )
    assert api.get(URL.replace("/11/", "/999/")).status_code == 404


def test_lectura_no_autoriza_carga_y_otra_pantalla_no_autoriza_lectura(db):
    api = client(db, {"ui_recepcion_calidad": (True, False)})
    assert api.get(URL).status_code == 200
    assert api.put(URL, data={"recibido": "true"}).status_code == 403
    api = client(db, {"ui_recepcion": (True, True)})
    assert api.get(URL).status_code == 403


def test_certificado_impide_borrar_o_reasignar_recepcion(db):
    service.guardar_certificado(db, 11, recibido=True, usuario_id=7)
    with pytest.raises(ValueError, match="certificados registrados"):
        service.proteger_recepcion_con_certificados(db, 1)
    service.proteger_recepcion_con_certificados(db, 3)


def test_rollback_revierte_archivo_y_estado_juntos(db):
    service.guardar_certificado(
        db, 11, recibido=True, usuario_id=7, nombre="a.pdf", contenido=PDF
    )
    db.rollback()
    state = service.obtener_certificado(db, 11)
    assert state["recibido"] is False and not state["documentos"]
