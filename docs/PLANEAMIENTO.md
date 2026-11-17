# Planeamiento y seguimiento

Actualizado: **13/11/2026** · Proyecto: **Compras y planificación**

Esta página reúne los pasos del proyecto. Las casillas marcadas indican tareas completadas según la evidencia indicada. Los pasos futuros son un plan de trabajo, no una autorización para ejecutarlos.

**Para verla en VS Code:** abrir este archivo y presionar **Ctrl+Shift+V**, o **Ctrl+K V** para ver la vista previa al costado. Para actualizar una casilla, cambiar `[ ]` por `[x]` en el editor y guardar. La vista previa refleja los cambios.

## 1. Entorno de trabajo — comprobado

- [x] Leer la bitácora y consultar el estado de Git.
- [x] Confirmar que las herramientas de Codex ejecutan comandos.
- [x] Ejecutar Python del entorno virtual del proyecto.
- [x] Comprobar TEMP y TMP después de la corrección.
- [x] Verificar escritura, lectura y eliminación de un archivo temporal.
- [x] Registrar el resultado en la [bitácora del proyecto](ESTADO_PROYECTO.md).

Resultado: el bloqueo de herramientas no se reprodujo en esta sesión. La API y los flujos funcionales todavía no se comprobaron en esta revisión.

## 2. Wizard OC — avances documentados

Estas casillas reflejan lo registrado en [Desarrollo incremental de Wizard OC](wizard_oc_desarrollo.md). Sus pruebas no se volvieron a ejecutar en esta sesión.

- [x] Lote 1: integridad del recálculo e indicadores por unidad.
- [x] Lote 2: permisos de simulación y persistencia; bloqueo de IA comercial externa.
- [x] Lote 3: configuración local de IA y controles de seguridad.
- [x] Documentar la prueba de conexión sintética autorizada.
- [x] Confirmar que los saldos LAF se cargarán manualmente desde Flexxus.
- [ ] Volver a ejecutar las pruebas focalizadas antes de modificar estos flujos.

## 3. Próximo lote — saldos LAF manuales desde Flexxus

**Objetivo:** registrar el saldo pendiente de forma independiente, conservando la cantidad original y una auditoría de cambios.

### Paso 1 · Revisar el estado real

- [ ] Leer `database/schema.sql` con encoding UTF-16 y las migraciones relacionadas.
- [ ] Revisar servicios, endpoints y pantallas que consultan o descuentan LAF.
- [ ] Comprobar el esquema de la base existente antes de asumir migraciones aplicadas.
- [ ] Identificar pruebas del flujo y ejecutar una validación inicial.

### Paso 2 · Preparar una propuesta concreta

- [ ] Definir campos de saldo, reglas de edición y datos de auditoría.
- [ ] Detallar tablas, endpoints, servicios y pantalla afectados.
- [ ] Explicar cómo se conservan las cantidades originales de los registros actuales.
- [ ] Preparar la migración y su validación, si se necesita cambiar el esquema.
- [ ] Presentar la migración para aprobación antes de ejecutarla, según lo acordado en las notas del módulo.

### Paso 3 · Implementar el lote acordado

- [ ] Implementar almacenamiento y auditoría con transacciones y consultas parametrizadas.
- [ ] Incorporar validación y permisos en los endpoints.
- [ ] Agregar la carga manual en la interfaz con el patrón visual existente.
- [ ] Actualizar el descuento LAF según las reglas acordadas.
- [ ] Versionar los recursos estáticos modificados.

### Paso 4 · Validar y cerrar

- [ ] Ejecutar pruebas focalizadas del flujo y permisos.
- [ ] Ejecutar Ruff sobre Python modificado y `node --check` sobre JavaScript modificado, si corresponde.
- [ ] Verificar `/health` y los endpoints afectados en la instancia identificada del proyecto.
- [ ] Revisar en pantalla carga, consulta, errores y permisos.
- [ ] Registrar resultados, límites y próximo paso en la bitácora.

## 4. Lotes posteriores — pendientes de definición

- [x] Crear plantilla Excel integral con parámetros y una hoja por listado del Wizard.
- [x] Implementar descarga, validación completa y confirmación para guardar/calcular en una sola transacción.
- [x] Verificar cobertura de códigos, cantidades, permisos, rollback y repetición sin duplicar LAF (101 pruebas Python y 15 Node del avance).
- [x] Revisar visualmente el Excel y el formulario en escritorio/móvil; cargar los endpoints en la instancia activa.
- [ ] Completar, validar y confirmar un archivo real y revisar el requerimiento de materiales resultante.
- [x] Implementar guía local del Wizard para solicitar revisión de datos y simular materiales sin guardar.
- [x] Verificar secuencia, errores, invalidación por cambios y simulación sin persistencia (6 pruebas Node; 51 pruebas Python del flujo).
- [ ] Revisar la guía en navegador con datos del sistema.
- [x] Implementar conversación con IA para conducir el Wizard, con vista previa de metadatos y acciones permitidas.
- [x] Configurar habilitación acotada, tarifas y presupuesto conservando modelo y clave existentes.
- [x] Verificar permisos, conversación y cálculo con 99 pruebas Python y 10 pruebas Node.
- [x] Aprobar y aplicar las migraciones existentes 006, 007 y 008, con respaldo y verificación de las cuatro tablas. Ver [resultado de aplicación](WIZARD_IA_MIGRACIONES_PENDIENTES.md).
- [x] Comprobar consultas reales y simular 05/2026 sin persistencia (50 PT y 295 componentes).
- [ ] Cargar o revisar stock PT, deuda y LAF del período elegido; las tablas nuevas están vacías.
- [ ] Verificar una conversación real confirmada por el usuario y el flujo completo en navegador.
- [x] Agregar vista previa del formulario de consultas IA en Wizard OC (período, tema y pregunta; sin conexión a datos ni proveedor).
- [ ] Revisar visualmente el formulario con una sesión autorizada.
- [ ] Definir fuentes, permisos y vista previa de datos para responder consultas reales de IA.
- [ ] Reproducibilidad de corridas: preparar propuesta y migración para revisión.
- [ ] Pronóstico local: definir alcance, datos de entrada y validaciones.
- [ ] Ajuste humano: definir edición, trazabilidad y permisos.
- [ ] Abastecimiento quincenal: acordar reglas e implementar un lote separado.

## 5. Condiciones vigentes

- IA comercial externa: **bloqueada**; la prueba sintética tiene alcance separado.
- Anthropic: **sin autorización**, según las notas actuales.
- Emisión automática de órdenes: **fuera del alcance autorizado**.
- Cambios locales existentes: conservarlos; no crear commits automáticamente.

## Documentación de consulta

- [Estado y continuidad del proyecto](ESTADO_PROYECTO.md)
- [Detalle de Wizard OC y controles de IA](wizard_oc_desarrollo.md)
- [Setup del proyecto](../README.md)
- [Organización de scripts](../scripts/README.md)
- [Validación de evaluación y recepción](VALIDACION_EVALUACION_PROVEEDORES.md)

Al completar cada paso, marcar su casilla solamente después de comprobar el resultado y actualizar la bitácora con la evidencia correspondiente.
