import json
import sqlite3
from unittest.mock import Mock

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import deps_auth as auth, wizard_ai as api
from app.schemas.ai_settings import AISettingsIn
from app.schemas.wizard_ai import WizardChatIn
from app.services import wizard_ai_service as service
from app.services.ai_settings_service import AISettingsError

BASE = "/api/plan-produccion-mensual/asistente-oc/ia/conversacion"


def payload():
    return {
        "confirmar_envio": True,
        "mensaje": "Preparar diciembre",
        "contexto": {
            "anio": 2026,
            "mes": 12,
            "paso": 1,
            "productos_plan": 0,
            "registros_stock_pt": 0,
            "registros_deuda": 0,
        },
    }


@pytest.fixture
def config(tmp_path, monkeypatch):
    data = AISettingsIn(
        modelo="modelo-ficticio",
        wizard_conversacional=True,
        precio_entrada_millon_usd="1",
        precio_salida_millon_usd="2",
        solicitudes_por_minuto=60,
    ).model_dump(mode="json", exclude={"api_key", "eliminar_clave_local"})
    data["api_key_configurada"] = True
    monkeypatch.setattr(
        service.settings, "_SETTINGS_PATH", tmp_path / "ai_settings.json"
    )
    monkeypatch.setattr(service.settings, "get_ai_settings", lambda: data)
    monkeypatch.setattr(
        service.settings,
        "get_connection_test_credentials",
        lambda: (data, "clave-ficticia"),
    )
    monkeypatch.setattr(
        httpx.HTTPTransport,
        "handle_request",
        Mock(side_effect=AssertionError("Red prohibida")),
    )
    return data


def transport(monkeypatch, output, status="completed", code=200):
    response = Mock(status_code=code)
    response.json.return_value = {
        "status": status,
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(output)}],
            }
        ],
    }
    client = Mock()
    client.post.return_value = response
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(service.httpx, "Client", Mock(return_value=client))
    return client


def test_conversacion_propone_sin_ejecutar_y_solo_envia_metadatos(config, monkeypatch):
    proposal = {
        "mensaje": "¿Tenés stock MP?",
        "accion": "stock_mp",
        "anio": None,
        "mes": None,
    }
    client = transport(monkeypatch, proposal)
    result = service.converse(WizardChatIn.model_validate(payload()), 7)
    assert result == proposal
    body = client.post.call_args.kwargs["json"]
    assert body["store"] is False
    assert "tools" not in body
    assert body["text"]["format"]["strict"] is True
    assert json.loads(body["input"])["contexto"] == WizardChatIn.model_validate(payload()).contexto.model_dump()
    with sqlite3.connect(
        service.settings._SETTINGS_PATH.parent / "wizard_ai_usage.sqlite3"
    ) as db:
        assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
    assert (
        b"Preparar diciembre"
        not in (
            service.settings._SETTINGS_PATH.parent / "wizard_ai_usage.sqlite3"
        ).read_bytes()
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"wizard_conversacional": False},
        {"precio_entrada_millon_usd": "0"},
        {"precio_salida_millon_usd": "0"},
        {"max_caracteres_envio": 10},
        {"presupuesto_diario_usd": "0.000001"},
    ],
)
def test_bloqueos_no_realizan_envios(config, monkeypatch, changes):
    config.update(changes)
    client = transport(monkeypatch, {})
    with pytest.raises(AISettingsError):
        service.converse(WizardChatIn.model_validate(payload()), 7)
    client.post.assert_not_called()


@pytest.mark.parametrize(
    "proposal,status",
    [
        (
            {"mensaje": "Ejecutar SQL", "accion": "sql", "anio": None, "mes": None},
            "completed",
        ),
        (
            {"mensaje": "Período", "accion": "periodo", "anio": None, "mes": None},
            "completed",
        ),
        (
            {"mensaje": "Hola", "accion": "preguntar", "anio": None, "mes": None},
            "incomplete",
        ),
        (
            {
                "mensaje": "Hola",
                "accion": "preguntar",
                "anio": None,
                "mes": None,
                "sql": "select 1",
            },
            "completed",
        ),
    ],
)
def test_rechaza_acciones_no_permitidas_o_respuesta_incompleta(
    config, monkeypatch, proposal, status
):
    transport(monkeypatch, proposal, status=status)
    with pytest.raises(AISettingsError):
        service.converse(WizardChatIn.model_validate(payload()), 7)


def test_frecuencia_y_reserva_sobreviven_a_nueva_conexion(config):
    config["solicitudes_por_minuto"] = 1
    service._reserve(config, {}, 1)
    with pytest.raises(AISettingsError, match="frecuencia"):
        service._reserve(config, {}, 2)
    config["solicitudes_por_minuto"] = 60
    config["presupuesto_diario_usd"] = "0.000001"
    with pytest.raises(AISettingsError, match="presupuesto"):
        service._reserve(config, {}, 2)


def test_fallo_http_no_reintenta_ni_expone_proveedor(config, monkeypatch):
    client = transport(monkeypatch, {}, code=401)
    with pytest.raises(AISettingsError, match="OpenAI no completó"):
        service.converse(WizardChatIn.model_validate(payload()), 7)
    client.post.assert_called_once()


def test_no_acepta_archivos_datos_ni_confirmacion_falsa():
    for changes in [
        {"confirmar_envio": False},
        {"archivo": "datos"},
        {"contexto": {**payload()["contexto"], "productos": []}},
    ]:
        with pytest.raises(ValidationError):
            WizardChatIn.model_validate({**payload(), **changes})


@pytest.mark.parametrize(
    "user,expected",
    [
        (None, 401),
        ({"permissions": {"ui_plan_mensual": (True, True)}}, 403),
        ({"id": 7, "permissions": {"ui_plan_asistente_oc": (True, False)}}, 200),
    ],
)
def test_api_exige_sesion_y_permiso_del_wizard(monkeypatch, user, expected):
    app = FastAPI()
    app.include_router(
        api.router,
        prefix="/api",
        dependencies=[Depends(auth.require_api_screen_permission)],
    )
    app.dependency_overrides[auth.get_current_user] = lambda: user
    app.dependency_overrides[auth.get_current_user_optional] = lambda: user
    converse = Mock(
        return_value={
            "mensaje": "Período",
            "accion": "preguntar",
            "anio": None,
            "mes": None,
        }
    )
    monkeypatch.setattr(api, "converse", converse)
    with TestClient(app) as client:
        result = client.post(BASE, json=payload())
        assert result.status_code == expected
        if expected == 200:
            assert result.headers["cache-control"] == "no-store"
            denied = client.post(
                BASE, json=payload(), headers={"Origin": "https://otro.invalid"}
            )
            assert denied.status_code == 403
            missing = payload()
            missing.pop("confirmar_envio")
            assert client.post(BASE, json=missing).status_code == 422
            assert converse.call_count == 1
        else:
            converse.assert_not_called()
