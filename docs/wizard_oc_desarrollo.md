# Desarrollo incremental de Wizard OC

## Carga integral desde Excel — 2026-11-13

Nuevo acceso **Cargar todo desde Excel**: plantilla de siete hojas (instrucciones, parámetros y cinco listados), catálogo real, validación completa, confirmación firmada y guardado/cálculo atómicos. El asistente puede ofrecer la acción `excel_integral`. Sin migraciones ni envíos del archivo a IA. Ver [contrato, uso, permisos, reemplazo de LAF y validación](WIZARD_EXCEL_INTEGRAL.md). Pruebas del avance: 101 Python y 15 Node aprobadas, más revisión visual del Excel y del formulario. No se importó un archivo comercial real.

## Asistente conversacional de requerimientos — 2026-11-13

El pedido actual amplía la guía local: se implementó conversación con OpenAI en **Wizard OC → Asistente IA para requerimientos**, ancla `/ui/plan-asistente-oc#wizard-chat`. La guía por reglas y el prototipo de consultas libres anteriores se conservan desplegados como opciones secundarias.

### Comportamiento implementado

La IA pide datos y devuelve un mensaje con una acción de una lista cerrada: seleccionar período, cargar plan, navegar a stock MP/LAF/PT/deuda, importar el archivo seleccionado, simular o revisar. El usuario aplica cada acción con un botón; importar exige confirmación adicional porque guarda información. Los importadores, servicios, permisos y cálculo existentes realizan la operación. La IA no ejecuta SQL, código ni cálculos de materiales ni emite órdenes. La simulación fuerza `persistir_sugerencias=false`. Se rechaza calcular con un plan cargado para otro período.

Cada turno tiene vista previa y confirmación explícita. Se envían mensaje, historial visible y metadatos cerrados: período, paso, números de registros y última acción/resultado del navegador. No se envían archivos, códigos, nombres ni cantidades automáticamente. El texto libre no se anonimiza: puede contener información comercial si el usuario la escribe y confirma. Se muestra esta limitación. Los mensajes permanecen en memoria de la página (hasta 30 mensajes de historial, además del límite de tamaño); no se guardan en la base ni en logs de la aplicación. Se usa Responses con `store=false`, lo que no garantiza ausencia de registros del proveedor.

### Configuración y límites

La habilitación `wizard_conversacional` es independiente de la política general anterior, que sigue bloqueando el endpoint genérico `/asistente-oc/ia`. El nuevo endpoint está en `/api/plan-produccion-mensual/asistente-oc/ia/conversacion`, con `/estado` para disponibilidad. Ambos requieren lectura de `ui_plan_asistente_oc`; las escrituras de importación conservan sus permisos propios. Se comprueba el origen de los POST y se responde con `Cache-Control: no-store`. El servidor valida entrada y salida con Pydantic; las acciones no se ejecutan en el endpoint de conversación.

