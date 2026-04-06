# Sistema de Compras y Planificación

Proyecto orientado a la gestión de estructuras de producto (MBOM), planificación mensual de producción, cálculo de requerimientos de materiales, seguimiento de costos y soporte para análisis con IA.

## Tecnologías

- Backend: Python 3 + FastAPI
- Base de datos: MariaDB/MySQL (`database/schema.sql`)
- ORM ligero / acceso: SQLAlchemy (uso de `Session` + sentencias `text()` parametrizadas)
- Frontend: Plantillas Jinja2 + JavaScript vanilla (fetch API)
- Gestión de dependencias: `requirements.txt`

## Estructura del Proyecto

```
app/
  main.py              # Punto de entrada FastAPI
  db.py                # Conexión y dependencia de sesión
  api/                 # Routers (endpoints REST y vistas UI)
    mbom_api.py        # Endpoints MBOM (estructura, costos, revisión)
    productos.py       # CRUD básico productos
    unidades.py        # Listado unidades de medida
    plan.py            # Plan producción mensual (stub inicial)
    stock.py           # Importación/visualización de stock (stub)
    ... ui_*           # Vistas HTML
  services/            # Lógica de negocio
    mbom_service.py    # Operaciones MBOM cabecera/detalle
    mbom_costos.py     # Cálculo de costos discriminados (materiales + procesos)
    operacion_service.py        # CRUD operaciones (catálogo)
    mbom_operacion_service.py   # Gestión rutas de operaciones
    producto_service.py
    unidad_service.py
    plan_service.py
    stock_import_service.py (futuro origen ERP externo)
  schemas/             # Modelos Pydantic (serialización)
  templates/           # HTML Jinja2 (ej: mbom/estructura.html)
  static/              # CSS/JS estáticos (si se agregan)
database/
  schema.sql           # Definición completa del schema
import/                # Archivos fuente de importaciones (CSV/Excel futuros)
```

## Principales Tablas (según `schema.sql`)

- `producto`: catálogo maestro (tipos: PT, WIP, MP, EMB, SERV, HERR)
- `unidad_medida`: unidades base (kg, un, m, etc.)
- `mbom_cabecera`: revisiones de la estructura (estado: BORRADOR, ACTIVO, ARCHIVADO)
- `mbom_detalle`: componentes de la estructura con cantidad, UM, merma y renglón
- `operacion`: catálogo de operaciones/procesos con tiempo estándar y costo por hora
- `mbom_operacion`: secuencia de operaciones (ruta) asociada a cada MBOM
- `costo_producto`: historial de costos unitarios vigentes por producto
- `plan_produccion_mensual`: cantidades planificadas de PT/WIP por mes
- `requerimiento_material_mensual`: cálculo consolidado de necesidades de componentes
- `stock_disponible_mes`: stock histórico / importado por mes
- `sugerencia_compra`: resultado del análisis de faltantes vs disponibilidad
- `precio_compra_hist`: historial de precios de compra por proveedor
- `reporte_ia`: almacenamiento de reportes generados vía integración IA

## Flujo MBOM (Manufacturing BOM)

1. Seleccionar o crear producto padre (tipo PT o WIP) desde la vista `mbom/estructura`.
2. Si no existe MBOM ACTIVO para el producto, se crea BORRADOR inicial.
3. Agregar líneas (componentes) mediante el selector modal.
4. Guardar cada línea (valida cantidad > 0, merma [0,1), UM y componente válido).
5. Calcular costos: endpoint obtiene costos unitarios vigentes de cada componente.
6. Activar revisión (BORRADOR -> ACTIVO archiva anteriores activas).
7. Clonar revisión ACTIVA para generar un nuevo BORRADOR editable (incrementa `revision`: A, B, C...).
8. Archivar manualmente si se desea retirar una revisión de uso.

## Endpoints Clave (Resumen)

Ruta base API: `/api`

MBOM:

- `GET /api/mbom/{producto_padre_id}?estado=ACTIVO|BORRADOR` → Estructura preferida.
- `POST /api/mbom/{producto_padre_id}` → Upsert de líneas en BORRADOR (crea si falta).
- `PUT /api/mbom/{mbom_id}` → Actualizar cabecera + líneas.
- `DELETE /api/mbom/detalle/{detalle_id}` → Borrar línea.
- `GET /api/mbom/{mbom_id}/costos` → Cálculo de costos discriminados (materiales + procesos).
- `POST /api/mbom/{mbom_id}/activar` → Activa revisión (archiva anterior ACTIVO).
- `POST /api/mbom/{mbom_id}/clonar` → Clona revisión a nuevo BORRADOR.
- `POST /api/mbom/demo/{codigo}` → Genera demo de MBOM con componentes MP.

