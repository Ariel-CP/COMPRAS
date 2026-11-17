import io
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import deps_auth as auth, wizard_excel as api
from app.services import wizard_excel_service as service

BASE = "/api/plan-produccion-mensual/asistente-oc/archivo-integral"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def mysql_syntax_for_sqlite(
        conn, cursor, statement, parameters, context, executemany
    ):
        # Ejecutar transacciones reales en SQLite sin agregar otro dialecto al producto.
        statement = statement.removesuffix(" FOR UPDATE")
        statement = statement.replace(
            "ON DUPLICATE KEY UPDATE", "ON CONFLICT(anio,mes,producto_id) DO UPDATE SET"
        )
        statement = re.sub(r"VALUES\((\w+)\)", r"excluded.\1", statement)

        def adapt(values):
            return tuple(str(v) if isinstance(v, Decimal) else v for v in values)

        return statement, (
            [adapt(row) for row in parameters] if executemany else adapt(parameters)
        )

    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE unidad_medida(id INTEGER PRIMARY KEY, codigo TEXT)")
        )
        conn.execute(
            text(
                "CREATE TABLE producto(id INTEGER PRIMARY KEY, codigo TEXT, nombre TEXT, tipo_producto TEXT, rubro TEXT, unidad_medida_id INTEGER, activo INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO unidad_medida VALUES(1,'UN')"))
        conn.execute(
            text(
                "INSERT INTO producto VALUES(1,'0001','Producto','PT','',1,1),(2,'MP-LAF','Chapa','MP','LAF',1,1),(3,'MP-OTRA','Material','MP','',1,1)"
            )
        )
        for table, quantity in [
            ("plan_produccion_mensual", "cantidad_planificada"),
            ("stock_disponible_mes", "stock_disponible"),
            ("asistente_oc_stock_pt_mes", "stock_pt"),
            ("asistente_oc_deuda_cliente_mes", "deuda_clientes"),
        ]:
            conn.execute(
                text(
                    f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, anio INTEGER, mes INTEGER, producto_id INTEGER, {quantity} NUMERIC, fecha_corte DATE, origen TEXT, UNIQUE(anio,mes,producto_id))"
                )
            )
        conn.execute(
            text(
                "CREATE TABLE asistente_oc_laf_solicitado(id INTEGER PRIMARY KEY, anio INTEGER, mes INTEGER, producto_id INTEGER, proveedor_nombre TEXT, cantidad_total NUMERIC, cantidad_q1 NUMERIC, cantidad_q2 NUMERIC, fecha_pedido DATE, fecha_entrega_estimada DATE, estado TEXT, observaciones TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO plan_produccion_mensual(anio,mes,producto_id,cantidad_planificada) VALUES(2026,5,1,7)"
            )
        )
    session = Session(engine)
    monkeypatch.setattr(
        service,
        "calcular_asistente_oc",
        lambda db, mes, anio, persistir_sugerencias: {
            "resumen": {"mes": mes, "anio": anio},
            "sugerencias": {"persistir": persistir_sugerencias},
        },
    )
    yield session
    session.close()
    engine.dispose()


def workbook_bytes(db, laf=False):
    wb = load_workbook(io.BytesIO(service.template(db, 2026, 5)))
    wb["Parametros"]["D2"] = date(2026, 4, 30)
    wb["Parametros"]["E2"] = date(2026, 5, 1)
    wb["Parametros"]["F2"] = date(2026, 5, 1)
    wb["Parametros"]["G2"] = "NO" if laf else "SI"
    for sheet in service.QUANTITIES:
        ws = wb[sheet]
        for row in range(2, ws.max_row + 1):
            if ws.cell(row, 1).value is not None:
                ws.cell(row, 4, 10 if sheet == "Plan_PT" else 0)
    if laf:
        values = [
            "MP-LAF",
            "Chapa",
            "UN",
            "Proveedor de prueba",
            4,
            2,
            2,
            date(2026, 4, 1),
            date(2026, 5, 20),
            "PENDIENTE",
            "",
        ]
        for c, v in enumerate(values, 1):
            wb["LAF_Solicitado"].cell(2, c, v)
    return wb


def content(wb):
    stream = io.BytesIO()
    wb.save(stream)
    wb.close()
    return stream.getvalue()


def test_plantilla_tiene_todas_las_hojas_codigos_texto_y_no_inventa_ceros(db):
    wb = load_workbook(io.BytesIO(service.template(db, 2026, 5)))
    assert set(service.HEADERS).issubset(wb.sheetnames)
    assert wb["Plan_PT"]["A2"].value == "0001"
    assert wb["Plan_PT"]["A2"].data_type == "s"
    assert wb["Plan_PT"]["D2"].value == 7
    assert wb["Stock_PT"]["D2"].value is None
    assert wb["Plan_PT"].freeze_panes == "A2"
    wb.close()


