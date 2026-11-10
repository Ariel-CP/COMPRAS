"""Política local de IA: bloqueada hasta aprobar controles y contenido de envío.

No consulta configuración, credenciales, bases ni proveedores externos.
"""


class ExternalAIDisabled(RuntimeError):
    """La integración externa aún no está autorizada."""


def external_ai_status() -> dict:
    return {
        "habilitada": False,
        "proveedor": None,
        "requiere_autorizacion_contenido": True,
    }


def require_external_ai() -> None:
    # Una clave o un proveedor configurados no equivalen a autorización de envío.
    raise ExternalAIDisabled("IA externa deshabilitada")
