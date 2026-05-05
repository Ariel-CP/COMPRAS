---
applyTo: "app/main.py,app/db.py,app/api/**/*.py,app/services/**/*.py,app/models/**/*.py,app/schemas/**/*.py,database/**/*.sql,scripts/**/*.py"
description: "Usar cuando edites backend FastAPI, acceso a datos, migraciones SQL o scripts de importacion/sincronizacion del sistema de compras."
---

- Verificá primero si el comportamiento debe vivir en router, service o script; por defecto los routers validan y delegan.
- Antes de escribir SQL, revisar [database/schema.sql](../../database/schema.sql) y solo después las migraciones específicas.
- Si tocás endpoints protegidos o navegación UI/API, confirmá cómo se registran routers y middleware en [app/main.py](../../app/main.py) y [app/api/router.py](../../app/api/router.py).
- En servicios de importación o sincronización, preferí idempotencia, logs claros y errores duros ante resultados parciales o falsos éxitos.
- Cuando agregues scripts nuevos, ubicarlos según [scripts/README.md](../../scripts/README.md): `ops` para operación controlada, `dev` para diagnóstico o pruebas manuales.
- Si no hay tests focalizados, validar con el task de `ruff`, con arranque de API o con una comprobación dirigida del flujo afectado.