@pytest.mark.parametrize(
    "sheet,cell,value",
    [
        ("Plan_PT", "D2", None),
        ("Stock_PT", "D2", -1),
        ("Stock_PT", "D2", 0.0000001),
        ("Stock_PT", "D2", "12"),
        ("Stock_PT", "D2", "=1+2"),
        ("Plan_PT", "A2", 1),
        ("Stock_MP", "A2", "DESCONOCIDO"),
        ("Stock_PT", "C2", "KG"),
        ("Parametros", "G2", "NO"),
        ("Parametros", "D2", date(2026, 5, 1)),
        ("Parametros", "B2", 2026.5),
        ("Plan_PT", "D2", 10**12),
    ],
)
def test_errores_se_reportan_sin_guardar(db, sheet, cell, value):
    wb = workbook_bytes(db)
    wb[sheet][cell] = value
    report, batch = service.validate(content(wb), service.catalog(db))
    assert not report["valido"] and report["errores"] and batch is None
    assert (
        db.execute(
            text("SELECT cantidad_planificada FROM plan_produccion_mensual")
        ).scalar_one()
        == 7
    )


def test_codigos_duplicados_y_cobertura_incompleta(db):
    wb = workbook_bytes(db)
    for c in range(1, 5):
        wb["Stock_MP"].cell(3, c, wb["Stock_MP"].cell(2, c).value)
    report, _ = service.validate(content(wb), service.catalog(db))
    assert any("duplicado" in e["mensaje"] for e in report["errores"])
    assert any("Faltan" in e["mensaje"] for e in report["errores"])


def test_laf_varios_pedidos_por_codigo_y_cantidades_validas(db):
    wb = workbook_bytes(db, laf=True)
    for c in range(1, 12):
        wb["LAF_Solicitado"].cell(3, c, wb["LAF_Solicitado"].cell(2, c).value)
    wb["LAF_Solicitado"]["D3"] = "Otro proveedor"
    report, batch = service.validate(content(wb), service.catalog(db))
    assert report["valido"] and len(batch["listas"]["LAF_Solicitado"]) == 2


@pytest.mark.parametrize(
    "cell,value",
    [
        ("F2", 5),
        ("A2", "MP-OTRA"),
        ("D2", "x" * 161),
        ("K2", "x" * 256),
        ("J2", "OTRO"),
    ],
)
def test_laf_respeta_tipo_longitudes_y_quincenas(db, cell, value):
    wb = workbook_bytes(db, laf=True)
    wb["LAF_Solicitado"][cell] = value
    assert not service.validate(content(wb), service.catalog(db))[0]["valido"]


def test_importacion_unica_guarda_todas_las_hojas_y_calcula_sin_persistir(
    db, monkeypatch
):
    data = content(workbook_bytes(db, laf=True))
    preview = service.preview(db, data, 7)

    def calculate(db, mes, anio, persistir_sugerencias):
        assert persistir_sugerencias is False
        assert (
            db.execute(
                text("SELECT cantidad_planificada FROM plan_produccion_mensual")
            ).scalar_one()
            == 10
        )
        assert (
            db.execute(
                text("SELECT COUNT(*) FROM asistente_oc_laf_solicitado")
            ).scalar_one()
            == 1
        )
        return {"sugerencias": {"persistir": False}}

    monkeypatch.setattr(service, "calcular_asistente_oc", calculate)
    result = service.import_and_calculate(db, data, preview["token"], 7)
    assert result["calculo"]["sugerencias"]["persistir"] is False
    assert (
        db.execute(text("SELECT mes FROM stock_disponible_mes LIMIT 1")).scalar_one()
        == 4
    )
    # Nueva validación y reimportación: la lista LAF no se duplica.
    preview = service.preview(db, data, 7)
    service.import_and_calculate(db, data, preview["token"], 7)
    assert (
        db.execute(
            text("SELECT COUNT(*) FROM asistente_oc_laf_solicitado")
        ).scalar_one()
        == 1
    )