Operaciones (Ruta de Procesos):

- `GET /api/operaciones/?activo=true` → Lista catálogo de operaciones.
- `POST /api/operaciones/` → Crear nueva operación.
- `PUT /api/operaciones/{id}` → Actualizar operación existente.
- `DELETE /api/operaciones/{id}` → Eliminar operación.
- `GET /api/mbom/{mbom_id}/operaciones` → Listar operaciones de una ruta MBOM.
- `POST /api/mbom/{mbom_id}/operaciones` → Agregar operación a ruta (secuencia + operacion_id).
- `DELETE /api/mbom/operaciones/{id}` → Eliminar operación de ruta.

Productos / Unidades:

- `GET /api/productos/?q=...&tipo=...&activo=...` → Listado filtrado.
- `POST /api/productos/` → Crear producto.
- `GET /api/unidades/` → Listar unidades.

(Planificación, stock y compras tendrán endpoints adicionales en próximas iteraciones.)

## Modelo de Costos Discriminados

El sistema calcula costos discriminados en dos componentes principales:

### Costos de Materiales

- Se toma el costo vigente por componente (`costo_producto` con `vigencia_desde <= hoy` y `vigencia_hasta` nula o futura).
- Costo total línea = `cantidad * costo_unitario * (1 + factor_merma)`
- Suma total materiales = agregación de todas las líneas de componentes.

### Costos de Procesos (Operaciones)

- Tabla `operacion`: catálogo de operaciones con `costo_hora` y `tiempo_estandar_minutos`
- Tabla `mbom_operacion`: secuencia de operaciones asociadas a cada MBOM
- Costo operación = `(tiempo_estandar_minutos / 60) * costo_hora`
- Suma total procesos = agregación de todas las operaciones en la ruta

### Estructura de Respuesta de Costos

```json
{
  "materiales": {
    "componentes": [...],
    "total": 0.00
  },
  "procesos": {
    "operaciones": [...],
    "total": 0.00
  },
  "total": 0.00,
  "desglose": {
    "materiales_pct": 0.00,
    "procesos_pct": 0.00
  }
}
```

## Requerimientos y Sugerencias de Compra (Futuro)

1. A partir del `plan_produccion_mensual` + MBOM ACTIVA → explotar cantidades de componentes.
2. Consolidar necesidades mensuales → `requerimiento_material_mensual`.
3. Cruzar con `stock_disponible_mes` → calcular faltantes.
4. Generar `sugerencia_compra` (cantidad necesaria - stock disponible) con estados gestionables.

## Integración ERP Externo (Pendiente)

- Importar CSV/Excel de stock y precios.
- Mapear códigos externos a `producto.codigo` (validación y reporte de diferencias).
- Registrar origen definido en el schema (valor enum correspondiente) en tablas de stock y precios históricos.

## Integración IA (Pendiente)

- Resúmenes de variación de costos, tendencias de precios, análisis de cobertura de stock.
- Generar reportes y almacenar texto en `reporte_ia`.
- Servicio encargado de: preparar dataset → prompt → llamada API OpenAI → persistencia.

## Instalación

Prerrequisitos:

- Python 3.11+
- MariaDB 11.x

MariaDB (crear base y usuario):

```sql
CREATE DATABASE compras_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'compras'@'%' IDENTIFIED BY 'TU_PASSWORD_SEGURA';
GRANT ALL PRIVILEGES ON compras_db.* TO 'compras'@'%';
FLUSH PRIVILEGES;
```

Aplicar el schema:

```bash
mysql -u compras -p compras_db < database/schema.sql
```

Backend:

```powershell
# Crear entorno virtual
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
# Variables de entorno (ejemplo)
setx DB_HOST 127.0.0.1
setx DB_NAME compras_db
setx DB_USER compras
setx DB_PASS TU_PASSWORD_SEGURA
```

### Instalador Automático para Raspberry Pi

Se incluye un instalador para dejar listo entorno, base de datos y servicio `systemd` en un solo paso.

Archivo: `scripts/install_raspberry.sh`

Uso rápido (modo schema):

```bash
cd ~/COMPRAS
chmod +x scripts/install_raspberry.sh
DB_USER=acepeda DB_PASS=2211 DB_INIT_MODE=schema DB_RESET=true ./scripts/install_raspberry.sh
```

Uso con clon completo de datos (dump):

```bash
cd ~/COMPRAS
chmod +x scripts/install_raspberry.sh
DB_USER=acepeda DB_PASS=2211 DB_INIT_MODE=dump DB_RESET=true DUMP_FILE=~/COMPRAS/backups_local_dump.clean.sql ./scripts/install_raspberry.sh
```

