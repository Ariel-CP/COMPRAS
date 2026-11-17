# Evaluación utilizada en Power BI

Inspección: 2026-11-17. Fuente: `TEMP/Evaluacion Proveedores.pbix`, 3.839.888 bytes, modificado el 30/04/2026. SHA-256 `78d02f05a3c05cb93a5ec8c38a92a81b46eb7bdc8bb012d6165c7ace7d6870d9`, igual antes/después. No se refrescó el modelo ni se modificó el archivo.

## Qué se recuperó

El archivo contiene 23 tablas, 14 columnas calculadas de negocio en `CONTROL DE RECEPCION` y ninguna medida DAX del modelo. La página es «Evaluación de Proveedores Insumos». Incluye un cálculo visual para clasificar el promedio. Se extrajeron columnas DAX, Power Query, relaciones, consultas de visuales y valores guardados en el modelo comprimido.

La consulta de recepción usa Access; PROVEEDORES referencia la base de recepción en Power Query, y EVAPROV referencia la base de proveedores. Estas son referencias almacenadas: no se comprobó que una actualización actual del PBIX pueda resolver todos los vínculos. El informe usa la relación activa `CONTROL DE RECEPCION.Codigo Proveedor → PROVEEDORES.CODIGO`.

## Fórmula comprobada

**Total por recepción = Calidad × 0,45 + Entrega × 0,45 + Certificado × 0,10 cuando aplica.**

| Componente | Regla DAX del archivo |
|---|---|
| Calidad (45 %) | PLAN MUESTREO: Simplificada = 100, Normal = 67, Estricta = 33; otro/vacío = BLANK. No se usa directamente porcentaje de piezas aceptadas o Estado para este componente. |
| Entrega (45 %) | Fecha prevista = FECHA EMISION OC + DEMORA_ENTREGA del maestro. Retraso = diferencia en días hasta Fecha de Entrega, mínimo cero. Hasta 21 días adicionales de retraso = 100; más de 21 = 33. |
| Certificado (10 %) | El DAX define 100 si proporción con certificado = 1; 67 si >= 0,01 y < 1; 33 si = 0. Solo se incluye si el maestro indica APLICA CERTIFICADO_CALIDAD = verdadero. |
| Clasificación visual | Promedio >= 70: Aprobado; >= 55 y < 70: Condicional; < 55: No Apto. No usa conversión previa a entero como el antiguo formulario Access. |

Para 3.060 proveedores del maestro guardado, DEMORA_ENTREGA = 21; además existen uno con 0 y uno con 90. Con demora base 21, la regla admite hasta 42 días desde emisión OC para los 100 puntos de entrega. Esto describe el código recuperado, no una nueva regla propuesta.

## Cómo calcula realmente el informe

Aunque algunos nombres de columna dicen «Proveedor», las puntuaciones guardadas varían entre recepciones del mismo proveedor/año. Se verificaron 366 grupos proveedor/año con más de un total. Los visuales solicitan el promedio de `PuntajeTotalProveedor`, con cada recepción ponderada por igual, no por Lote o CANTIDAD OC.

La página filtra **PROVEEDORES.EVALUAR = verdadero** y las consultas de visuales guardadas filtran **Fecha de Entrega >= 01/01/2025 y < 01/01/2026**. No es el filtro por Fecha Control usado en diagnósticos anteriores. Los nombres queryRef internos contienen tanto Sum como Avg, pero las consultas guardadas usan la misma agregación del puntaje rotulado «Puntaje Promedio»; no se debe concluir suma por el nombre queryRef.

## Datos y conciliación del archivo

- 19.827 recepciones guardadas, de varios años.
- 1.115 recepciones con Año derivado de Fecha de Entrega = 2025; tras EVALUAR verdadero: 1.085 recepciones y 54 códigos de proveedor.
- Promedios 2025 por código con ese filtro: **41 Aprobados, 13 Condicionales, ninguno No Apto**. Se reprodujo la agregación desde valores guardados; no se ejecutó el motor de visuales Power BI ni se revisó la UI.
- Ejemplo, código 2: 97 recepciones, promedio 83,16185567; último puntaje guardado 90. Son valores distintos.
- Cero discrepancias en las 19.827 filas para plan→calidad, calidad×45 %, entrega×45 %, certificado×10 % si aplica, y suma con blancos tratados como cero. Entrega coincide también en las 12.614 filas con fechas/plazo verificables.
- Los 1.126 controles/64 códigos del diagnóstico Access anterior corresponden a datos vivos y Fecha Control; no se deben comparar directamente con esta foto del PBIX y Fecha de Entrega.

