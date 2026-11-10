import urllib.request

import httpx
from unittest.mock import Mock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader

from app.api import deps_auth as auth
from app.api import plan_produccion as api
from app.services import ai_policy_service as policy

BASE = "/api/plan-produccion-mensual"


@pytest.fixture(autouse=True)
def bloquear_http_externo(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Las pruebas no deben realizar solicitudes HTTP externas")

    async def deny_async(*args, **kwargs):
        deny()

    # No afecta al transporte ASGI ni al canal interno del event loop de Windows.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_async)
    monkeypatch.setattr(urllib.request, "urlopen", deny)


@pytest.fixture
def client_factory(monkeypatch):
    db = Mock()
    calcular = Mock(return_value={"resumen": {}})
    historial = Mock(return_value=1)
    analisis = Mock(return_value={"resumen": {}})
    valorizados = Mock(return_value={"items": []})
    monkeypatch.setattr(api, "calcular_asistente_oc", calcular)
    monkeypatch.setattr(api, "registrar_corrida_asistente_oc", historial)
    monkeypatch.setattr(api, "calcular_faltantes_y_capacidad", analisis)
    monkeypatch.setattr(api, "calcular_requerimientos_valorizados", valorizados)

    def build(user):
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

    return build, db, calcular, historial, analisis, valorizados


def user(screen="ui_plan_asistente_oc", write=False):
    return {
        "id": 123,
        "email": "prueba@example.invalid",
        "permissions": {screen: (True, write)},
    }


@pytest.mark.parametrize("flag", [None, "false", "0", "off", "no", "False", "f", "n"])
def test_lector_simula_sin_guardar_ni_registrar(client_factory, flag):
    build, db, calcular, historial, *_ = client_factory
    suffix = "" if flag is None else f"&persistir_sugerencias={flag}"
    with build(user()) as client:
        response = client.post(
            f"{BASE}/asistente-oc/calcular?mes=2&anio=2026{suffix}", json={}
        )
    assert response.status_code == 200
    assert calcular.call_args.kwargs["persistir_sugerencias"] is False
    historial.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize("flag", ["true", "True", "TRUE", "1", "yes", "on", "t", "y"])
def test_lector_no_puede_guardar_con_variantes_booleanas(client_factory, flag):
    build, db, calcular, historial, *_ = client_factory
    with build(user()) as client:
        response = client.post(
            f"{BASE}/asistente-oc/calcular?mes=2&anio=2026&persistir_sugerencias={flag}",
            json={},
        )
    assert response.status_code == 403
    calcular.assert_not_called()
    historial.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    "usuario",
    [
        user(write=True),
        {"id": 123, "email": "prueba@example.invalid", "roles": ["admin"]},
    ],
)
def test_guardar_respeta_permiso_de_pantalla_y_admin(client_factory, usuario):
    build, db, calcular, historial, *_ = client_factory
    with build(usuario) as client:
        response = client.post(
            f"{BASE}/asistente-oc/calcular?mes=2&anio=2026&persistir_sugerencias=1",
            json={},
        )
    assert response.status_code == 200
    assert calcular.call_args.kwargs["persistir_sugerencias"] is True
    historial.assert_called_once()
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    "usuario",
    [
        {"permissions": {"plan": (True, True)}},
        user("ui_plan_mensual", True),
        user("ui_plan_asistente_oc"),
    ],
)
def test_modulo_antiguo_u_otra_pantalla_no_autorizan_guardado(client_factory, usuario):
    build, _, calcular, *_ = client_factory
    with build(usuario) as client:
        response = client.post(
            f"{BASE}/asistente-oc/calcular?mes=2&anio=2026&persistir_sugerencias=true",
            json={},
        )
    assert response.status_code == 403
    calcular.assert_not_called()


@pytest.mark.parametrize("screen", ["ui_plan_mensual", "ui_plan_requerimientos"])
def test_analisis_es_consulta_por_defecto(client_factory, screen):
    build, db, _, _, analisis, _ = client_factory
    with build(user(screen)) as client:
        response = client.get(f"{BASE}/faltantes-capacidad?mes=2&anio=2026")
        denied = client.get(
            f"{BASE}/faltantes-capacidad?mes=2&anio=2026&persistir_sugerencias=1"
        )
    assert response.status_code == 200
    assert analisis.call_args.args[-1] is False
    assert denied.status_code == 403
    db.execute.assert_not_called()


def test_valorizacion_no_elude_escritura_con_booleano_numerico(client_factory):
    build, _, _, _, _, valorizados = client_factory
    with build(user("ui_plan_requerimientos")) as client:
        response = client.get(
            f"{BASE}/requerimientos-valuados?mes=2&anio=2026&persistir=1"
        )
    assert response.status_code == 403
    valorizados.assert_not_called()


def test_ia_sigue_bloqueada_con_claves_y_admin(client_factory, monkeypatch):
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(key, "clave-ficticia")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("EXTERNAL_AI_ENABLED", "true")
    build, db, calcular, historial, *_ = client_factory
    with build({"roles": ["admin"]}) as client:
        state = client.get(f"{BASE}/asistente-oc/ia/estado")
        response = client.post(
            f"{BASE}/asistente-oc/ia", json={"consulta": "Datos ficticios"}
        )
    assert state.status_code == 200
    assert state.json()["habilitada"] is False
    assert state.json()["proveedor"] is None
    assert response.status_code == 403
    with pytest.raises(policy.ExternalAIDisabled):
        policy.require_external_ai()
    db.execute.assert_not_called()
    calcular.assert_not_called()
    historial.assert_not_called()


def test_ia_exige_sesion_y_pantalla(client_factory):
    build, *_ = client_factory
    with build(None) as client:
        assert client.get(f"{BASE}/asistente-oc/ia/estado").status_code == 401
    with build(user("ui_plan_mensual")) as client:
        assert client.get(f"{BASE}/asistente-oc/ia/estado").status_code == 403


@pytest.mark.parametrize(
    "usuario,expected",
    [
        (user(), "false"),
        (user(write=True), "true"),
        ({"roles": ["ADMIN"]}, "true"),
        ({"permissions": {"plan": (True, True)}}, "false"),
    ],
)
def test_controles_ui_siguen_permisos_de_pantalla(usuario, expected):
    env = Environment(loader=FileSystemLoader("app/templates"))
    macros = env.get_template("partials/perm_macros.html").make_module(
        {"current_user": usuario}
    )
    assert str(macros.can_write_any_js(["ui_plan_asistente_oc"])).strip() == expected
    assert ("disabled" in str(macros.can_write_any_attr(["ui_plan_asistente_oc"]))) == (
        expected == "false"
    )
