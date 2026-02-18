Copilot Instructions — Sistema de Compras (Python + FastAPI + MariaDB)

Arquitectura general

Este proyecto implementa un backend de planificación de compras usando
FastAPI y MariaDB.

Componentes principales:

-   app/main.py → punto de entrada FastAPI
-   app/api/ → routers HTTP organizados por recurso
-   app/services/ → lógica de negocio (cálculos, importaciones, IA)
-   app/models/ → modelos internos y acceso a datos
-   app/db.py → conexión a MariaDB/MySQL
-   database/schema.sql → definición completa del esquema (fuente de
    verdad)

El flujo típico es: API endpoint → service → database → response

Nunca acceder a la base directamente desde el endpoint.

Base de datos (crítico)

El esquema está definido en: database/schema.sql

Siempre: - Leer este archivo antes de usar tablas - Respetar PK, FK,
enums y checks existentes - Usar consultas parametrizadas - No modificar
estructura sin migración explícita

Tablas clave: - producto - plan_produccion_mensual -
stock_disponible_mes - requerimiento_material_mensual -
sugerencia_compra - precio_compra_hist

Estructura y convenciones

Usar esta estructura:

app/ main.py db.py api/ services/ models/ database/ schema.sql

Convenciones:

-   snake_case → funciones y variables
-   PascalCase → clases
-   Pydantic models → requests/responses
-   APIRouter → endpoints
-   lógica de negocio → services/
-   endpoints → solo validación y delegación

Frontend UI (/ui)

Stack: - FastAPI + Jinja2 templates - JavaScript vanilla (fetch API) -
CSS global en: app/static/css/estilos.css

Patrones: - endpoints JSON en /api - UI en /ui - CRUD via fetch →
POST/PUT/DELETE - tablas con atributos data-* para estado

Referencias: - app/templates/productos/index.html -
app/templates/rubros/list.html

Integraciones externas

ERP Flexxus: - importar datos desde CSV/Excel - mapear a
producto.codigo - usar services para lógica de importación

OpenAI: - integrar desde services/ - preparar datasets estructurados -
no llamar OpenAI desde endpoints directamente

Flujo de desarrollo esperado

Para nuevas funcionalidades:

1.  Usar /plan
2.  Identificar tablas afectadas
3.  Crear services primero
4.  Crear endpoints en api/
5.  Crear modelos Pydantic
6.  Integrar con UI si corresponde

Buenas prácticas obligatorias

Siempre: - usar type hints - usar logging - usar variables de entorno
para configuración - evitar hardcodear credenciales - manejar errores
correctamente - mantener separación endpoint / service / database

Nunca: - lógica de negocio en endpoints - modificar schema sin
análisis - concatenar SQL manualmente

Referencias clave del proyecto

Fuente de verdad de datos: database/schema.sql

Ejemplos de UI: app/templates/productos/index.html

Estilos globales: app/static/css/estilos.css
