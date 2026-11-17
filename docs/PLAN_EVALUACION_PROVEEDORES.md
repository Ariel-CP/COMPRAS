# Plan de evaluación de proveedores

Fecha: 2026-11-17. Estado: propuesta para acordar; sin implementación ni cambios en BD.

## Decisión del usuario y avance

Nueva fuente aportada: se inspeccionó el PBIX usado en las últimas evaluaciones. Su metodología de insumos es automática 45 % calidad, 45 % entrega y 10 % certificado; se reproduce como promedio por recepción con Fecha de Entrega y EVALUAR. Ver [fórmulas, conciliación y diferencias con el importador](EVALUACION_POWERBI.md). Esta evidencia pasa a ser la referencia para analizar la última evaluación; no se restablece la simulación manual retirada ni se cambian calificaciones existentes.

Actualización 17/11/2026: a pedido del usuario se retiró la simulación anual 2025 del último avance. Se conservan la vista previa histórica y la investigación de la fórmula del formulario confirmado; ver [nota de fórmulas](EVALUACION_FORMULARIO_NEW.md).

El registro B será implementado por este sistema. Access es la fuente inicial; luego se incorporará el sistema de compras. No es necesario esperar un formulario externo para iniciar el diagnóstico. Ya se realizó lectura real de ambas bases: ver [hallazgos, matriz y próximo incremento](EVALUACION_ACCESS_DIAGNOSTICO.md). Aún falta definir los criterios y pesos V13 a partir de evidencia verificable; no equiparar automáticamente el histórico antiguo a las categorías actuales.

## Base documental aportada: PG-4.06.02 versión 13

Leídas las seis páginas de `TEMP/(ABRIR) PG-4.06.02-V13.pdf`, revisión del 14/05/2024, con marca de copia no controlada. Inspección visual de la página 4 para categorías y tabla de calificación. Se utiliza como referencia aportada por el usuario; no se verificó vigencia contra el control documental.

- Compras clasifica A (crítico) o B (no crítico), prepara listados y cada sector evalúa sus proveedores de contacto (puntos 10 y 50).
- La selección inicial debe registrar antecedentes/referencias/muestras y conservar evidencia en el legajo (punto 30).
- Para críticos, evaluación anual mediante RG-PG.4.06.02_B y reevaluaciones adicionales a criterio del responsable ante situaciones particulares. Las categorías son Cumplimiento en insumos/servicios, Gestión y Post contractual. El formulario B contiene los criterios y puntajes; no está incluido en el PDF (punto 40).
- Resultado por suma de puntos: aprobado 70–100, condicional 55–69, no apto 0–54. El texto usa rangos enteros: precisar redondeo/decimales con el formulario antes de dar por confirmado el tratamiento actual del sistema.
- Condicional: plazo para adecuarse y participación comercial únicamente si no hay cotización de proveedor aprobado. No apto: baja comercial, con excepción consentida por el responsable del área y documentada en comentarios (puntos 30/40).
- La baja requiere solicitud del requirente y aprobación de Compras, motivo y registro de inactividad (punto 60). No convertir automáticamente el puntaje en una baja sin modelar ese circuito.
- No críticos: seguimiento continuo de experiencia de compra, con evaluación menos estricta (puntos 30/40).
- Al finalizar se prevé envío al proveedor o, si no tiene correo, al responsable. Diseñar trazabilidad de entrega; este documento no autoriza al agente a enviar comunicaciones (punto 50).
- Histórico con calificaciones y observaciones; resultados e incumplimientos/acciones correctivas para revisión por Dirección (puntos 70/80).

### Ajuste del plan y brechas

1. Obtener RG-PG.4.06.02_B vigente: construir la matriz oficial de criterios, máximos, suma, evidencias y datos faltantes. Las métricas operativas serán insumos cuya correspondencia debe demostrarse; no reemplazan la evaluación formal.
2. Auditar clasificación A/B, responsables, legajos y cobertura anual en datos reales. Preparar piloto de tres proveedores críticos.
3. Definir captura/revisión de la evaluación y reevaluaciones extraordinarias. Revisar la clave única proveedor/año/período y el modelo anual/cuatrimestral: pueden limitar múltiples evaluaciones dentro del mismo período; el procedimiento no exige cuatrimestres.
4. Adecuar categorías y trazabilidad sin renombrar históricos de forma ciega. Revisar esquema real antes de proponer migraciones; conservar metodología/origen para comparaciones.
5. Completar evolución con observaciones, detalle y seguimiento; definir comparación entre evaluaciones equivalentes y separar promedios de la última calificación formal.
6. Diseñar plazos de mejora, excepciones, baja aprobada, comunicación y reporte para Dirección. Implementar y probar por incrementos después de acordar el formulario y el piloto.

