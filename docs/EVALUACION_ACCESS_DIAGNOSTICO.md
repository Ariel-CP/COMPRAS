# Evaluación de proveedores: diagnóstico inicial de Access

Fecha de consulta: 2026-11-17. Lectura real mediante ODBC con `ReadOnly=1`, conexión serializada y cierre en `finally`. Sin importación a MariaDB ni modificaciones en Access.

Actualización: ya se recuperó el código del formulario confirmado por el usuario desde una copia local con macros deshabilitadas. Ver [fórmulas, pesos y diferencia V11/V13](EVALUACION_FORMULARIO_NEW.md). La limitación anterior sobre fórmulas no inspeccionadas queda resuelta para ese formulario; sigue pendiente la correspondencia documental con V13.

## Vista previa implementada

Disponible en `/ui/evaluaciones/vista-previa`, enlazada desde Evaluaciones y Evolución (requiere lectura de `ui_evaluaciones`). Busca código/nombre en EVAPROV, selecciona por Id de origen y muestra respuestas textuales, PV, PO/PP, subtotales, total de origen y suma calculada con advertencias. No ejecuta importadores ni guarda el borrador.

Tres casos reales conciliados en subtotales: ID 1874, código 10296: 35 + 60 + 5 = 100; ID 1764, código 1518: 23 + 41,67 + 3 = 67,67; ID 1695, código 10837: 25 + 16,5 + 3 = 44,5. Los tres pertenecen al período textual 2023, aunque fueron registrados en 2024. Esta validación no demuestra la fórmula interna de cada criterio ni su correspondencia V13.

Discrepancias identificadas sin corregir origen: ID 700 suma 69 frente a total 60; ID 381 suma 42 frente a total 60. Evidencia: `outputs/evaluacion_proveedores/conciliacion_piloto.json`.

El borrador muestra las tres categorías V13, período, evaluador y observaciones editables. No calcula un resultado V13 porque faltan criterios/pesos acordados. Los textos se pierden al navegar o recargar, advertido en pantalla. No se ha incorporado todavía evidencia automática de recepción por período: los datos mostrados son exclusivamente EVAPROV.

Validación: 32 pruebas aprobadas (servicio, renderizado/escape HTML, permisos, auth y regresión Access), Ruff aprobado, renderizado con datos reales 200. API reiniciada bajo la cuenta con acceso a R:, salud 200 y ruta confirmada en OpenAPI. Sin comprobación visual en navegador autenticado ni verificación del esquema MariaDB vivo; sin migraciones, commits ni nuevas escrituras en bases de negocio. Próximo paso: revisar esta vista con el usuario y acordar la matriz V13 antes de habilitar cálculo/guardado.

## Fuentes verificadas

### Criterios para 2025: ampliación del 17/11/2026

El usuario indicó evaluar conforme a los criterios utilizados y al procedimiento. Se inspeccionaron por ODBC los campos de `PROVEEDORES` y catálogos; mediante DAO se abrieron backend y frontend relacionado en modo solo lectura, sin ejecutar consultas, macros ni formularios y sin alterar vínculos. El frontend identificado se denomina `Gestion de Evaluación de Proveedores Server270622.accdb`; su nombre no demuestra vigencia V13.

Se verificaron 12 campos de aplicabilidad: tiempo de entrega, cumplimiento de entrega, calidad de proveedor, certificado, entrega del servicio según fecha, calidad del servicio, conformidad de calidad, gestión de precio, gestión de facturación, reclamos y servicio posventa. No equivalen por sí solos a una escala ni a pesos. Sobre 3.063 proveedores, precio/reclamos/posventa figuran falsos en todos; facturación solo verdadero en uno. No es válido convertir automáticamente esos falsos en criterio no aplicable sin confirmar su uso actual.

Las consultas SQL de evaluación del frontend leen puntajes almacenados y períodos; no contienen fórmulas de asignación de puntos. Se confirmó existencia de formularios `EVALUACION DE PROVEEDORES` y `EVALUACION DE PROVEEDORESNEW`, pero DAO no permitió verificar sus controles/código de cálculo mediante este inventario. No se ejecutaron los formularios ni la consulta UPDATE hallada en el catálogo.

Evidencia 2025 consultada por **Fecha Control** entre 01/01/2025 inclusive y 01/01/2026 exclusiva: **1.126 controles, 64 códigos distintos, 1.122 aceptados y 4 rechazados**. Certificado verdadero en 189 y falso en 937; falso sigue siendo dato por validar, no incumplimiento confirmado. Los 64 códigos son proveedores con controles; no constituyen la totalidad de proveedores críticos/servicios que requieren reevaluación anual. Evidencia agregada en `outputs/evaluacion_proveedores/cobertura_2025.json`.

Regla de implementación: preservar criterios y respuestas históricas; para 2025 documentar correspondencia con las tres categorías V13, fuente, aplicabilidad, escala, máximo, ponderación y responsable. No copiar respuestas de 2023/2024 como evaluación de 2025, no transformar aceptación de recepción en aprobación formal y no usar ausencia de datos como cero ni como excelente. Antes de guardar resultados finales falta verificar las reglas de cálculo y su vigencia en el formulario utilizado por Compras/Calidad. No se generaron calificaciones 2025 ni se modificó el código de la aplicación en esta ampliación.

