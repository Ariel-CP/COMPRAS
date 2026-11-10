"""Excepción acotada: solo prueba sintética autorizada; no recibe datos comerciales."""

import json
import threading
import time
from datetime import datetime, timezone

import httpx

from app.services.ai_settings_service import (
    AISettingsError,
    get_connection_test_credentials,
)
from app.services import ai_settings_service

_LOCK = threading.Lock()
_attempts: dict = {"dia": "", "cantidad": 0, "ultimo": None}


def _audit(user_id: int, state: str) -> None:
    path = ai_settings_service._SETTINGS_PATH.parent / "ai_connection_tests.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "fecha": datetime.now(timezone.utc).isoformat(),
                    "usuario_id": user_id,
                    "accion": "prueba_conexion_ia",
                    "estado": state,
                }
            )
            + "\n"
        )


def test_openai_connection(user_id: int) -> dict:
    config, key = get_connection_test_credentials()
    with _LOCK:
        day = datetime.now(timezone.utc).date().isoformat()
        now = time.monotonic()
        if _attempts["dia"] != day:
            _attempts.update(dia=day, cantidad=0, ultimo=None)
        if _attempts["cantidad"] >= 3 or (
            _attempts["ultimo"] is not None and now - _attempts["ultimo"] < 60
        ):
            raise AISettingsError(
                "Esperá un minuto entre pruebas. Máximo 3 pruebas por día e instancia."
            )
        try:
            _audit(user_id, "iniciada")
        except OSError:
            raise AISettingsError(
                "No se pudo registrar la prueba; no se realizó el envío."
            ) from None
        _attempts["cantidad"] += 1
        _attempts["ultimo"] = now
    success = False
    try:
        with httpx.Client(
            timeout=min(config["timeout_segundos"], 20),
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": config["modelo"],
                    "input": "Respondé OK",
                    "store": False,
                    "max_output_tokens": min(64, config["max_tokens_salida"]),
                },
            )
        errors = {
            400: "OpenAI rechazó el modelo o los parámetros de prueba. Revisá el modelo configurado.",
            401: "OpenAI rechazó la clave API. Revisá la credencial guardada.",
            403: "La cuenta no tiene permiso para usar el modelo configurado.",
            404: "El modelo configurado no está disponible para esta cuenta.",
            429: "OpenAI informó falta de cuota o un límite de solicitudes. Revisá la facturación y los límites.",
        }
        if response.status_code != 200:
            raise AISettingsError(
                errors.get(
                    response.status_code,
                    "OpenAI no pudo completar la prueba. Intentá más tarde.",
                )
            )
        data = response.json()
        text = "".join(
            part.get("text", "")
            for item in data.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        )
        success = True
        return {
            "conexion_correcta": True,
            "respuesta_ok": text.strip().upper().rstrip(".! ") == "OK",
            "mensaje": (
                "Conexión correcta. OpenAI respondió OK."
                if text.strip().upper().rstrip(".! ") == "OK"
                else "Conexión establecida. El modelo no devolvió OK dentro del límite de la prueba."
            ),
            "ia_compras_habilitada": False,
        }
    except (httpx.RequestError, ValueError, TypeError, AttributeError):
        raise AISettingsError(
            "No se pudo completar la prueba por un problema de conexión o respuesta. No se reintentó automáticamente."
        ) from None
    finally:
        key = ""
        try:
            _audit(user_id, "correcta" if success else "fallida")
        except OSError:
            pass
