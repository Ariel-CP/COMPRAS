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

✅ **Interfaz de Usuario Optimizada**
- Tabla responsive con ajuste dinámico de altura
- Columnas redimensionables manualmente
- Sticky headers para mejor navegación
- Búsqueda y filtrado de productos (hasta 500 registros)
- Creación rápida de productos desde la UI

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

**Última actualización:** 1 de diciembre de 2025  
**Versión:** 0.2.0 - Sistema de costos discriminados con rutas de operaciones