Variables soportadas:

- `APP_USER` (default: usuario actual)
- `DB_NAME` (default: `compras_db`)
- `DB_USER` (default: `acepeda`)
- `DB_PASS` (default: `2211`)
- `DB_HOST` (default: `127.0.0.1`)
- `DB_PORT` (default: `3306`)
- `DB_INIT_MODE` (`schema` o `dump`, default: `schema`)
- `DB_RESET` (`true`/`false`, default: `false`)
- `DUMP_FILE` (ruta del dump cuando `DB_INIT_MODE=dump`)
- `CREATE_SERVICE` (`true`/`false`, default: `true`)
- `WRITE_ENV` (`true`/`false`, default: `true`)
- `INSTALL_PACKAGES` (`true`/`false`, default: `true`)

Comandos de control del servicio:

```bash
sudo systemctl status compras-api
sudo systemctl restart compras-api
sudo journalctl -u compras-api -f
```

### Deploy rápido desde Windows a Raspberry

Para actualizar código en una Raspberry y reiniciar el servicio sin entrar archivo por archivo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_raspberry.ps1 -Host compras-dev
```

Opciones útiles:

```powershell
# Incluir carpeta database en el deploy
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_raspberry.ps1 -Host compras-dev -IncludeDatabase

# Ejecutar también el instalador remoto luego de copiar archivos
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_raspberry.ps1 -Host compras-dev -RunInstaller
```

El script:

- empaqueta `app/`, `requirements.txt`, `requirements-dev.txt` y `scripts/install_raspberry.sh`
- copia el paquete a la Raspberry por `scp`
- descomprime en el proyecto remoto
- reinicia `compras-api`
- valida que `/ui/login` responda `200`

## Ejecución

```powershell
.\.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Acceso UI: `http://localhost:8000/ui/mbom`

## Seguridad y Buenas Prácticas

- No almacenar credenciales en el código (usar `.env` / variables entorno).
- Consultas SQL parametrizadas (`text()` + dict) para evitar inyección.
- Validaciones en servicio antes de persistir (ej.: cantidades > 0, merma < 1).
- Estados controlados por enumeraciones del schema (evitar valores mágicos).

## Flujo Típico de Usuario (MBOM)

1. Abrir vista MBOM.
2. Buscar producto PT existente o crear nuevo rápido.
3. Cargar estructura; si no hay ACTIVO se crea BORRADOR.
4. Agregar componentes mediante modal → ajustar cantidades/UM/merma.
5. Guardar líneas y verificar costos.
6. Grabar todo y activar revisión para uso en cálculos.
7. Clonar cuando se requiera nueva modificación sin tocar la activa.

## Funcionalidades Implementadas

✅ **Gestión de MBOM (Bill of Materials)**

- CRUD completo de estructuras de producto con revisiones
- Estados: BORRADOR → ACTIVO → ARCHIVADO
- Clonación de revisiones para nuevas versiones
- Selector modal de componentes con búsqueda

✅ **Cálculo de Costos Discriminados**

- Costos de materiales (componentes + merma)
- Costos de procesos (operaciones × tiempo × costo/hora)
- Desglose porcentual materiales vs procesos
- Panel con tabs: Materiales | Procesos | Total

✅ **Gestión de Operaciones (Rutas de Proceso)**

- Catálogo de operaciones con tiempo estándar y costo/hora
- Asignación de secuencia de operaciones a cada MBOM
- Cálculo automático de costos de proceso
- UI integrada con selector modal y CRUD en línea
- Plantillas reutilizables de rutas de operación (guardar, listar y aplicar)
- Aplicación masiva de rutas con modo reemplazo/apéndice y control de secuencias

✅ **Interfaz de Usuario Optimizada**

- Tabla responsive con ajuste dinámico de altura
- Columnas redimensionables manualmente
- Sticky headers para mejor navegación
- Búsqueda y filtrado de productos (hasta 500 registros)
- Creación rápida de productos desde la UI
- Mensajes persistentes y seleccionables para operaciones y costos
- Resaltado automático en amarillo de materiales sin costo cargado

## Avances recientes

### Diciembre 2025

- **Plan de Producción Mensual**: ahora editable en tabla completa, con navegación por Enter y edición rápida de cantidades para todos los productos terminados (PT) activos.
- **Importación/Exportación masiva**: soporte para cargar y descargar el plan mensual en formato Excel/CSV, con plantilla de ejemplo y validación de datos.
- **Análisis de variación**: resumen de diferencias entre plan actual y anterior, con visualización de variaciones por producto y totales.
- **Mejoras de usabilidad**:
  - Navegación con Enter entre celdas de la tabla.
  - Al enfocar la celda de cantidad, si el valor es 0, se limpia automáticamente para agilizar la carga.
  - Feedback visual tras guardar/importar/exportar.