Se conservó `gpt-4o-mini` y la clave cifrada existentes. Por el pedido actual se habilitó el asistente localmente, sin realizar envíos. Se configuraron USD 0,15 de entrada y USD 0,60 de salida por millón de tokens, según [OpenAI Docs](https://developers.openai.com/api/docs/models/gpt-4o-mini), conservando el presupuesto de USD 1 diario y los demás límites existentes. La documentación marca el modelo como deprecado: su disponibilidad para esta cuenta no se verificó contra el proveedor ni se cambió de modelo automáticamente. La actualización local quedó auditada como operación de mantenimiento (`usuario_id=0`), sin valores de credenciales.

Tiempo, tokens de salida, tamaño del cuerpo, frecuencia global y reserva estimada de presupuesto se controlan antes del envío. La reserva conservadora usa tamaño UTF-8 más margen y tarifas declaradas; no es una medición de factura y depende de mantener las tarifas correctas para el modelo. Se registra de forma transaccional y persistente en `.local/wizard_ai_usage.sqlite3`: fecha UTC, instante, usuario y micro USD reservados. No se reintegra por fallos. Se cierra la conexión y se mantiene el contador entre reinicios; no hay reintentos ni redirecciones HTTP. Este control no sustituye límites del proveedor ni cubre otros módulos.

### Archivos y validación

Backend: `app/schemas/wizard_ai.py`, `app/services/wizard_ai_service.py`, `app/api/wizard_ai.py`, registro en `router.py` y permisos en `deps_auth.py`. Configuración: campos nuevos en `ai_settings.py` y `admin/settings.html`. UI: `plan/wizard_chat.html`, `wizard_chat.js`, estilos e integración en `plan_asistente_oc.html`.

Validación: 99 pruebas Python conjuntas de conversación, configuración, cálculo y permisos; 10 pruebas Node de guía y chat, incluyendo confirmación de envío, acciones sin ejecución automática, errores, invalidación por cambios y simulación sin persistencia. Ruff, Jinja y sintaxis JavaScript comprobados. Las pruebas usan datos ficticios y transporte simulado. DPAPI falló bajo la cuenta del sandbox; las 32 pruebas de configuración pasaron bajo la cuenta de Windows del proyecto con temporales nuevos dentro de `.local`. Se comprobó que esa cuenta puede abrir la credencial existente sin mostrarla ni enviarla. No se realizó conversación externa ni revisión visual autenticada.

**Bloqueo de base real resuelto (2026-11-13):** el usuario aprobó 006, 007 y 008; se aplicaron tras validar el respaldo. Cuatro tablas creadas y verificadas. Consultas de ajustes, LAF e historial y simulación real de 05/2026 correctas (50 PT, 295 componentes), sin escrituras ni persistencia. Las tablas nuevas están vacías y requieren datos revisados por el usuario. Ver [resultado y evidencia de migraciones](WIZARD_IA_MIGRACIONES_PENDIENTES.md). Sigue pendiente probar una conversación externa confirmada y revisar el flujo en navegador autenticado.

## Guía de preparación de materiales — 2026-11-13

Acceso: **Wizard OC → Preparar materiales con el asistente**, ancla `/ui/plan-asistente-oc#wizard-guia`.

Se implementó una guía local por reglas: carga del período y plan, confirmación de stock MP/LAF, stock PT, deuda a clientes, simulación y revisión de propuesta. Navega por los pasos existentes, ofrece instrucciones y solicita confirmaciones explícitas. Las importaciones se realizan con los botones actuales y conservan sus permisos y efectos de guardado. Las confirmaciones son del usuario: no prueban integridad o actualidad del stock ni de los archivos.

La carga inicial exige plan con productos y lectura correcta de ajustes y LAF. Los errores no permiten avanzar. Cambiar datos invalida la revisión desde el paso afectado; cambiar período exige cargar nuevamente el plan. La guía evita envíos duplicados desde su propio botón y descarta el avance de una operación si se modificaron datos durante la espera. La simulación fuerza `persistir_sugerencias=false`, aun con la casilla de persistencia marcada. La emisión de órdenes sigue sin implementarse. La guía no conserva el avance al recargar y no bloquea la navegación manual del Wizard.

Archivos principales: `app/templates/plan/wizard_guia.html`, `app/static/js/wizard_guia.js` e integración en `app/templates/plan/plan_asistente_oc.html`. Sin cambios de tablas, migraciones, servicios o endpoints. La vista previa de preguntas libres se conserva en una sección desplegable.

Verificado: 51 pruebas de `test_plan_oc_service.py`, `test_plan_oc_security.py` y `test_screen_permissions.py`; 6 pruebas con `node --test tests/wizard_guia.test.cjs`, incluida la garantía de simulación sin persistencia; compilación Jinja y sintaxis JavaScript integrada y externa. No se validó visualmente en navegador ni contra datos reales. Advertencias existentes de Pydantic y caché pytest.

Pendiente: conversación libre con IA que solicite datos y seleccione acciones permitidas. La guía actual no usa un modelo de IA. Para esa integración se necesitan selección y vista previa del contenido, permisos por fuente, validación de acciones y controles de transporte ya indicados en los lotes anteriores; se mantiene bloqueada la IA comercial externa.

## Lote 1: integridad del recálculo e indicadores por unidad

- Las sugerencias APROBADAS se conservan completas, incluso cuando el nuevo faltante es cero. Se informa una alerta para revisión humana.
- La persistencia bloquea la fila existente con `SELECT ... FOR UPDATE` hasta el commit o rollback del llamador.
- Los endpoints actuales de asistente OC y faltantes/capacidad devuelven `resumen.por_unidad`, agrupado por ID de unidad, sin conversiones implícitas.
- Con varias unidades, los totales escalares de materiales y cobertura global son `null`; los consumidores deben usar `por_unidad`. Con una unidad mantienen valores numéricos. Sin materiales se devuelve una lista vacía, totales cero y cobertura 100%.
- La cobertura de cada unidad se calcula sobre faltantes netos: el excedente de un material no cubre otro material.
- Wizard OC y Plan mensual muestran los indicadores por unidad. Los cálculos individuales de demanda, MBOM, stock y descuento LAF conservan sus reglas.

Validación: `tests/test_plan_oc_service.py`, datos ficticios y dependencias de base sustituidas. No requiere migraciones, dependencias nuevas ni conexiones de IA.

## Lote 2: permisos y bloqueo de IA externa

- `POST /api/plan-produccion-mensual/asistente-oc/calcular`: lectura de `ui_plan_asistente_oc` para simular; escritura de esa misma pantalla para `persistir_sugerencias=true`. También se validan las variantes booleanas aceptadas por FastAPI, como `1` y `yes`.
- La simulación no persiste sugerencias ni registros en `asistente_oc_corrida_hist`. La autenticación conserva su gestión habitual de sesiones.
- `GET /api/plan-produccion-mensual/faltantes-capacidad`: ahora simula por defecto, tanto en el endpoint como en el servicio. Lectura de Plan mensual o Requerimientos permite consultar; escritura de alguna de esas pantallas permite guardar explícitamente.
- Plan mensual incluye una casilla desmarcada para guardar sugerencias. Wizard OC conserva su casilla y usa permisos de pantalla para los controles de escritura, incluyendo administradores.
- El control interno de permisos considera los parámetros de consulta, igual que el control general. Las consultas valorizadas requieren escritura cuando se solicita persistencia, incluidas las exportaciones XLSX.
- `GET /api/plan-produccion-mensual/asistente-oc/ia/estado` informa el bloqueo. `POST /api/plan-produccion-mensual/asistente-oc/ia` devuelve 403 sin procesar el contenido ni consultar el cálculo o bases de negocio. Ambas rutas requieren sesión y lectura de Wizard OC.
- La política local bloquea IA externa incluso con claves, proveedor configurado o rol administrador. No incorpora SDK, transporte ni mecanismo de habilitación; el futuro envío requiere otro lote y autorización de contenido.
- Este bloqueo se limita al módulo de IA de Wizard OC: no modifica las conexiones existentes de BCRA u otros módulos.

Validación: `tests/test_plan_oc_security.py`, `tests/test_plan_oc_service.py` y `tests/test_screen_permissions.py`, sin acceso a bases productivas ni proveedores. Sin migraciones ni cambios de credenciales/configuración productiva.

## Lote 3: configuración de IA y revisión de saldos LAF

Acceso: **Administración → Configuración → IA y controles**, o **Administración → IA y controles**. Usa los permisos existentes de `ui_admin_settings`; no agrega roles ni migraciones.

- Modelo OpenAI editable, clave nueva/retener/eliminar y límites preparados de tiempo, tokens, caracteres, frecuencia y presupuesto diario en USD.
- Los envíos siguen bloqueados por `ai_policy_service`, incluso después de guardar. No se comprueba la clave contra OpenAI ni se lista su catálogo de modelos. Los límites aún no representan un transporte habilitado.
- Guardado local atómico en `.local/ai_settings.json`, excluido de Git. La clave se cifra con Windows DPAPI para la cuenta que ejecuta la API; no es portable entre cuentas/equipos. No se modifica `.env` ni `app/config.json`.
- Las respuestas muestran solo presencia y origen de la clave. Una variable `OPENAI_API_KEY` tiene prioridad; eliminar la clave local no elimina una variable de entorno.
- La clave se admite por HTTPS o localhost. La interfaz impide ingresarla/enviarla desde HTTP remoto y el backend también rechaza ese caso. No se admite guardado desde otro origen web.
- Auditoría atómica con la configuración: fecha UTC, usuario, acción y nombres de campos modificados; conserva hasta 200 eventos. Sin valores, claves ni prompts.
- `GET /api/system/settings` devuelve únicamente URL pública y días BCRA, evitando exponer credenciales del archivo general. El formulario BCRA conserva sus campos actuales.
- No se implementó todavía el módulo de filtrado/vista previa de contenido: su aprobación y desarrollo siguen siendo requisitos para un futuro envío.

Fuente de saldos LAF confirmada por el usuario: **carga manual desde Flexxus**. La tabla actual distingue cantidad total, quincenas y estado, pero no conserva cantidad recibida/saldo independiente ni vínculo a una orden. No se reinterpreta `cantidad_total` de registros existentes. El siguiente lote deberá definir una entrada de saldo independiente y su auditoría; si requiere esquema nuevo, se presentará la migración antes de ejecutarla.

Validación: `tests/test_ai_settings.py` con claves/archivos ficticios, cifrado DPAPI local, aislamiento de HTTP externo, permisos, retención/eliminación, fallos de escritura y ocultamiento de secretos.

## Próximos lotes

1. Saldos LAF manuales desde Flexxus: proponer almacenamiento y auditoría separados de la cantidad original; revisar esquema real y aprobar cualquier migración antes de modificar descuentos.
2. Reproducibilidad de corridas: presentar el plan de migración y obtener aprobación antes de alterar MariaDB.
3. Pronóstico local, ajuste humano y reglas quincenales de abastecimiento, en lotes separados.

OpenAI queda opcional y deshabilitado; Anthropic no está autorizado. Ningún lote autoriza emitir órdenes automáticamente o enviar datos comerciales al exterior.


## Prueba de conexión autorizada

El botón **Probar conexión** usa la clave y modelo guardados. Requiere escritura en Configuración y confirmación antes de cada envío. Su endpoint `/api/system/settings/ia/probar` no acepta prompts ni datos comerciales: envía únicamente `Respondé OK` a la API oficial Responses de OpenAI, con `store=false`, hasta 64 tokens de salida y sin reintentos ni redirecciones. Esto no garantiza ausencia de registros del proveedor.

Esta excepción fue autorizada por el usuario exclusivamente para la prueba sintética. El bloqueo general de IA comercial se conserva. La prueba puede generar costos; los límites de presupuesto configurados siguen pendientes de implementación para la integración general. Se limita a un intento por minuto y tres por día UTC por instancia; reiniciar la instancia reinicia ese contador. Registra metadatos locales, sin claves, prompt ni salida del proveedor. Las pruebas automáticas usan transporte simulado.
