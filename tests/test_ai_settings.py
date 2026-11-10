import json
import os
import urllib.request
from unittest.mock import Mock

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import ai_settings as api
from app.api import deps_auth as auth
from app.api import system_api
from app.schemas.ai_settings import AISettingsIn
from app.services import ai_policy_service, ai_settings_service as service


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        service, "_SETTINGS_PATH", tmp_path / "private" / "ai_settings.json"
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def deny(*args, **kwargs):
        raise AssertionError("No se permiten llamadas externas")

    async def deny_async(*args, **kwargs):
        deny()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_async)
    monkeypatch.setattr(urllib.request, "urlopen", deny)


@pytest.fixture
def encrypted(monkeypatch):
    protect = Mock(return_value="DPAPI-FICTICIO")
    monkeypatch.setattr(service, "_protect_secret", protect)
    return protect


def test_defaults_no_habilitan_ni_crean_archivo():
    data = service.get_ai_settings()
    assert data["habilitada"] is False
    assert data["api_key_configurada"] is False
    assert data["modelo"] == ""
    assert not service._SETTINGS_PATH.exists()


def test_clave_solo_cifrada_y_auditoria_sin_valores(encrypted):
    secret = "clave-ficticia-para-pruebas"
    response = service.save_ai_settings(
        AISettingsIn(modelo="modelo-prueba", api_key=secret), 7
    )
    stored = service._SETTINGS_PATH.read_text(encoding="utf-8")
    assert secret not in stored
    assert secret not in json.dumps(response)
    assert "DPAPI-FICTICIO" not in json.dumps(response)
    assert "api_key" not in response
    assert response["api_key_configurada"] is True
    assert response["habilitada"] is False
    assert json.loads(stored)["auditoria"][-1]["usuario_id"] == 7
    assert "clave_local" in json.loads(stored)["auditoria"][-1]["campos"]
    encrypted.assert_called_once_with(secret)
    with pytest.raises(ai_policy_service.ExternalAIDisabled):
        ai_policy_service.require_external_ai()


def test_conservar_reemplazar_y_eliminar_clave(encrypted):
    service.save_ai_settings(AISettingsIn(api_key="clave-ficticia-original"), 1)
    service.save_ai_settings(AISettingsIn(modelo="modelo-nuevo"), 1)
    assert encrypted.call_count == 1
    assert service.get_ai_settings()["api_key_local_configurada"]
    service.save_ai_settings(AISettingsIn(api_key="clave-ficticia-nueva"), 1)
    assert encrypted.call_count == 2
    result = service.save_ai_settings(AISettingsIn(eliminar_clave_local=True), 1)
    assert result["api_key_configurada"] is False
    assert json.loads(service._SETTINGS_PATH.read_text())["api_key_dpapi"] is None


def test_variable_entorno_tiene_prioridad_y_no_se_borra(monkeypatch, encrypted):
    monkeypatch.setenv("OPENAI_API_KEY", "clave-ficticia-entorno")
    result = service.save_ai_settings(AISettingsIn(eliminar_clave_local=True), 1)
    assert result["api_key_origen"] == "entorno"
    assert result["api_key_configurada"] is True
    assert "clave-ficticia-entorno" not in service._SETTINGS_PATH.read_text()


def test_archivo_corrupto_no_se_sobrescribe(encrypted):
    service._SETTINGS_PATH.parent.mkdir()
    service._SETTINGS_PATH.write_text("archivo inválido", encoding="utf-8")
    with pytest.raises(service.AISettingsError):
        service.save_ai_settings(AISettingsIn(), 1)
    assert service._SETTINGS_PATH.read_text(encoding="utf-8") == "archivo inválido"
    encrypted.assert_not_called()


def test_fallo_atomicidad_conserva_configuracion(monkeypatch, encrypted):
    service.save_ai_settings(AISettingsIn(modelo="original"), 1)
    previous = service._SETTINGS_PATH.read_bytes()
    monkeypatch.setattr(
        service.os, "replace", Mock(side_effect=OSError("falla ficticia"))
    )
    with pytest.raises(service.AISettingsError):
        service.save_ai_settings(AISettingsIn(modelo="cambio"), 2)
    assert service._SETTINGS_PATH.read_bytes() == previous
    assert list(service._SETTINGS_PATH.parent.glob(".ai_settings_*")) == []