- **Refactor backend**:
  - Endpoints para resumen, edición masiva, importación y descarga de plantilla.
  - Validaciones robustas y mensajes claros de error.
  - Alineación estricta con el schema de base de datos.
- **Documentación**: actualización de este README y plantillas de importación.

### Anteriores

- Integración de IA (OpenAI) para generación de reportes y análisis automáticos.
- Importación de stock y precios desde ERP Flexxus (CSV/Excel).
- Limpieza de archivos y refactorización de servicios no utilizados.
- Mejoras en la interfaz: feedback visual tras guardar, editar o eliminar planes, y autocompletado de productos por código/nombre.
- Validaciones robustas: no duplicar producto+mes+año, cantidad > 0, mensajes claros de error.
- Documentación y estructura del proyecto actualizada.

## Próximos Pasos

- Implementar importación de datos externos (`/api/mbom/{producto_id}/importar-flexxus`).
- Vincular materiales a operaciones específicas (`mbom_detalle.operacion_secuencia`).
- Explotación MBOM + plan mensual para requerimientos materiales.
- Generación automática de sugerencias de compra.
- Endpoints de reportes IA y summaries comparativos.
- Manejo de alternativas (`mbom_alternativa`) y efectividad (`mbom_detalle_efectividad`).
- Historial de costos de operaciones (similar a `costo_producto`).
- Tests unitarios de servicios clave (cálculo costos, activación/clonado, validación cantidades).

## Git / Versionado

Inicializado repositorio local. Para publicar remoto:

```powershell
git remote add origin https://github.com/ORG/REPO.git
git push -u origin master   # o main si se renombra
```

Renombrar branch si se desea:

```powershell
git branch -m master main
git push -u origin main
```

## Convenciones

- `snake_case` para funciones/variables.
- `PascalCase` modelos Pydantic y clases.
- Revisiones MBOM: secuencia alfabética simple (A, B, C...).
- Renglones: múltiplos de 10 para permitir inserciones futuras.

## Contacto / Mantenimiento

Documentar cambios relevantes en este README y mantener sincronizados los scripts de migración si se altera el schema.

---

**Última actualización:** 8 de diciembre de 2025  
**Versión:** 0.3.0 - Plan de Producción Mensual editable, importación/exportación masiva y análisis de variación

## Cambios recientes (13 de febrero de 2026)

Resumen de cambios aplicados en esta sesión de desarrollo:

- Autenticación y autorización:
  - Añadido soporte para usuarios, roles, sesiones y permisos por formulario.
  - Endpoints: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`.
  - Script de semilla: `scripts/seed_admin.py` para crear usuario administrador y permisos iniciales.
  - Archivo de migración inicial para auth (ver `database/migrations/`).

- Protección de endpoints (guards):
  - Se aplicó la dependencia `require_permission` en routers clave para forzar permisos por formulario:
    - `app/api/stock.py`, `app/api/precios.py`, `app/api/tipo_cambio.py`, `app/api/unidades.py`, `app/api/mbom_api.py`, `app/api/informes.py`, `app/api/plan.py`.

- Frontend / UX:
  - Plantilla de login actualizada en `app/templates/auth/login.html` para mostrar mensajes de error legibles (evita "[object Object]").

- Servicios y utilidades:
  - Nuevo servicio de autenticación en `app/services/auth_service.py` (hashing, JWT, sesiones).
  - Dependencias y esquemas añadidos en `app/schemas` y `app/api/deps_auth.py`.

- Dependencias:
  - Actualizado `requirements.txt` para incluir `passlib[bcrypt]`, `PyJWT`, `email-validator` y mantener compatibilidad con `bcrypt`.

## Cambios recientes (02 de marzo de 2026)

En esta sesión se completaron ajustes de permisos y la interfaz para respetar roles y privilegios de escritura/lectura.

- Frontend: controles y botones de acción deshabilitados cuando el usuario no tiene permiso de escritura. Plantillas actualizadas:
  - `app/templates/productos/index.html`
  - `app/templates/rubros/list.html`
  - `app/templates/mbom/estructura.html`
  - `app/templates/precios/historial.html`
  - `app/templates/stock/index.html`
  - `app/templates/plan/plan_mensual.html`

- UI: se añadió verificación en plantillas para evitar que usuarios con solo permiso de lectura vean o usen botones Crear/Editar/Importar/Guardar.

- Nota técnica: la verificación se realiza leyendo `current_user.permissions["<form_key>"]` (tupla `[leer, escribir]`) expuesta por la dependencia de autenticación en la capa de renderizado de plantillas.

- Mantenimiento: se dejó preparado un macro Jinja2 (por implementar) para centralizar esta lógica si se desea limpiar duplicación en múltiples plantillas.

Pruebas sugeridas:

1. Iniciar servidor y loguear como `admin@example.com` (o el admin creado con `scripts/seed_admin.py`). Verificar que los botones de creación/edición/importación estén habilitados.
2. Crear un usuario con permisos solo de lectura sobre `productos` y loguear: verificar que el formulario de alta y botones de edición estén deshabilitados.
3. Revisar la consola del navegador para asegurarse de que no se envían peticiones mutantes desde botones deshabilitados.

Si quieres, puedo (1) convertir la verificación en un macro Jinja2 reutilizable y aplicarlo automáticamente a las plantillas restantes, y (2) crear pruebas automáticas básicas para la autorización.
Archivos modificados (ejemplos):

- `app/templates/auth/login.html`
- `app/api/deps_auth.py`
- `app/services/auth_service.py`
- `app/api/auth.py`
- `scripts/seed_admin.py`
- `app/api/stock.py`, `app/api/precios.py`, `app/api/tipo_cambio.py`, `app/api/unidades.py`, `app/api/mbom_api.py`, `app/api/informes.py`, `app/api/plan.py`

Comandos rápidos para probar localmente:

```powershell
# (desde la raíz del proyecto, con venv activado)
python scripts/seed_admin.py --email admin@example.com --password admin123 --nombre "Admin"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Probar login (dev):
curl -i -c cookies.txt -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"admin123"}' http://127.0.0.1:8000/api/auth/login