Próximo insumo concreto: formulario RG-PG.4.06.02_B, preferentemente vigente y con un ejemplo completado que permita conciliar el cálculo.

## Diagnóstico revisado en código

- `/ui/evaluaciones/evolucion` consulta el historial formal de `evaluacion_proveedor_anual`; permite proveedor y fechas, gráfico, promedio y tendencia entre los últimos dos puntajes.
- La evaluación formal suma calidad, servicio y embalaje como aportes ya ponderados. Los límites actuales son 70 para aprobado y 55 para condicional. Deben confirmarse con el procedimiento interno vigente.
- La importación de Power BI utiliza calidad, entrega y certificado, guardando el último en el campo de embalaje. Hay que resolver la interpretación antes de comparar series.
- El ranking operativo usa calidad 40 %, entrega 35 % y respuesta a no conformidades 25 %. La falta de fechas impide calcular el total; la ausencia de un promedio de respuesta NC recibe actualmente 100 puntos. Es necesario distinguir ausencia de incidentes de falta de información.
- El historial filtra por fecha de evaluación y, si falta, por el 1 de enero del año; la pantalla ordena por año/período. Revisar cómo representar evaluaciones anuales y cuatrimestrales juntas.
- La guía [de validación existente](VALIDACION_EVALUACION_PROVEEDORES.md) describe un flujo anterior de métricas; sus ejemplos no deben asumirse como contrato de la evaluación formal actual.

## Etapas propuestas

| Etapa | Trabajo | Resultado verificable |
|---|---|---|
| 1. Acordar reglas | Elegir fuente principal, criterios, pesos, periodicidad, responsable y tratamiento de datos faltantes. Confirmar límites y población de proveedores. | Matriz con definición, fuente, cálculo, peso y evidencia de cada criterio. |
| 2. Diagnosticar datos | Verificar esquema real y cobertura por proveedor/período; revisar duplicados, equivalencias de códigos, fechas y orígenes. Access solo lectura. | Informe de cobertura y faltantes, sin escrituras. |
| 3. Piloto | Elegir tres proveedores con buen desempeño, incidencias y datos incompletos; reconstruir un período y cotejarlo con el cálculo utilizado por Compras/Calidad. | Diferencias explicadas y fórmula acordada. |
| 4. Preparar evaluación | Reutilizar servicios para presentar detalle de indicadores, evidencia, faltantes y propuesta de resultado; revisar antes de guardar la evaluación formal. | Una evaluación reproducible con responsable y observaciones. |
| 5. Mejorar evolución | Mostrar origen/metodología, períodos comparables, desglose, acceso al detalle y advertencias por datos incompletos. Revisar promedio y tendencia al mezclar anual/cuatrimestral. | Historial comprensible y conciliado con la evaluación guardada. |
| 6. Seguimiento | Definir acciones para condicional/no apto, responsable, vencimiento y próxima revisión. | Plan de seguimiento acordado y verificable. |

## Alcance técnico previsto, sujeto a las decisiones

- Tablas a revisar: `proveedor`, `evaluacion_proveedor_anual`, `evaluacion_criterio_detalle`, `recepcion_cabecera`, `recepcion_detalle`, `recepcion_staging`, `recepcion_no_conformidad`. Revisar también snapshots y métricas si se eligen como fuente. No se propone migración hasta verificar el esquema real y las necesidades de trazabilidad.
- Servicios: `evaluacion_service.py`, `evaluacion_csv_recepcion_service.py`, `evaluacion_access_import_service.py`; contrastar con recepción operativa y snapshots sin sustituir sus recorridos.
- Endpoints existentes: `/api/evaluaciones/`, `/api/evaluaciones/proveedor/{id}/historial`, `/api/evaluaciones/ranking-operativo`; conservar endpoint → service → database y permisos por pantalla.
- UI: `app/templates/evaluaciones/index.html` y `evolucion.html`, con Jinja2, fetch y estilos globales existentes. Versionar estáticos si se extrae JavaScript.
- Validaciones futuras: límites 55/70, pesos y total, datos faltantes, períodos/fechas, importación idempotente y equivalencia de criterios, permisos, conciliación con tres casos reales. Ejecutar pytest focalizado, Ruff y comprobación JS cuando haya cambios.

## Próximo paso

Definir si la evaluación debe nacer de recepciones del sistema, de Power BI/Excel o de carga manual; luego construir la matriz de criterios con un período y tres proveedores reales.

## Límites de esta revisión

Se revisaron fuentes y migraciones 010/011/013, además del esquema base UTF-16. No se verificaron esquema vivo, registros reales, Access, Power BI ni pantalla autenticada; no se ejecutaron pruebas porque este avance solo documenta el plan.
