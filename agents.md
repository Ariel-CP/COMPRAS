# AGENTS.md

## Propósito

Workspace de compras y planificación con FastAPI + MariaDB/MySQL. La fuente de verdad del modelo de datos es [database/schema.sql](database/schema.sql). El agente debe priorizar cambios pequeños, verificables y alineados con la estructura real del repo.

## Arranque Rápido

- Usar el entorno virtual del repo: `.venv\Scripts\python.exe` en Windows.
- Comandos disponibles en tasks de VS Code:
  - `Run API (uvicorn)`
  - `Lint (ruff)`
  - `Format (black)`
  - `Test (pytest)`
- Hay muy pocos tests automatizados en [tests/test_ui_auth_redirect.py](tests/test_ui_auth_redirect.py); cuando no exista un test focalizado, validar con `ruff`, arranque de API o revisión localizada del flujo tocado.

## Arquitectura Real

- Entrada FastAPI: [app/main.py](app/main.py)
- Router API agregado: [app/api/router.py](app/api/router.py)
- Acceso a BD y sesiones: [app/db.py](app/db.py)
- Lógica de negocio: `app/services/`
- Endpoints JSON: `app/api/`
- Vistas HTML y routers UI: `app/templates/` y `app/api/ui_*.py`
- SQL y migraciones: `database/` y `database/migrations/`
- Scripts operativos y de desarrollo: ver [scripts/README.md](scripts/README.md)

El repo ya incluye módulos además de MBOM y compras: auth, usuarios, roles, backups, recepciones, evaluaciones, informes, tipo de cambio y administración.

## Reglas Operativas

- Leer [database/schema.sql](database/schema.sql) antes de asumir tablas, enums, checks o relaciones.
- Mantener el flujo `endpoint -> service -> database`; no poner lógica de negocio sustancial en routers.
- Preferir consultas parametrizadas y transacciones explícitas cuando varias escrituras dependan entre sí.
- Si el cambio toca UI, preservar el patrón actual: Jinja2 + fetch API + clases globales de [app/static/css/estilos.css](app/static/css/estilos.css).
- Las rutas `/ui/*` están protegidas por middleware salvo login/logout y home; revisar [app/main.py](app/main.py) antes de cambiar navegación o auth.
- El proyecto parchea compatibilidad de `TemplateResponse`; no reemplazar ese patrón sin revisar [app/main.py](app/main.py).
- Scripts nuevos deben respetar la separación `scripts/ops` vs `scripts/dev` descrita en [scripts/README.md](scripts/README.md).

## Convenciones del Repo

- `snake_case` para funciones y variables, `PascalCase` para clases.
- Type hints y `logging` siempre que el código nuevo lo justifique.
- Pydantic para request/response en `app/schemas/`.
- Mantener comentarios breves y solo cuando aclaren una regla no obvia.
- No hardcodear credenciales ni rutas sensibles; usar configuración y variables de entorno existentes.

## Pitfalls Verificados

- En Windows conviene fijar el intérprete del workspace a `.venv\Scripts\python.exe`.
- `database/schema.sql` está en UTF-16/Unicode; si una herramienta falla al leerlo, usar una lectura con encoding explícito.
- En sincronización de BD hay antecedentes de falsos positivos: tratar dumps vacíos o stderr como fallos reales, no como éxito.

## Documentación a Enlazar

- Visión general y setup: [README.md](README.md)
- Modelo de costos MBOM: [docs/costos_discriminados.md](docs/costos_discriminados.md)
- Validación del flujo de evaluación/recepción: [docs/VALIDACION_EVALUACION_PROVEEDORES.md](docs/VALIDACION_EVALUACION_PROVEEDORES.md)
- Organización de scripts: [scripts/README.md](scripts/README.md)

## Cómo Responder en Este Repo

- Responder en español.
- Para cambios grandes, proponer primero un plan corto con tablas afectadas, endpoints, services y validaciones.
- Si hay documentación existente para el tema, enlazarla en vez de duplicarla.
- Si el pedido parece apoyarse en CSV/Access/Power BI, revisar primero servicios y docs de recepción/evaluación antes de inventar un flujo nuevo.