# Probar endpoint protegido usando la cookie recibida:
curl -b cookies.txt http://127.0.0.1:8000/api/stock/2025/01
```

Notas y recomendaciones:

- Asegúrate de aplicar las migraciones SQL que crean las tablas de `usuario`, `rol`, `usuario_rol`, `permiso_form` antes de ejecutar el `seed_admin.py`.
- Reinicia `uvicorn` cuando actualices plantillas para evitar caché de reloader en algunos entornos.
- Considerar agregar CSRF y rate-limiting para endpoints de autenticación y de importación de archivos en producción.

## Cambios recientes (13 de marzo de 2026)

### Módulo de administración de backups

Se agregó un módulo específico para administrar backups de base de datos desde UI y API.

- Vista UI (requiere permiso):
  - `GET /ui/admin/backups`

- Endpoints API:
  - `GET /api/backups/` → lista backups disponibles
  - `POST /api/backups/` → genera nuevo backup SQL
  - `GET /api/backups/{filename}/download` → descarga backup
  - `DELETE /api/backups/{filename}` → elimina backup
  - `POST /api/backups/restore` → sube archivo `.sql` y restaura la base actual

- Configuración:
  - `BACKUP_DIR` (opcional): directorio destino para los `.sql` (default `backups/`)
  - `MYSQLDUMP_PATH` (opcional): ruta explícita de `mysqldump` si no está en `PATH`
  - `MYSQL_CLIENT_PATH` (opcional): ruta explícita de `mysql` para restauración si no está en `PATH`
  - Desde la UI de backups también se puede elegir un directorio puntual por operación (incluye rutas de pendrive como `E:\Backups`).
  - La UI permite guardar directorios favoritos y programar backup automático por hora y días seleccionados.

- Permisos:
  - Nuevo `form_key`: `admin_backups`
  - Se muestra como opción en **Configuración** del menú superior para usuarios con acceso.

Ejemplo (Windows PowerShell):

```powershell
$env:BACKUP_DIR = "backups"
$env:MYSQLDUMP_PATH = "C:\\Program Files\\MariaDB 11.4\\bin\\mysqldump.exe"
$env:MYSQL_CLIENT_PATH = "C:\\Program Files\\MariaDB 11.4\\bin\\mysql.exe"
```

Notas:

- El directorio `backups/` está excluido de git en `.gitignore`.
- La pantalla `/ui/admin/backups` informa si `mysqldump` está disponible antes de permitir generar backups.
- La restauración es una operación destructiva: puede sobrescribir datos y causar pérdida de información posterior al backup.
- La UI exige confirmaciones explícitas de sobreescritura/pérdida de datos y el texto `RESTAURAR` antes de ejecutar.
- Programación automática: la app ejecuta un backup en los días seleccionados a la hora configurada en la pantalla de backups (se guarda en `parametro_sistema`).

