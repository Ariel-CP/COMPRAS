# Wizard IA: habilitación del flujo de datos

Fecha de diagnóstico y ejecución: **13/11/2026**. Estado: **aprobada por el usuario y aplicada; verificación completada**.

La conversación del Wizard está implementada. La inspección inicial confirmó que faltaban las cuatro tablas siguientes. Las migraciones aprobadas ya las crearon en la base configurada.

## Resultado de la ejecución

- Aprobación recibida del usuario: «lo apruebo».
- Respaldo válido: `.local/backups/wizard_oc/compras_db_20261113_122936.sql`, **10.914.738 bytes**, 36 tablas. Se verificaron código cero, ausencia de stderr, cierre del dump, cobertura de tablas y SHA-256 `5812a1a064bf40cc0a9b819db26d97997e9c571e44ac2f05d1558f32b04e9249`. No se efectuó una restauración de prueba.
- Los intentos iniciales fallaron por negociación TLS o informaron stderr. Se marcaron sus archivos como `.failed` para evitar confundirlos con respaldos válidos. Se comprobó destino loopback y se usó `--skip-ssl` solo en la invocación local que produjo el respaldo validado; no se cambió la configuración general ni las credenciales.
- Se aplicaron 006, 007 y 008 en orden con `scripts/ops/apply_migration.py`. Todas finalizaron correctamente. No se borraron ni modificaron registros existentes.
- Verificadas columnas, dos índices secundarios por tabla, claves externas y unicidad por período/producto para stock PT y deuda. Las cuatro tablas estaban vacías después de su creación.
- Consultas reales de ajustes, LAF e historial correctas. Simulación del período **05/2026**: 50 productos PT y 295 componentes; una alerta de cálculo. `persistir_sugerencias=false`, cero sugerencias persistidas/eliminadas, sin corridas guardadas. Se instaló un control de sentencias en la conexión de verificación para rechazar cualquier escritura y se cerró con rollback.
- Evidencias operativas sin secretos en `.local/wizard_migrations_preflight.json` y `.local/wizard_migrations_verificacion.json`, excluidas de Git.
- Pendiente: revisión visual autenticada, carga de stock PT/deuda/LAF reales y primera conversación externa confirmada desde la pantalla. Las tablas vacías no validan saldos cero.

| Migración existente | Tabla que crea | Uso |
| --- | --- | --- |
| [006](../database/migrations/006_add_asistente_oc_sources.sql) | `asistente_oc_stock_pt_mes` | Stock de productos terminados por período |
| [006](../database/migrations/006_add_asistente_oc_sources.sql) | `asistente_oc_deuda_cliente_mes` | Deuda de clientes por período |
| [007](../database/migrations/007_add_asistente_oc_corrida_hist.sql) | `asistente_oc_corrida_hist` | Historial de cálculos guardados |
| [008](../database/migrations/008_add_asistente_oc_laf_solicitado.sql) | `asistente_oc_laf_solicitado` | Pedidos LAF ya solicitados |

## Alcance revisado

- Se leyeron las tres migraciones en UTF-8 y el esquema base en UTF-16.
- Las migraciones contienen `CREATE TABLE IF NOT EXISTS`; no contienen cargas de datos, eliminaciones ni modificaciones de tablas existentes.
- `producto.id` y `usuario.id` en la base real son `BIGINT UNSIGNED`, compatibles con las claves externas propuestas.
- Se mantienen cantidades y pedidos existentes. No se implementa aquí un saldo recibido LAF independiente ni se reinterpretan cantidades originales.
- Los endpoints y servicios ya utilizan estas tablas. No se propone modificar sus nombres ni agregar un circuito alternativo.

## Procedimiento ejecutado tras la aprobación

1. Volver a comprobar la base destino y el esquema, sin imprimir credenciales.
2. Generar y verificar un respaldo con el mecanismo existente del proyecto antes de ejecutar DDL. Un dump vacío o un error no cuenta como respaldo válido.
3. Aplicar 006, 007 y 008, en ese orden, comprobando cada sentencia y deteniéndose ante un fallo.
4. Verificar tablas, índices, claves externas y tipos resultantes.
5. Comprobar consultas de ajustes, LAF e historial y simulación sin persistencia. Se verificaron directamente los servicios, sin crear ni suplantar una sesión de usuario.
6. Registrar resultados. La revisión del requerimiento en pantalla queda pendiente de una sesión autenticada.

MariaDB realiza commits implícitos para este DDL: no se presenta como una transacción reversible. Si una sentencia falla, se documentará qué tablas se crearon antes de reanudar. No se borrarán automáticamente tablas ni datos para revertir.

La aprobación solicitada se limita a estas migraciones existentes y sus verificaciones. No incluye emitir OC, enviar archivos de negocio a la IA o desarrollar el futuro lote de saldos LAF manuales.

Detalle de la conversación y sus controles: [Wizard OC](wizard_oc_desarrollo.md).
