from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services import evaluacion_preview_service as service


def fila(**cambios):
    return {
        "Id": 1,
        "Codigo": "001",
        "Razon_Social": "Prueba",
        "Fecha": datetime(2024, 1, 1),
        "P_CAL": 25,
        "P_SER": 40,
        "P_EMB": 5,
        "Calif_Total": 70,
        "CALIFICACION": "APROBADO",
        "Cal_Cum_Esp": "Excelente",
        "PV_Cumplimiento de specificaciones": 5,
        **cambios,
    }


def test_preserva_respuesta_y_valor_sin_convertir_respuesta_textual_a_puntos():
    r = service.conciliar_fila(fila())
    assert r["criterios"][0]["respuesta"] == "Excelente"
    assert r["criterios"][0]["valor"] == Decimal(5)
    assert r["total_calculado"] == 70
    assert r["conciliado"]


def test_discrepancia_no_sobrescribe_total_ni_resultado_original():
    r = service.conciliar_fila(fila(Calif_Total=54, CALIFICACION="NO APTO"))
    assert r["total_origen"] == 54
    assert r["resultado_origen"] == "NO APTO"
    assert r["resultado_por_suma"] == "APROBADO"
    assert not r["conciliado"]
    assert r["advertencias"]


@pytest.mark.parametrize("valor", [None, "NaN", "Infinity", "Excelente"])
def test_dato_invalido_no_se_trata_como_cero(valor):
    r = service.conciliar_fila(fila(P_CAL=valor))
    assert r["total_calculado"] is None
    assert r["resultado_por_suma"] is None
    assert not r["conciliado"]


def test_futuro_no_se_elige_como_piloto(monkeypatch):
    monkeypatch.setattr(
        service, "leer_evaluaciones_preview", lambda: [fila(Fecha=datetime(2099, 1, 1))]
    )
    r = service.obtener_vista_previa(access_id=1)
    assert not r["pilotos"]
    assert r["seleccionada"]["advertencias"]


def test_fecha_y_tolerancia_decimal():
    r = service.conciliar_fila(fila(P_SER="40.01"), hoy=date(2024, 1, 1))
    assert r["diferencia"] == Decimal("0.01")
    assert r["conciliado"]


def test_cierra_conexion_y_libera_lock_al_fallar(monkeypatch):
    class Conexion:
        cerrada = False

        def cursor(self):
            raise RuntimeError("fallo ODBC")

        def close(self):
            self.cerrada = True

    connection = Conexion()
    monkeypatch.setattr(service, "_access_read_connection", lambda _: connection)
    with pytest.raises(service.AccessReadError):
        service.leer_evaluaciones_preview()
    assert connection.cerrada
    assert not service._access_connection_lock.locked()


def test_filtro_no_colapsa_evaluaciones_del_mismo_proveedor(monkeypatch):
    monkeypatch.setattr(
        service, "leer_evaluaciones_preview", lambda: [fila(), fila(Id=2)]
    )
    r = service.obtener_vista_previa(q="prueba", access_id=2)
    assert r["coincidencias"] == 2
    assert len(r["opciones"]) == 2
    assert r["seleccionada"]["id"] == 2


def test_renderizado_escapa_datos_access_y_muestra_borrador(monkeypatch):
    from starlette.requests import Request
    from app.api import ui_evaluaciones
    from app.main import app  # noqa: F401  # Activa compatibilidad TemplateResponse.

    monkeypatch.setattr(
        service,
        "leer_evaluaciones_preview",
        lambda: [fila(Razon_Social="<script>alert(1)</script>")],
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/ui/evaluaciones/vista-previa",
            "headers": [],
        }
    )
    request.state.current_user = {"roles": ["admin"], "permissions": {}}
    response = ui_evaluaciones.ui_evaluaciones_vista_previa(request, q="", access_id=1)
    html = response.body.decode()
    assert response.status_code == 200
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "Post contractual" in html
    assert "Sin guardado" in html


def test_vista_tiene_permiso_y_redirige_sin_sesion():
    from fastapi.testclient import TestClient
    from app.api.deps_auth import resolve_ui_permission
    from app.main import app

    assert resolve_ui_permission("/ui/evaluaciones/vista-previa", "GET") == (
        "ui_evaluaciones",
        False,
    )
    response = TestClient(app).get(
        "/ui/evaluaciones/vista-previa", follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"].startswith("/ui/login")