def test_fallo_al_calcular_revierte_todas_las_escrituras(db, monkeypatch):
    data = content(workbook_bytes(db, laf=True))
    preview = service.preview(db, data, 7)

    def fail(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(service, "calcular_asistente_oc", fail)
    with pytest.raises(RuntimeError):
        service.import_and_calculate(db, data, preview["token"], 7)
    assert (
        db.execute(
            text("SELECT cantidad_planificada FROM plan_produccion_mensual")
        ).scalar_one()
        == 7
    )
    for table in list(service.TABLES.values())[1:]:
        assert db.execute(text("SELECT COUNT(*) FROM " + table)).scalar_one() == 0


def test_preview_vinculada_a_archivo_usuario_datos_y_vencimiento(db):
    data = content(workbook_bytes(db))
    preview = service.preview(db, data, 7)
    with pytest.raises(service.PreviewExpired):
        service.import_and_calculate(db, data, preview["token"], 8)
    with pytest.raises(service.PreviewExpired):
        service.import_and_calculate(db, data + b"x", preview["token"], 7)
    claims = jwt.decode(
        preview["token"], service.get_settings().auth_secret_key, algorithms=["HS256"]
    )
    claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired = jwt.encode(
        claims, service.get_settings().auth_secret_key, algorithm="HS256"
    )
    with pytest.raises(service.PreviewExpired):
        service.import_and_calculate(db, data, expired, 7)
    db.execute(text("UPDATE plan_produccion_mensual SET cantidad_planificada=8"))
    db.commit()
    with pytest.raises(service.PreviewExpired):
        service.import_and_calculate(db, data, preview["token"], 7)
    assert (
        db.execute(
            text("SELECT cantidad_planificada FROM plan_produccion_mensual")
        ).scalar_one()
        == 8
    )


def test_no_acepta_archivo_invalido_y_enero_usa_diciembre():
    with pytest.raises(service.WorkbookError):
        service._open(b"no es un zip")
    assert service.previous_period(2026, 1) == (2025, 12)


@pytest.mark.parametrize("change", ["hoja", "encabezado", "duplicado_laf"])
def test_estructura_y_pedidos_identicos_duplicados(db, change):
    wb = workbook_bytes(db, laf=True)
    if change == "hoja":
        del wb["Stock_PT"]
    elif change == "encabezado":
        wb["Plan_PT"]["D1"] = "otro_encabezado"
    else:
        for column in range(1, 12):
            wb["LAF_Solicitado"].cell(
                3, column, wb["LAF_Solicitado"].cell(2, column).value
            )
    report, batch = service.validate(content(wb), service.catalog(db))
    assert not report["valido"] and batch is None


def test_rollback_conserva_pedidos_laf_previos(db, monkeypatch):
    first = content(workbook_bytes(db, laf=True))
    p = service.preview(db, first, 7)
    service.import_and_calculate(db, first, p["token"], 7)
    original = service._snapshot(db, 2026, 5)
    wb = workbook_bytes(db, laf=False)
    for row in range(2, wb["LAF_Solicitado"].max_row + 1):
        for column in range(1, 12):
            wb["LAF_Solicitado"].cell(row, column).value = None
    data = content(wb)
    p = service.preview(db, data, 7)
    assert p["valido"] and p["existentes"]["LAF_Solicitado"] == 1

    def fail(*args, **kwargs):
        raise RuntimeError("fallo al final de la operación")

    monkeypatch.setattr(service, "calcular_asistente_oc", fail)
    with pytest.raises(RuntimeError):
        service.import_and_calculate(db, data, p["token"], 7)
    assert service._snapshot(db, 2026, 5) == original


def client_for(db, user):
    app = FastAPI()
    app.include_router(
        api.router,
        prefix="/api",
        dependencies=[Depends(auth.require_api_screen_permission)],
    )
    app.dependency_overrides[api.get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: user
    app.dependency_overrides[auth.get_current_user_optional] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize(
    "user,status",
    [(None, 401), ({"permissions": {"ui_plan_mensual": (True, True)}}, 403)],
)
def test_api_requiere_sesion_y_pantalla(db, user, status):
    with client_for(db, user) as client:
        assert (
            client.get(BASE + "/plantilla.xlsx?anio=2026&mes=5").status_code == status
        )
        assert (
            client.post(
                BASE + "/validar", files={"archivo": ("carga.xlsx", b"x")}
            ).status_code
            == status
        )


@pytest.mark.parametrize(
    "wizard_write,monthly_write,expected",
    [(False, False, 403), (True, False, 403), (True, True, 200)],
)
def test_lector_puede_validar_pero_carga_exige_ambos_permisos(
    db, wizard_write, monthly_write, expected
):
    user = {
        "id": 7,
        "permissions": {
            "ui_plan_asistente_oc": (True, wizard_write),
            "ui_plan_mensual": (True, monthly_write),
        },
    }
    data = content(workbook_bytes(db))
    files = {"archivo": ("carga.xlsx", data)}
    with client_for(db, user) as client:
        p = client.post(BASE + "/validar", files=files)
        assert p.status_code == 200 and p.json()["valido"]
        result = client.post(
            BASE + "/importar",
            files=files,
            data={"token": p.json()["token"], "confirmar": "true"},
        )
        assert result.status_code == expected


def test_origen_externo_y_confirmacion_falsa_se_rechazan(db):
    user = {"id": 7, "roles": ["admin"]}
    data = content(workbook_bytes(db))
    files = {"archivo": ("carga.xlsx", data)}
    with client_for(db, user) as client:
        assert (
            client.post(
                BASE + "/validar",
                files=files,
                headers={"Origin": "https://otro.invalid"},
            ).status_code
            == 403
        )
        p = client.post(BASE + "/validar", files=files).json()
        assert (
            client.post(
                BASE + "/importar",
                files=files,
                data={"token": p["token"], "confirmar": "false"},
            ).status_code
            == 400
        )
