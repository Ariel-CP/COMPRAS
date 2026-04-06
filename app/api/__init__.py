"""Paquete de routers y vistas (API/UI).

Estas importaciones son intencionales para ayudar al anÃ¡lisis estÃ¡tico
(Pylance/Pyright) a resolver `from app.api import <submodulo>`.
"""

from . import router as router  # noqa: F401
from . import ui_rubros as ui_rubros  # noqa: F401
from . import ui_sessions as ui_sessions  # noqa: F401