def test_fallo_cifrado_no_guarda_clave(monkeypatch):
    monkeypatch.setattr(
        service,
        "_protect_secret",
        Mock(side_effect=service.AISettingsError("falló cifrado")),
    )
    with pytest.raises(service.AISettingsError):
        service.save_ai_settings(AISettingsIn(api_key="clave-ficticia-de-prueba"), 1)
    assert not service._SETTINGS_PATH.exists()


@pytest.mark.skipif(os.name != "nt", reason="DPAPI requiere Windows")
def test_dpapi_real_con_secreto_ficticio():
    encrypted = service._protect_secret("clave-ficticia-sin-valor-comercial")
    assert len(encrypted) > 40
    assert "clave-ficticia" not in encrypted


def client_for(user, base_url="https://testserver"):
    app = FastAPI()
    app.include_router(
        api.router,
        prefix="/api",
        dependencies=[Depends(auth.require_api_screen_permission)],
    )
    app.include_router(
        system_api.router,
        prefix="/api",
        dependencies=[Depends(auth.require_api_screen_permission)],
    )
    app.dependency_overrides[auth.get_current_user] = lambda: user
    app.dependency_overrides[auth.get_current_user_optional] = lambda: user
    return TestClient(app, base_url=base_url)


@pytest.mark.parametrize(
    "user,status",
    [
        (None, 401),
        ({"permissions": {}}, 403),
        ({"permissions": {"ui_admin_settings": (True, False)}}, 200),
    ],
)
def test_lectura_requiere_permiso_configuracion(user, status):
    with client_for(user) as client:
        response = client.get("/api/system/settings/ia")
    assert response.status_code == status
    if status == 200:
        assert response.headers["cache-control"] == "no-store"


def test_lector_no_puede_guardar():
    with client_for({"permissions": {"ui_admin_settings": (True, False)}}) as client:
        response = client.post(
            "/api/system/settings/ia", json={"modelo": "modelo-prueba"}
        )
    assert response.status_code == 403
    assert not service._SETTINGS_PATH.exists()


def test_editor_guarda_sin_revelar_clave(encrypted):
    with client_for(
        {"id": 7, "permissions": {"ui_admin_settings": (True, True)}}
    ) as client:
        response = client.post(
            "/api/system/settings/ia",
            json={"api_key": "clave-ficticia-sin-valor", "modelo": "modelo-prueba"},
        )
        data = client.get("/api/system/settings/ia")
    assert response.status_code == 200
    assert response.json()["habilitada"] is False
    assert "clave-ficticia" not in response.text + data.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"habilitada": True},
        {"proveedor": "anthropic"},
        {"timeout_segundos": 0},
        {"presupuesto_diario_usd": 0},
        {"max_tokens_salida": 999999},
    ],
)
def test_no_se_puede_habilitar_o_guardar_limites_invalidos(payload):
    with client_for({"roles": ["admin"]}) as client:
        response = client.post("/api/system/settings/ia", json=payload)
    assert response.status_code == 422
    assert not service._SETTINGS_PATH.exists()


def test_origen_externo_no_puede_guardar():
    with client_for({"roles": ["admin"]}) as client:
        response = client.post(
            "/api/system/settings/ia",
            json={},
            headers={"Origin": "https://externo.invalid"},
        )
    assert response.status_code == 403
    assert not service._SETTINGS_PATH.exists()


def test_clave_rechazada_sobre_http_remoto(encrypted):
    with client_for({"roles": ["admin"]}, base_url="http://testserver") as client:
        response = client.post(
            "/api/system/settings/ia", json={"api_key": "clave-ficticia-no-transmitir"}
        )
    assert response.status_code == 400
    encrypted.assert_not_called()


def test_configuracion_general_no_expone_secretos(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "database_url": "secreto-bd",
                "openai_api_key": "secreto-openai",
                "anthropic_api_key": "secreto-anthropic",
                "auth_secret_key": "secreto-auth",
                "bcra_api_token": "secreto-token",
                "bcra_sync_days": 5,
                "bcra_api_base_url": "https://api.bcra.gob.ar",
            }
        )
    )
    monkeypatch.setattr(system_api, "_APP_CONFIG_PATH", config)
    with client_for({"roles": ["admin"]}) as client:
        response = client.get("/api/system/settings")
    assert response.status_code == 200
    assert response.json() == {
        "bcra_sync_days": 5,
        "bcra_api_base_url": "https://api.bcra.gob.ar",
    }
    assert "secreto" not in response.text


