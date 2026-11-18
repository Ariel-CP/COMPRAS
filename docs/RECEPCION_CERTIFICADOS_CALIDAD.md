# Certificados del proveedor en Control de Calidad

Implementado el 18/11/2026 para las recepciones operativas de COMPRAS.
Desde **Control de Calidad**, abrir un material/lote y usar la sección
**Certificado de calidad del proveedor**:

1. Marcar «Verificado: el proveedor entregó el certificado de calidad».
2. Opcionalmente seleccionar un PDF, JPG o PNG de hasta 10 MB.
3. Pulsar **Guardar certificado**. Adjuntar un archivo marca la entrega automáticamente.

También se guarda cualquier cambio pendiente de esta sección antes de guardar la
inspección. Si la carga del certificado falla, la inspección no se registra. Son
operaciones separadas: un certificado guardado no se pierde si la inspección falla.
La casilla puede registrarse sin documento digital y corregirse mientras no haya
archivos. Con documentos adjuntos permanece marcada. Se pueden agregar documentos,
se conservan los anteriores y un reintento del mismo archivo no lo duplica.
La descarga requiere permiso de lectura de Control de Calidad; el guardado, escritura.

Desde **Controles recientes**, el detalle de una recepción local ofrece
**Control de calidad y certificados** para volver a la ficha incluso después de
finalizar la inspección. Los usuarios sin permiso de Calidad no ven ese enlace.
El historial Access y las recepciones importadas conservan el modo de solo lectura.
No se mezclan estos nuevos registros con el ranking histórico recalculado desde Access.

## Datos y API

Migración [026](../database/migrations/026_recepcion_certificados_calidad.sql), aplicada
en MariaDB el 18/11/2026 tras comprobar el esquema real. Crea dos tablas sin alterar
tablas o registros existentes:

- `recepcion_certificado_calidad`: estado por `recepcion_linea_id`, usuario y fecha.
- `recepcion_certificado_documento`: documentos BLOB completos, nombre original
  depurado, MIME, tamaño, SHA-256, usuario y fecha; únicos por línea y hash.

Los documentos se incluyen en los respaldos completos de MariaDB. No son vínculos
a archivos de la PC del usuario ni archivos publicados en `/static`. No hay borrado
de documentos desde este flujo. Las recepciones con certificados registrados no se
pueden borrar ni editar/reasignar, para conservar su asociación a proveedor/material/lote.
El guardado usa transacción y bloqueo; no ejecuta commits dentro del service.

| Método | Endpoint bajo `/api/recepcion` | Función |
| --- | --- | --- |
| GET | `/calidad/lineas/{id}/certificado` | Estado, recepción asociada y metadatos sin bytes |
| PUT | `/calidad/lineas/{id}/certificado` | FormData con `recibido` y `archivo` opcional |
| GET | `/calidad/lineas/{id}/certificado/documentos/{documento_id}` | Descarga autenticada del archivo de esa línea |

La extensión y la firma inicial deben corresponder a PDF/JPEG/PNG; se rechazan
vacíos y tamaños superiores al límite. Esta validación no interpreta el contenido
técnico del certificado. Descarga como adjunto, con `nosniff` y `private, no-store`.

Implementación: `app/services/recepcion_certificado_service.py`,
`app/schemas/recepcion_certificado.py`, router existente `app/api/recepcion_api.py`,
`app/templates/recepcion/calidad_material.html` y su JS. La ficha consulta por ID
directamente, sin depender de encontrar la línea entre las primeras 500 pendientes.
Enlaces desde la plantilla/JS de controles; recursos modificados versionados.

## Validaciones

Pruebas de servicio/API en `tests/test_recepcion_certificado.py`: persistencia de
casilla, descarga exacta, deduplicación, conservación de documentos, rollback conjunto,
formatos, tamaño, aislamiento por línea, históricos y permisos de lectura/escritura.
Compatibilidad cubierta por las pruebas existentes de recepción operativa y permisos:
42 pruebas conjuntas aprobadas (15 nuevas).
Ruff y sintaxis de ambos JS comprobados; ambas plantillas renderizadas con Jinja.

Prueba adicional contra MariaDB real: recepción temporal y PDF sintético dentro de
una transacción, lectura idéntica del BLOB y validación Pydantic; rollback y cero
registros de prueba restantes comprobados. Se guardó estructura/cantidades previas
en `outputs/runtime/esquema_antes_certificados.json` y se verificó que no cambiaron
las tablas existentes. No se hizo un respaldo integral nuevo ni prueba de restauración.
No había recepciones operativas locales al comenzar. No se realizó carga de un
certificado real desde una sesión del usuario ni revisión visual autenticada.
Instancia reiniciada por el supervisor; salud 200, endpoints nuevos presentes en
OpenAPI, JavaScript nuevo servido y acceso al certificado sin sesión bloqueado con 401.

Ver también [validación de evaluación/recepción](VALIDACION_EVALUACION_PROVEEDORES.md)
y [evidencia histórica de certificados](RANKING_POWERBI_UI.md#evidencia-de-certificado--18112026).
