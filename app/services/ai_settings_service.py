"""Configuración local de IA, sin transporte ni habilitación de envíos."""

import base64
import ctypes
import json
import os
import tempfile
import threading
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.ai_settings import AISettingsIn

_SETTINGS_PATH = Path(__file__).resolve().parents[2] / ".local" / "ai_settings.json"
_LOCK = threading.RLock()
_MAX_FILE_BYTES = 256000


class AISettingsError(RuntimeError):
    pass


def _protect_secret(value: str) -> str:
    if os.name != "nt":
        raise AISettingsError(
            "El guardado cifrado requiere Windows. Usá una variable de entorno en otro sistema."
        )

    class DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    protect = crypt32.CryptProtectData
    protect.argtypes = [
        ctypes.POINTER(DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    protect.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    raw = value.encode("utf-8")
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source = DataBlob(len(raw), buffer)
    target = DataBlob()
    # CRYPTPROTECT_UI_FORBIDDEN, alcance del usuario de Windows que ejecuta la API.
    if not protect(
        ctypes.byref(source),
        "Wizard OC API key",
        None,
        None,
        None,
        1,
        ctypes.byref(target),
    ):
        raise AISettingsError(
            "Windows no pudo proteger la clave. No se guardaron cambios."
        )
    try:
        return base64.b64encode(ctypes.string_at(target.pbData, target.cbData)).decode(
            "ascii"
        )
    finally:
        kernel32.LocalFree(target.pbData)


def _read_document() -> dict:
    try:
        if not _SETTINGS_PATH.exists():
            return {}
        if _SETTINGS_PATH.stat().st_size > _MAX_FILE_BYTES:
            raise AISettingsError(
                "El archivo de configuración de IA supera el tamaño permitido."
            )
        document = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(
            document.get("config", {}), dict
        ):
            raise ValueError("Formato inválido")
        AISettingsIn.model_validate(document.get("config", {}))
        if not isinstance(document.get("auditoria", []), list):
            raise ValueError("Auditoría inválida")
        return document
    except (OSError, ValueError, TypeError):
        raise AISettingsError(
            "No se pudo leer la configuración de IA. No se sobrescribió el archivo."
        ) from None


def _public(document: dict) -> dict:
    config = AISettingsIn.model_validate(document.get("config", {})).model_dump(
        mode="json",
        exclude={"api_key", "eliminar_clave_local"},
    )
    environment_key = bool(os.environ.get("OPENAI_API_KEY"))
    local_key = bool(document.get("api_key_dpapi"))
    return {
        **config,
        "habilitada": False,
        "api_key_configurada": environment_key or local_key,
        "api_key_local_configurada": local_key,
        "api_key_origen": (
            "entorno"
            if environment_key
            else "local_cifrada" if local_key else "sin_configurar"
        ),
        "autorizacion_por_envio": True,
        "seudonimizacion_obligatoria": True,
        "auditoria_solo_metadatos": True,
        "actualizado": document.get("actualizado"),
    }


def get_ai_settings() -> dict:
    with _LOCK:
        return _public(_read_document())


def save_ai_settings(payload: AISettingsIn, user_id: int) -> dict:
    key = payload.api_key.get_secret_value().strip() if payload.api_key else ""
    if payload.eliminar_clave_local and key:
        raise AISettingsError(
            "Elegí reemplazar o eliminar la clave, no ambas acciones."
        )
    if key and (not 10 <= len(key) <= 1024 or any(c.isspace() for c in key)):
        raise AISettingsError("La clave no tiene un formato válido.")
    with _LOCK:
        previous = _read_document()
        encrypted_key = previous.get("api_key_dpapi")
        if payload.eliminar_clave_local:
            encrypted_key = None
        elif key:
            encrypted_key = _protect_secret(key)
        config = payload.model_dump(
            mode="json", exclude={"api_key", "eliminar_clave_local"}
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        fields = [
            name
            for name, value in config.items()
            if previous.get("config", {}).get(name) != value
        ]
        if key or payload.eliminar_clave_local:
            fields.append("clave_local")
        audit = previous.get("auditoria", [])[-199:] + [
            {
                "fecha": timestamp,
                "usuario_id": user_id,
                "accion": "configuracion_ia_actualizada",
                "campos": fields,
            }
        ]
        document = {
            "version": 1,
            "config": config,
            "api_key_dpapi": encrypted_key,
            "actualizado": timestamp,
            "auditoria": audit,
        }
        temp_path = None
        try:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=_SETTINGS_PATH.parent,
                prefix=".ai_settings_",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                json.dump(document, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, _SETTINGS_PATH)
        except OSError:
            raise AISettingsError(
                "No se pudo guardar la configuración de IA."
            ) from None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return _public(document)


def _unprotect_secret(value: str) -> str:
    if os.name != "nt":
        raise AISettingsError(
            "La clave local requiere la cuenta de Windows que la guardó."
        )

    class DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    try:
        raw = base64.b64decode(value, validate=True)
        buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        source, target = DataBlob(len(raw), buffer), DataBlob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        decrypt = crypt32.CryptUnprotectData
        decrypt.argtypes = [
            ctypes.POINTER(DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DataBlob),
        ]
        decrypt.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        if not decrypt(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
        ):
            raise ValueError("No se pudo descifrar")
        try:
            return ctypes.string_at(target.pbData, target.cbData).decode("utf-8")
        finally:
            kernel32.LocalFree(target.pbData)
    except (OSError, ValueError, TypeError):
        raise AISettingsError(
            "No se pudo abrir la clave local con esta cuenta de Windows."
        ) from None


def get_connection_test_credentials() -> tuple[dict, str]:
    with _LOCK:
        document = _read_document()
        config = _public(document)
        if not config["modelo"]:
            raise AISettingsError("Guardá el modelo antes de probar la conexión.")
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key and document.get("api_key_dpapi"):
            key = _unprotect_secret(document["api_key_dpapi"])
        if not key:
            raise AISettingsError("Guardá una clave API antes de probar la conexión.")
        return config, key