- Base de proveedores configurada por el importador: tabla `EVAPROV`, 1.710 filas y 66 columnas. Contiene respuestas de criterios, valores PV/PO/PP, subtotales, total, resultado, evaluador, sector, período y comentarios.
- Base de recepción configurada en el sistema: `CONTROL DE RECEPCION`, 20.567 filas. Estados presentes: 20.322 aceptados, 234 rechazados, 4 anulados y 7 sin estado. La presencia de un dato no confirma su validez.
- Inventario adicional en proveedores: `PROVEEDORES`, `EVALUADORES`, `CALIFICACION`, `PERIODO`, `ACCIONES A IMPLEMENTAR`, `ANALISIS EVALUACION`, entre otras tablas/consultas. Su estructura y contenido aún no se revisaron.

## Matriz inicial de disponibilidad

Las agrupaciones siguientes describen Access histórico, no equivalen todavía a las tres categorías de V13.

| Bloque histórico | Criterios disponibles | Fuente inicial | Uso propuesto |
|---|---|---|---|
| Calidad | Especificaciones, certificado, innovación | Respuesta `Cal_*` y campos PV/PO/PP | Conservar histórico y validar puntuación; recepción aporta evidencia de aceptación y certificado. |
| Servicio | Tiempo de entrega, disponibilidad ante reclamo, precio/mercado, posventa, servicio de entrega, pago, stock, comunicación | Respuesta `Ser_*` y campos PV/PO/PP | Evaluador confirma criterios comerciales y de servicio; automatizar solo indicadores demostrables. |
| Embalaje | Presentación, identificación, tipo y durabilidad | Respuesta `Emb_*`, PV y PO/PP de embalaje | Evidencia de recepción como apoyo; no equiparar automáticamente un control de embalaje a los cuatro criterios. |
| Cierre | P_CAL, P_SER, P_EMB, Calif_Total, CALIFICACION, Fecha, PERIODO, EVALUADOR | EVAPROV | Conciliar importes y clasificación preservando identidad y versión del origen. |

Las respuestas históricas son principalmente Excelente/Suficiente/Insuficiente. Las distribuciones de PV presentan valores 5/3/0, pero todavía falta comprobar correspondencia fila por fila y fórmulas. Los PP muestran diferentes ponderaciones históricas: no se debe aplicar una fórmula única a todos los años ni derivar pesos vigentes únicamente del máximo observado.

## Hallazgos que condicionan el diseño

1. El importador existente trata `Cal_*`, `Ser_*` y `Emb_*` como números; las respuestas textuales no se convierten y se pierde el detalle en esos casos. Debe leer y preservar respuesta y puntuación verificadas, sin inventar conversiones.
2. Dos evaluaciones tienen diferencias mayores a 0,02 entre suma de P_CAL/P_SER/P_EMB y Calif_Total. Hay que identificar y explicar esos casos antes de elegir un total canónico.
3. Hay 36 grupos repetidos por código literal y texto de período; no son duplicados confirmados. No eliminar ni colapsar sin revisar Id, fechas, tipo y contenido.
4. EVAPROV tiene 1.294 evaluaciones anuales, 412 cuatrimestrales y 4 de preselección. El importador actual no conserva PRESELECCION como tipo propio. El año de fecha y el período textual deben cotejarse, no asumirse equivalentes.
5. Dos fechas de evaluación y dos fechas de control están después del 17/11/2026 (años 2027/2028). Deben revisarse; no corregidas ni excluidas automáticamente.
6. Por fecha, las evaluaciones válidas anteriores a hoy abarcan 2019–2024; no se observan registros fechados 2025/2026 en EVAPROV. Esto describe esta tabla, no prueba ausencia de evaluaciones en otras fuentes.
7. Recepción tiene cantidad OC informada en 1.960 filas y fecha de emisión OC en 12.615; no se identificó en el listado leído un campo de fecha comprometida. Fecha de emisión y fecha de recepción no bastan para afirmar entrega a tiempo.
8. `TieneCertificado` es verdadero en 316 controles y falso en 20.251; falta verificar si falso representa ausencia real, valor por defecto o dato no relevado. No convertir automáticamente en mala calificación.
9. Solo 14 evaluaciones tienen comentarios y ninguna tiene referencias. El nuevo registro debe facilitar evidencia y justificación sin inventar datos históricos.

## Próximo incremento concreto

1. Revisar metadatos y tablas auxiliares de proveedores y, si existe acceso disponible, definición del formulario/consulta de evaluación vigente; ODBC no muestra por sí solo las fórmulas de un formulario Access.
2. Conciliar tres evaluaciones históricas y las dos diferencias de totales, con Id de origen, respuestas, PV/PO/PP y versión/fecha. Verificar esquema MariaDB real antes de diseñar persistencia.
3. Acordar una matriz V13 con categoría oficial, criterio, escala, máximo, evidencia, fuente y responsable. Lo no demostrable desde recepción se completará por el evaluador.
4. Implementar una vista previa de evaluación sin escrituras; después guardar evaluaciones confirmadas y conectarlas a Evolución. Mantener adaptadores para Access ahora y Compras después.

## Evidencia y límites

- Resultado agregado: `outputs/evaluacion_proveedores/diagnostico_access.json` (sin exportar nombres, correos ni comentarios individuales).
- Script reproducible: `scripts/dev/diagnosticar_evaluacion_access.py`; fecha de corte fija 2026-11-17 para este diagnóstico.
- Ruff aprobado y dos consultas completas ejecutadas; no se ejecutaron pruebas de flujos funcionales al no modificarse la aplicación.
- Sin revisión autenticada de UI, sin lectura de formularios Access, sin verificación de esquema MariaDB vivo ni conciliación individual. No se modificó el importador existente.
