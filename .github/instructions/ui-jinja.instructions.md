---
applyTo: "app/api/ui_*.py,app/templates/**/*.html,app/static/**/*"
description: "Usar cuando edites vistas UI, templates Jinja2, JavaScript vanilla o estilos del sistema de compras."
---

- Mantener el patrón actual: rutas HTML en `app/api/ui_*.py`, datos por `fetch` contra `/api`, y templates Jinja2 en `app/templates/`.
- Reutilizar clases y estructura de [app/static/css/estilos.css](../../app/static/css/estilos.css) y tomar como referencia pantallas existentes antes de inventar un patrón nuevo.
- Si una vista requiere autenticación, recordar que `/ui/*` está protegido por middleware y dependencias en [app/main.py](../../app/main.py).
- No mover lógica de negocio al template ni al router UI; el router prepara contexto y la API resuelve operaciones.
- Para CRUDs en tablas, seguir el patrón del repo: `data-*` para estado de fila, edición inline o formularios simples, y mensajes claros ante errores.