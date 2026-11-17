# Carga integral de materiales desde Excel

Acceso: **Wizard OC → Cargar todo desde Excel** (`/ui/plan-asistente-oc#wizard-excel`).

## Uso

1. Elegir el período y descargar la plantilla completa.
2. Completar las hojas y las tres fechas de corte. Mantener códigos como texto y cantidades como números de Excel, sin fórmulas. Escribir cero si corresponde; las celdas vacías no se interpretan como cero.
3. Seleccionar el archivo y pulsar **Validar archivo completo**. La pantalla muestra los errores por hoja/fila o el resumen previo.
4. Revisar período, stock base y lista LAF. Pulsar **Confirmar carga y calcular materiales** y aceptar la confirmación.
5. Revisar el requerimiento y las alertas del paso 5. El cálculo no guarda sugerencias ni emite órdenes de compra.

## Hojas

| Hoja | Datos y reglas |
| --- | --- |
| Instrucciones | Guía de uso y alcance de la carga. No se importa. |
| Parametros | Versión 1, año/mes del plan, fechas de corte MP/PT/deuda y `sin_laf=SI/NO`. La fecha MP debe corresponder al mes anterior al plan, que es la base usada por el cálculo existente. |
| Plan_PT | Códigos de todos los PT activos, nombre y unidad de referencia, cantidad planificada. |
| Stock_MP | Todos los materiales y componentes activos del catálogo que no son PT, con stock en su unidad del sistema. |
| Stock_PT | Todos los PT activos y su stock disponible. |
| Deuda_Clientes | Todos los PT activos y cantidades pendientes de fabricar/entregar. |
| LAF_Solicitado | Pedidos previos de MP LAF activas: proveedor, total, Q1/Q2, fechas opcionales, estado y observaciones. Varios pedidos distintos pueden compartir código. |

La descarga incorpora los códigos, nombres y unidades reales y los valores ya guardados cuando existen para ese período. Las cantidades no disponibles quedan vacías. Las fechas de corte se precargan solo si los registros existentes tienen una fecha única. El nombre es informativo: esta carga no crea artículos ni modifica nombres, códigos, unidades o MBOM.

Para confirmar que no hay pedidos LAF, dejar su hoja vacía y escribir `SI` en `sin_laf`. Si hay filas LAF, usar `NO`. Las quincenas no pueden sumar más que el total; no se reinterpreta el total de pedidos parciales como un saldo recibido independiente. El futuro lote de saldos LAF sigue separado.

## Qué se actualiza

Plan, stock MP, stock PT y deuda se actualizan por período/producto mediante upsert. Se exige cobertura completa del catálogo activo de cada hoja para evitar omisiones silenciosas. La lista **LAF del período se reemplaza completa**, previa vista previa y confirmación, para que reimportar un archivo no duplique pedidos. Las sugerencias existentes y el historial de corridas no se modifican. El stock MP se guarda en el mes anterior al plan; los otros listados, en el mes del plan.

Todas las escrituras y la simulación usan una única transacción: si falla una hoja, una consulta o el cálculo, se hace rollback de la carga completa, incluida la lista LAF previa. No se utilizan los importadores individuales que hacen commits por separado. Se reutiliza el cálculo de `plan_produccion_service.calcular_asistente_oc` con `persistir_sugerencias=False`.

El catálogo, las unidades y la MBOM deben existir en el sistema. El Excel reúne las entradas del Wizard; no reemplaza la configuración de estructuras o capacidades.

## Validación y permisos

- XLSX de hasta 20 MB; ZIP descomprimido de hasta 60 MB y 2.000 entradas; hasta 10.000 filas por hoja.
- Encabezados y hojas obligatorios; cantidades finitas, no negativas, hasta seis decimales y dentro de `DECIMAL(18,6)`.
- Rechazo de fórmulas, errores de Excel, macros, vínculos externos, códigos desconocidos/inactivos, unidades distintas y duplicados. Longitudes LAF alineadas con el esquema.
- Hasta 100 errores detallados en pantalla y contador total.
- Vista previa sin escrituras. Confirmación firmada, válida durante 30 minutos y vinculada al usuario, al archivo exacto y al estado de los cinco listados y el catálogo. Si cambian, hay que volver a validar. La importación bloquea las filas/rangos del período con `FOR UPDATE` antes de comprobar el estado.
- Descargar y validar requiere lectura de `ui_plan_asistente_oc`. Guardar requiere escritura de esa pantalla y de `ui_plan_mensual` o `ui_plan`. El permiso de Wizard ya habilita la carga de stock en el flujo existente.
- POST desde el mismo origen, respuestas sin caché y confirmación explícita. El contenido del archivo no se envía a OpenAI. El asistente conversacional puede ofrecer la acción `excel_integral`, que lleva al formulario sin guardar ni enviar el archivo.

## Implementación

| Capa | Archivos / endpoints |
| --- | --- |
| API | `app/api/wizard_excel.py`: `GET /api/plan-produccion-mensual/asistente-oc/archivo-integral/plantilla.xlsx`, `POST /validar`, `POST /importar` bajo ese prefijo |
| Servicio | `app/services/wizard_excel_service.py` |
| Esquemas | `app/schemas/wizard_excel.py` |
| Plantilla | `app/resources/plantilla_integral_wizard_oc.xlsx`, contrato de columnas en `wizard_oc_columnas.json` |
| UI | `plan/wizard_excel.html`, `wizard_excel.js` e integración en `plan_asistente_oc.html` |
| Generación base | `scripts/dev/crear_plantilla_integral_wizard.mjs`, con Artifact Tool del runtime; la API completa el archivo con openpyxl, dependencia existente del proyecto |

Sin tablas ni migraciones nuevas. Esquema real y migraciones 006–008 revisados antes de implementar. No se alteraron los importadores individuales.

## Validaciones ejecutadas el 13/11/2026

- **101 pruebas Python aprobadas**: 34 de la carga integral y regresión de conversación, cálculo y permisos. Los tests transaccionales usan SQLite aislado con adaptación de sintaxis MySQL solo en tests; comprueban commit único, rollback real, preservación de LAF previos, repetición sin duplicados y rechazo de confirmaciones de otro archivo/usuario, vencidas o con datos cambiados. No sustituyen una prueba de concurrencia contra MariaDB.
- **15 pruebas Node aprobadas**, incluidas cinco de validación/confirmación del formulario, permisos de lectura, invalidación y doble envío.
- Ruff y sintaxis JavaScript externo e integrado correctos. Jinja renderizado con usuario ficticio local.
- Excel final exportado y revisado con Artifact Tool: siete hojas, códigos textuales, encabezados, paneles congelados y ausencia de errores de fórmulas. Revisión visual de cada hoja; se corrigieron anchos y ajuste de nombres largos.
- Formulario renderizado sin red en Edge headless, escritorio y móvil. Esto verifica el diseño, no una sesión autenticada de producción.
- Plantilla descargable generada con **lectura real** de la base para 11/2026: 50 PT y 930 materiales/componentes. No se cargaron ni alteraron datos comerciales para probarla.
- Instancia reiniciada en segundo plano con la cuenta de Windows del proyecto (PID de arranque 6752). `/health` 200, recurso JS 200 y tres endpoints confirmados en OpenAPI. Descarga sin sesión devuelve 401.

Pendiente: el usuario debe completar y confirmar un archivo real. No se ejecutó una carga integral contra MariaDB ni se emitieron OC ni se enviaron datos comerciales a un proveedor externo.
