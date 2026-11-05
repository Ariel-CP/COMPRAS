![Compras: planificación, trazabilidad y calidad](docs/assets/readme-cover.svg)

# Sistema de Compras y Planificación

**Del catálogo de artículos al control de recepción.**

Gestión de estructuras MBOM, producción, materiales y proveedores en una aplicación web. Integra stock, precios, inspección de calidad, históricos de Access y planos PDF.

**FastAPI** · **MariaDB / MySQL** · **Jinja2** · **Microsoft Access**

[Instalación](#instalacion) · [Ejecutar](#ejecucion) · [Módulos](#modulos) · [Validación](#validacion) · [Operación](#operacion)

---

## Qué podés gestionar

| Producción y materiales | Compras y proveedores | Recepción y calidad |
| --- | --- | --- |
| Estructuras MBOM y costos | Catálogo de artículos y planos | Ingreso e inspección de materiales |
| Planificación mensual | Stock e historial de precios | Muestreo y pendientes de calidad |
| Requerimientos de materiales | Evaluación de proveedores | Consulta histórica de Access |

> **Para empezar:** prepará el entorno, configurá la base y ejecutá la API. Si el sistema ya está instalado, continuá en [Ejecución y comprobación](#ejecucion).

## Tecnologías y estructura

- Python + FastAPI, Pydantic y SQLAlchemy con consultas parametrizadas.
- MariaDB/MySQL.
- Jinja2, JavaScript con `fetch` y CSS compartido.
- Microsoft Access mediante `pyodbc`, con lectura de archivos en modo `ReadOnly=1`.

<details>
<summary><strong>Explorar la estructura del repositorio</strong></summary>

```text
app/
  main.py              # Aplicación, middleware y compatibilidad de plantillas
  core/config.py       # Configuración desde entorno, .env y app/config.json
  db.py                # Motor y sesiones de base de datos
  api/                 # Endpoints JSON y routers UI
  services/            # Lógica de negocio
  schemas/             # Modelos Pydantic
  templates/           # Vistas Jinja2
  static/              # CSS y JavaScript
database/
  schema.sql           # Dump base en UTF-16; revisar junto con las migraciones
  migrations/          # Cambios incrementales del modelo
scripts/
  ops/                 # Administración, migraciones, importaciones y despliegue
  dev/                 # Diagnóstico y herramientas de desarrollo
tests/                 # Pruebas por módulo
import/                # Plantillas de importación
```

</details>


El modelo se documenta en [database/schema.sql](database/schema.sql) y [database/migrations](database/migrations). El dump puede no incluir migraciones posteriores. Antes de operar sobre una instalación existente, comprobar su esquema real y las migraciones aplicadas.

<a id="instalacion"></a>

## Instalación local en Windows

Requisitos: Python 3.11 o posterior, MariaDB/MySQL accesible y Git para operaciones de versionado. Las consultas a Access requieren el controlador ODBC de Microsoft Access compatible con la arquitectura de Python y acceso al archivo configurado.

### 1. Preparar el entorno

Ejecutar desde la raíz del repositorio en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt pytest
```

Seleccionar `.venv\Scripts\python.exe` como intérprete del workspace. No es necesario activar el entorno si se invoca ese ejecutable directamente.

### 2. Configurar la aplicación

La API usa [app/core/config.py](app/core/config.py). Las variables de entorno tienen prioridad sobre `app/config.json`; también se carga `.env` desde la raíz. Hay una referencia en [.env.example](.env.example).

Ejemplo de `.env`, reemplazando los valores de muestra:

```dotenv
DATABASE_URL="mysql+pymysql://USUARIO:CLAVE@127.0.0.1:3306/compras_db?charset=utf8mb4"
AUTH_SECRET_KEY="REEMPLAZAR_POR_UN_SECRETO_PROPIO"
AUTH_COOKIE_SECURE=false
ACCESS_DB_PATH="R:/ruta/al/Control.accdb"
PLANOS_DIR="R:/ruta/a/planos/pdf"
```

Codificar en formato URL los caracteres especiales del usuario o la contraseña en `DATABASE_URL`. La API no construye esta URL a partir de `DB_HOST`, `DB_NAME`, `DB_USER` y `DB_PASS`; algunos scripts operativos sí usan esas variables y tienen su propia configuración.

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Conexión SQLAlchemy a MariaDB/MySQL |
| `MYSQL_POOL_SIZE`, `MYSQL_MAX_OVERFLOW` | Límites del pool de conexiones |
| `AUTH_SECRET_KEY` | Firma de tokens de sesión |
| `AUTH_COOKIE_SECURE` | Cookie HTTPS; usar `false` para desarrollo HTTP local |
| `AUTH_ACCESS_TOKEN_MINUTES`, `AUTH_REMEMBER_DAYS` | Duración de sesión |
| `ACCESS_DB_PATH`, `ACCESS_TABLE_NAME` | Archivo y tabla de origen de Access |
| `PLANOS_DIR` | Carpeta de planos PDF |
| `BACKUP_DIR`, `MYSQLDUMP_PATH`, `MYSQL_CLIENT_PATH` | Backups y clientes de base de datos |
| `BCRA_API_BASE_URL`, `BCRA_SYNC_DAYS`, `SYNC_JOB_TOKEN` | Configuración de tipo de cambio y sincronización |

No publicar archivos de configuración con credenciales, tokens o rutas privadas.

### 3. Preparar la base de datos

Crear la base y configurar un usuario con los permisos necesarios para la instalación. Para inicializarla, revisar el dump y las migraciones que correspondan a la versión elegida.

- `database/schema.sql` está en UTF-16. Convertirlo a UTF-8 antes de usar un cliente que no acepte ese encoding.
- El dump contiene `DROP TABLE`; no restaurarlo sobre una base con datos que se deban conservar.
- En instalaciones existentes, aplicar únicamente las migraciones pendientes, revisando dependencias. Hay migraciones históricas con prefijos repetidos: no ejecutar toda la carpeta mediante un bucle indiscriminado.
- Guardar un respaldo antes de modificar el esquema.

Ejemplo de ejecución de una migración pendiente, después de revisar su contenido y los requisitos:

```powershell
.\.venv\Scripts\python.exe scripts/ops/apply_migration.py database/migrations/025_permisos_por_pantalla.sql
```

Para administración y permisos iniciales, revisar [scripts/ops/seed_admin.py](scripts/ops/seed_admin.py), [scripts/ops/seed_roles.py](scripts/ops/seed_roles.py) y las migraciones de autenticación y permisos por pantalla.

<a id="ejecucion"></a>

## Ejecución y comprobación

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Para desarrollo con recarga automática, agregar `--reload` o usar la task **Run API (uvicorn)** de VS Code.

- Inicio de sesión: [http://localhost:8000/ui/login](http://localhost:8000/ui/login).
- Inicio de la aplicación: [http://localhost:8000/ui/](http://localhost:8000/ui/).
- Estado del proceso: `GET /health`.
- Estado de la base de datos: `GET /api/health/db`.
- Documentación de endpoints: [http://localhost:8000/docs](http://localhost:8000/docs).

Las vistas `/ui/*` requieren sesión salvo login/logout. El acceso a pantallas y operaciones depende de los permisos del usuario; los controles se implementan en [app/main.py](app/main.py) y [app/api/deps_auth.py](app/api/deps_auth.py).

Antes de iniciar otra instancia, comprobar si el puerto 8000 está ocupado. Si una recarga queda pendiente, revisar los logs y reiniciar solo la instancia del proyecto. Comprobar también el endpoint modificado: que responda el login o un archivo estático no demuestra que la API haya cargado el código nuevo.

<a id="modulos"></a>

## Módulos y flujos

### Artículos y planos

El catálogo de artículos está en `producto`: el código se guarda en `codigo` y el nombre en `nombre`.

La vista [Planos de artículos](http://localhost:8000/ui/planos-articulos) consulta `GET /api/productos/planos`. La asociación se resuelve en [articulo_plano_service.py](app/services/articulo_plano_service.py):

- Relaciona los cuatro dígitos finales del código del artículo con el número base del plano disponible en el catálogo PDF.
- Admite varios artículos por plano y varias revisiones de un mismo PDF.
- Incluye código, nombre, descripción disponible y relaciones con productos mediante MBOM.
- El historial de Access reutiliza estas asociaciones; no obtiene el nombre de las observaciones ni usa un catálogo alternativo.

El plano `539` de Access se normaliza a `0539` para la búsqueda y la visualización. Los números de cinco dígitos se conservan sin truncarlos; no se deben asociar a un plano diferente tomando solo sus últimas cifras.

### Recepción e inspección de materiales

| Pantalla | Ruta |
| --- | --- |
| Nueva recepción | `/ui/recepcion` |
| Controles recientes | `/ui/recepcion/controles` |
| Pendientes de calidad | `/ui/recepcion/calidad` |
| Historial de Access | `/ui/recepcion/historial-access` |

La recepción operativa registra ingresos e inspecciones en MariaDB/MySQL mediante [recepcion_operativa_service.py](app/services/recepcion_operativa_service.py). Incluye control de calidad, muestreo e intentos de inspección; revisar las migraciones asociadas antes de habilitar estas funciones en otra instalación.

El historial consulta Access en modo solo lectura mediante [access_read_service.py](app/services/access_read_service.py). Es un recorrido distinto de la recepción operativa y del staging de importación.

| Campo de Access | Significado |
| --- | --- |
| `ID_INT` | Identificador del control, usado para abrir su detalle |
| `N_interno` | Número de inspección mostrado en el listado |
| `PLANO` | Número de plano usado para asociar artículos |
| `Lote` | Cantidad ingresada |
| `Material` | Material informado en origen |
| `NOTA` | Observaciones; no es el nombre del artículo |

El listado muestra la fecha de control sin hora, código y nombre del artículo, cantidad, OC/remito y estado. Las columnas se pueden reordenar y redimensionar; las preferencias se guardan en el navegador y se pueden restablecer con **Restablecer columnas**. Las consultas históricas tienen caché breve y pueden tardar por la conexión ODBC.

### Importaciones de Access y evaluación

Hay recorridos separados para importar datos a staging, normalizarlos, calcular métricas y evaluar proveedores. El servicio [recepcion_access_snapshot_service.py](app/services/recepcion_access_snapshot_service.py) también permite guardar versiones de origen de `CONTROL DE RECEPCION`, `CRD` y `CRD-ORI`, conservando identidad y contenido original; un snapshot no equivale a crear recepciones canónicas.

Para validar recepción y evaluación, consultar [la guía del flujo](docs/VALIDACION_EVALUACION_PROVEEDORES.md) y contrastar sus ejemplos con los endpoints actuales de `/docs`. Para el importador de snapshots, revisar [scripts/ops/importar_snapshot_access.py](scripts/ops/importar_snapshot_access.py).

### MBOM y costos

El flujo permite crear una revisión BORRADOR, cargar componentes y operaciones, calcular costos, activar la revisión y clonar una revisión activa para continuar editando. La activación archiva revisiones activas anteriores.

El cálculo distingue materiales y procesos. Las reglas y ejemplos se documentan en [Modelo de costos discriminados](docs/costos_discriminados.md); la lógica se encuentra en `app/services/mbom_service.py`, `mbom_costos.py` y `mbom_operacion_service.py`.

### Planificación, stock, precios y administración

El repositorio incluye planificación mensual y variaciones, importación de stock, historial e importación de precios, proveedores, evaluación, informes y tipo de cambio. También incluye usuarios, roles, permisos por pantalla, backups y actualización remota. Consultar los endpoints disponibles en `/docs` y [app/api/router.py](app/api/router.py), en lugar de asumir que estos módulos están pendientes.

<a id="csv"></a>

## Corrección de nombres desde CSV

El script [corregir_nombres_articulos_csv.py](scripts/ops/corregir_nombres_articulos_csv.py) compara `Código;Descripción` con el catálogo local. Lee UTF-8 o CP1252, valida nombres y códigos duplicados y genera un reporte JSON con valores anteriores y nuevos.

Primero comparar:

```powershell
.\.venv\Scripts\python.exe scripts/ops/corregir_nombres_articulos_csv.py TEMP/Articulos.csv
```

Después de revisar el reporte, aplicar las correcciones:

```powershell
.\.venv\Scripts\python.exe scripts/ops/corregir_nombres_articulos_csv.py TEMP/Articulos.csv --apply
```

La aplicación usa una transacción y verifica los nombres tras guardar. Los reportes se escriben por defecto en `TEMP/correccion_nombres/`. Los códigos inexistentes quedan informados; no se crean artículos ni se modifican códigos. Cuando un código tiene mojibake, solo se utiliza su variante corregida para buscar una coincidencia inequívoca.

<a id="validacion"></a>

## Validación y desarrollo

Ejecutar desde la raíz con el entorno del repositorio:

```powershell
.\.venv\Scripts\python.exe -m ruff check app/services/access_read_service.py app/services/articulo_plano_service.py
.\.venv\Scripts\python.exe -m pytest tests/test_access_article_names.py tests/test_articulo_plano_service.py tests/test_access_read_service.py -q
node --check app/static/js/recepcion_access_history.js
```

Son ejemplos para el flujo de historial y planos. Elegir las pruebas según el módulo modificado. La suite también cubre permisos, auth, recepción operativa, importaciones, snapshots, muestreo y tipo de cambio. Para ejecutar todas las pruebas: `.venv\Scripts\python.exe -m pytest`.

Las tasks de VS Code incluyen **Run API (uvicorn)**, **Lint (ruff)**, **Format (black)** y **Test (pytest)**. Evitar reformatear archivos ajenos al cambio. Mantener el flujo `endpoint -> service -> database`, consultas parametrizadas y validaciones de negocio en servicios.

Los archivos de código y documentación usan UTF-8. En PowerShell, configurar `$OutputEncoding` en UTF-8 antes de enviar texto con acentos a otro proceso por un pipe. Para antecedentes de caracteres dañados, revisar [producto_service.py](app/services/producto_service.py) y [sus pruebas de mojibake](tests/test_producto_mojibake.py).

<a id="operacion"></a>

## Operación y despliegue

La organización de herramientas está en [scripts/README.md](scripts/README.md) y la referencia operativa en [scripts/ops/README.md](scripts/ops/README.md).

- Instalación de Raspberry Pi: [scripts/ops/install_raspberry.sh](scripts/ops/install_raspberry.sh).
- Despliegue desde Windows: [scripts/ops/deploy_raspberry.ps1](scripts/ops/deploy_raspberry.ps1).
- Actualización desde Git: [scripts/ops/update.sh](scripts/ops/update.sh).
- Migraciones y comprobaciones posteriores: [scripts/ops/post_deploy_raspberry.sh](scripts/ops/post_deploy_raspberry.sh).

Antes de usar scripts históricos de instalación o despliegue, revisar las rutas calculadas y referencias internas tras su traslado a `scripts/ops`, las variables exigidas y la configuración del destino. No usar credenciales de ejemplo ni reinicializar una base existente para actualizar código.

El servicio de Raspberry se consulta con:

```bash
sudo systemctl status compras-api
sudo journalctl -u compras-api -f
```

La API expone `GET /api/system/update-status` y `POST /api/system/update` para consultar y ejecutar actualizaciones, sujetos a permisos. El actualizador puede ejecutar `git reset --hard` contra la rama configurada: preservar los cambios locales antes de utilizarlo. Comprobar el proceso, la base de datos y el flujo afectado después de desplegar.

<a id="documentacion"></a>

## Documentación relacionada

| Guía | Contenido |
| --- | --- |
| [Instrucciones para agentes](agents.md) | Convenciones, arquitectura y reglas del workspace |
| [Modelo de costos MBOM](docs/costos_discriminados.md) | Cálculos de materiales y procesos |
| [Recepción y evaluación](docs/VALIDACION_EVALUACION_PROVEEDORES.md) | Validación del flujo de proveedores |
| [Organización de scripts](scripts/README.md) | Separación entre operación y desarrollo |
| [Operación y mantenimiento](scripts/ops/README.md) | Administración y herramientas de despliegue |

---

[Volver al inicio](#sistema-de-compras-y-planificación)

Última actualización: **5 de noviembre de 2026**. Versión: [VERSION](VERSION), leída por [app/core/version.py](app/core/version.py).