@pytest.mark.parametrize("write", [False, True])
def test_formulario_no_incluye_clave_y_respeta_permiso(write):
    from html.parser import HTMLParser
    from types import SimpleNamespace
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    class FormParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.fieldsets = []
            self.key = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "fieldset":
                self.fieldsets.append(attrs)
            if attrs.get("id") == "ia-clave":
                self.key = attrs

    usuario = {"nombre": "Prueba", "permissions": {"ui_admin_settings": (True, write)}}
    env = Environment(
        loader=FileSystemLoader("app/templates"), autoescape=select_autoescape(["html"])
    )
    html = env.get_template("admin/settings.html").render(
        current_user=usuario,
        request=SimpleNamespace(state=SimpleNamespace(current_user=usuario)),
        app_version="prueba",
    )
    parser = FormParser()
    parser.feed(html)
    assert parser.key["type"] == "password"
    assert "value" not in parser.key
    assert ("disabled" in parser.fieldsets[0]) is (not write)
    assert "IA y controles" in html
    assert "#ia" in html


@pytest.fixture
def test_transport(monkeypatch):
    from app.services import ai_connection_test_service as connection

    monkeypatch.setattr(
        connection, "_attempts", {"dia": "", "cantidad": 0, "ultimo": None}
    )
    monkeypatch.setattr(
        connection,
        "get_connection_test_credentials",
        lambda: (
            {
                "modelo": "modelo-prueba",
                "timeout_segundos": 30,
                "max_tokens_salida": 1500,
            },
            "clave-ficticia-prueba",
        ),
    )
    from unittest.mock import MagicMock

    transport = MagicMock()
    client = transport.return_value.__enter__.return_value
    monkeypatch.setattr(connection.httpx, "Client", transport)
    return connection, client


def test_conexion_solo_envia_prompt_autorizado(test_transport):
    connection, client = test_transport
    client.post.return_value = httpx.Response(
        200,
        json={
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "OK"}]}
            ]
        },
    )
    result = connection.test_openai_connection(7)
    assert result["conexion_correcta"] is True
    assert result["respuesta_ok"] is True
    assert result["ia_compras_habilitada"] is False
    assert client.post.call_args.args == ("https://api.openai.com/v1/responses",)
    assert client.post.call_args.kwargs["json"] == {
        "model": "modelo-prueba",
        "input": "Respondé OK",
        "store": False,
        "max_output_tokens": 64,
    }
    audit = (service._SETTINGS_PATH.parent / "ai_connection_tests.log").read_text()
    assert "clave-ficticia" not in audit
    assert "Respondé" not in audit
    with pytest.raises(service.AISettingsError):
        connection.test_openai_connection(7)
    assert client.post.call_count == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_errores_proveedor_no_exponen_respuesta(test_transport, status):
    connection, client = test_transport
    client.post.return_value = httpx.Response(
        status, json={"error": "secreto-ficticio-no-mostrar"}
    )
    with pytest.raises(service.AISettingsError) as exc:
        connection.test_openai_connection(7)
    assert "secreto-ficticio" not in str(exc.value)
    assert client.post.call_count == 1


def test_boton_exige_confirmacion_y_permiso(monkeypatch):
    call = Mock(return_value={"conexion_correcta": True})
    monkeypatch.setattr(api, "test_openai_connection", call)
    with client_for({"permissions": {"ui_admin_settings": (True, False)}}) as client:
        assert (
            client.post(
                "/api/system/settings/ia/probar", json={"confirmar_envio": True}
            ).status_code
            == 403
        )
    with client_for({"roles": ["admin"]}) as client:
        assert client.post("/api/system/settings/ia/probar", json={}).status_code == 422
        assert (
            client.post(
                "/api/system/settings/ia/probar", json={"confirmar_envio": False}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/system/settings/ia/probar",
                json={"confirmar_envio": True, "consulta": "dato-no-autorizado"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/system/settings/ia/probar", json={"confirmar_envio": True}
            ).status_code
            == 200
        )
    call.assert_called_once()


@pytest.mark.skipif(os.name != "nt", reason="DPAPI requiere Windows")
def test_clave_cifrada_se_recupera_para_prueba_autorizada():
    secret = "clave-ficticia-solo-prueba"
    cipher = service._protect_secret(secret)
    assert service._unprotect_secret(cipher) == secret