## Hallazgos que afectan el resultado

1. **Importación del sistema:** `evaluacion_csv_recepcion_service.py` asume puntajes constantes por proveedor/año y toma el último valor. El PBIX demuestra que esa premisa no se cumple: en 32 de los 54 proveedores de 2025 el promedio difiere del último. Hay que conciliar y adaptar ese recorrido antes de usarlo para reproducir el ranking Power BI. No se modificó ni recalculó ninguna evaluación existente.
2. **Certificado no aplicable:** el aporte queda BLANK y no se redistribuye su peso. Calidad y entrega excelentes suman 90, no 100. Si aplica y no hay certificado, el aporte almacenado puede ser 3,3. No confundir ausencia de certificado con no aplicabilidad.
3. **Proporción de certificados:** la columna guardada tiene únicamente 316 valores 1 y 19.511 blancos; no aparecen proporciones intermedias. El código está en una columna calculada, con contexto de fila. Por tanto, no hay evidencia de que esté evaluando una proporción anual por proveedor como podría sugerir su nombre. La rama de 67 puntos no se observa en la proporción guardada.
4. **Fechas faltantes:** las 7.212 recepciones sin emisión OC obtuvieron 33 puntos de entrega. Esto mezcla falta de información con demora efectiva; es un comportamiento existente a revisar, no un criterio nuevo.
5. **Plan faltante:** 7.065 recepciones no tienen plan ni puntaje de calidad; el total continúa sumando los otros componentes. No aparece «Sin evaluación» solo por faltar ese dato.
6. **Modelo distinto del formulario NEW:** esta metodología es automática para insumos, 45/45/10. No es la de 15 criterios manuales 30/60/10 o 35/60/5; la simulación retirada no se restableció.

## Cómo llevarlo al sistema

1. Usar este PBIX como referencia concreta para reproducir el último método de insumos: mismas fuentes, Fecha de Entrega, EVALUAR, aplicabilidad, puntuación por recepción y promedio por proveedor/año.
2. Conciliar tres proveedores y los 54 promedios guardados antes de cambiar la importación o emitir evaluaciones 2025.
3. Separar reproducción fiel de propuestas de mejora (fechas faltantes, no aplicabilidad, porcentaje anual de certificado). Cualquier corrección debe quedar versionada y comparar antes/después; no cambiar silenciosamente las evaluaciones anteriores.
4. Definir por separado la cobertura de servicios y la relación documental con el procedimiento; esta página se titula evaluación de insumos y no demuestra cobertura de todos los proveedores críticos.

## Evidencia y ejecución

Script: `scripts/dev/inspeccionar_pbix_evaluacion.py`. Lector local [PBIXRay](https://github.com/Hugoberry/pbixray), instalado únicamente en `tmp/pbix_tools`; no se cambió el entorno de la API ni se envió el PBIX a servicios externos.

Comando PowerShell, desde el repo:

```powershell
$env:PYTHONPATH = "$PWD\tmp\pbix_tools"
.venv\Scripts\python.exe scripts/dev/inspeccionar_pbix_evaluacion.py 'TEMP/Evaluacion Proveedores.pbix'
```

Resultados en `outputs/evaluacion_powerbi/`: `formulas.dax`, `formulas_dax.json`, `consultas_power_query.json`, `relaciones.json`, `visuales.json`, `resumen.json` y `promedios_2025.json` (por código, sin exportar contactos/correos). Se ejecutó el diagnóstico real y Ruff pasó. No se modificó la aplicación, no se reinició el servidor ni se escribieron bases; no se ejecutaron pruebas funcionales porque este avance solo inspecciona y documenta.
