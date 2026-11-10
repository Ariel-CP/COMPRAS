# Desarrollo incremental de Wizard OC

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
