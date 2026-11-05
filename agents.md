# AGENTS.md

## Propósito

Workspace de compras y planificación con FastAPI + MariaDB/MySQL. El modelo de datos se documenta en [database/schema.sql](database/schema.sql) y las migraciones de [database/migrations](database/migrations); el dump base puede no incluir cambios posteriores. El agente debe priorizar cambios pequeños, verificables y alineados con la estructura real del repo.

## Arranque Rápido

- Usar el entorno virtual del repo: `.venv\Scripts\python.exe` en Windows.
- Comandos disponibles en tasks de VS Code:
  - `Run API (uvicorn)`
  - `Lint (ruff)`
  - `Format (black)`
  - `Test (pytest)`
- Hay pruebas focalizadas en `tests/` para auth, permisos por pantalla, recepción, Access, planos, artículos y tipo de cambio. Buscar primero las del flujo tocado y ejecutarlas con `.venv\Scripts\python.exe -m pytest tests/test_<modulo>.py -q`.
- Validar el código Python modificado con `.venv\Scripts\python.exe -m ruff check <archivos>`; para JavaScript, usar `node --check <archivo>` si Node está disponible.
- Para iniciar manualmente: `.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`. La task de VS Code agrega `--reload`.
- Antes de iniciar otra instancia, comprobar el puerto 8000. Verificar `/health` y el endpoint del flujo modificado; una respuesta del login o de un archivo estático no confirma que la API haya cargado los cambios.

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

- Leer [database/schema.sql](database/schema.sql) y las migraciones relacionadas antes de asumir tablas, enums, checks o relaciones. Si se opera sobre una base existente, comprobar su esquema real y no asumir que todas las migraciones están aplicadas.
- Mantener el flujo `endpoint -> service -> database`; no poner lógica de negocio sustancial en routers.
- Preferir consultas parametrizadas y transacciones explícitas cuando varias escrituras dependan entre sí.
- Si el cambio toca UI, preservar el patrón actual: Jinja2 + fetch API + clases globales de [app/static/css/estilos.css](app/static/css/estilos.css).
- Las rutas `/ui/*` están protegidas por middleware salvo login/logout. Revisar [app/main.py](app/main.py) y [app/api/deps_auth.py](app/api/deps_auth.py) antes de cambiar navegación, auth o permisos por pantalla; no asumir que home es pública.
- El proyecto parchea compatibilidad de `TemplateResponse` e inyecta `app_version`; no reemplazar ese patrón sin revisar [app/main.py](app/main.py). Versionar recursos estáticos modificados siguiendo el patrón existente para evitar mezclar HTML y JavaScript antiguos.
- Scripts nuevos deben respetar la separación `scripts/ops` vs `scripts/dev` descrita en [scripts/README.md](scripts/README.md).

## Recepción, Access y Artículos

- El catálogo de artículos se guarda en `producto` (`codigo`, `nombre`); no asumir que existe una tabla llamada `articulos`.
- Recepción operativa: [app/services/recepcion_operativa_service.py](app/services/recepcion_operativa_service.py). Historial directo de Access: [app/services/access_read_service.py](app/services/access_read_service.py). Son recorridos distintos; no sustituir uno por otro sin revisar el consumidor.
- Para snapshots versionados e identidad de origen, revisar [app/services/recepcion_access_snapshot_service.py](app/services/recepcion_access_snapshot_service.py) y las migraciones relacionadas. No confundir snapshot, staging y recepción canónica.
- Mantener Access en modo solo lectura (`ReadOnly=1`), cerrar conexiones y respetar los locks y cachés existentes. No modificar vínculos o archivos Access para resolver una consulta de la UI.
- El historial `/ui/recepcion/historial-access` debe reutilizar la asociación de `/ui/planos-articulos` mediante [app/services/articulo_plano_service.py](app/services/articulo_plano_service.py). El listado asocia los cuatro dígitos finales del código con el plano base disponible en el catálogo PDF; no agregar un catálogo alternativo solo al historial.
- Normalizar `539` a `0539` para buscar y mostrar planos de cuatro dígitos; conservar números de cinco dígitos sin truncarlos. Admitir varios artículos por plano y evitar duplicarlos por revisión del PDF.
- En Access, `ID_INT` identifica el control, `N_interno` es el número de inspección, `Lote` es la cantidad ingresada y `NOTA` contiene observaciones. Mantener separados material, nombre del artículo y observaciones; usar `ID_INT` para abrir el detalle aunque el listado muestre solo el interno.
- Al cambiar columnas del historial, actualizar encabezados, celdas, `colspan` y preferencias de orden/ancho en `localStorage`; conservar las asociaciones después de buscar o paginar.
- Para correcciones desde CSV, identificar encoding y separador antes de comparar. Revisar duplicados, códigos sin coincidencia y límites de longitud. Reutilizar [scripts/ops/corregir_nombres_articulos_csv.py](scripts/ops/corregir_nombres_articulos_csv.py) cuando corresponda: comparar primero y aplicar con respaldo, transacción y verificación posterior. Una corrección de nombres no autoriza crear artículos ni cambiar sus códigos.

## Convenciones del Repo

- `snake_case` para funciones y variables, `PascalCase` para clases.
- Type hints y `logging` siempre que el código nuevo lo justifique.
- Pydantic para request/response en `app/schemas/`.
- Mantener comentarios breves y solo cuando aclaren una regla no obvia.
- No hardcodear credenciales ni rutas sensibles; usar configuración y variables de entorno existentes.

## Pitfalls Verificados

- En Windows conviene fijar el intérprete del workspace a `.venv\Scripts\python.exe`.
- Si una recarga de uvicorn queda pendiente, comprobar logs, proceso y respuesta del endpoint. Reiniciar solo la instancia identificada del proyecto; no dar por aplicada una modificación únicamente porque cambió el archivo.
- `database/schema.sql` está en UTF-16/Unicode; leerlo con encoding explícito. Los archivos de código y documentación deben conservar UTF-8.
- En PowerShell, fijar `$OutputEncoding` a UTF-8 antes de enviar texto con acentos a Python u otros procesos mediante un pipe; comprobar que el archivo no termine con signos `?` en lugar de caracteres originales.
- Hay antecedentes de mojibake CP1252/UTF-8 en nombres y códigos. Revisar los caracteres reales antes de corregirlos; consultar [app/services/producto_service.py](app/services/producto_service.py) y [tests/test_producto_mojibake.py](tests/test_producto_mojibake.py) antes de duplicar normalizadores.
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
