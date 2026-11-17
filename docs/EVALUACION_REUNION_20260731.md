# Evaluación de proveedores para reunión

El usuario solicitó evaluar 01/01/2026–31/07/2026 con criterios del PBIX y **cero puntos si no tiene certificado**. Se prepararon PDF y Excel; no se modificaron la aplicación, el PBIX, Access ni calificaciones de MariaDB.

## Resultado entregado

- 536 recepciones con Fecha de Entrega desde 01/01/2026 inclusive hasta 01/08/2026 exclusiva, extraídas de Access el 17/11/2026.
- 519 recepciones incluidas y 36 proveedores: **7 aprobados, 28 condicionales y 1 no apto**.
- 17 exclusiones: 16 por EVALUAR falso y una por identidad sin coincidencia exacta única (ID_INT 21205, ALKEN DIVISION METALURGICA S.A.).
- Promedio global ponderado por número de recepciones: 64,21387283 puntos. El ranking clasifica el promedio de cada proveedor con precisión completa, no el último puntaje ni un promedio redondeado.
- No apto calculado: SAITTA SERGIO SALVADOR, código 11316, 52,39285714; tiene 20 de 28 recepciones sin emisión OC. Es necesario revisar ese faltante antes de concluir incumplimiento de plazos o decidir restricciones comerciales.

## Método y datos que condicionan la lectura

Se conservan calidad 45 % (Simplificada 100, Normal 67, Estricta 33) y entrega 45 % del [PBIX inspeccionado](EVALUACION_POWERBI.md): emisión OC + DEMORA_ENTREGA, tolerancia adicional hasta 21 días, después 33 puntos base. Se conserva la penalización de 33 cuando falta emisión OC, pero se señala expresamente. Certificado aporta 10 únicamente si existe y aplica; ausencia/falso/no aplicabilidad aporta 0, sin redistribución del peso. Todas las 519 recepciones incluidas tienen el indicador de certificado falso y aporte cero.

Se detectaron **411 recepciones con código origen 0 y 39 nombres distintos**. El join literal del PBIX las atribuiría a YPF GAS del maestro. No se entregó esa atribución incorrecta: se contrastó código y nombre; ante inconsistencia se admitió exclusivamente nombre exacto único, normalizando solo espacios y mayúsculas. Se reasociaron 399 recepciones incluidas. No hubo coincidencias aproximadas, ediciones en Access ni cambios de sus códigos; el Excel conserva ID_INT, código/nombre original y método de asociación en Recepciones, columnas U:W. El resultado preliminar 26 proveedores/20 aprobados/6 condicionales fue descartado tras esta verificación de identidad.

Las 415 recepciones sin emisión OC afectan 33 proveedores; no faltan plan de muestreo ni plazo del maestro en las incluidas. Los resultados conservan esa penalización del PBIX y no deben interpretarse como prueba de atraso real cuando falta la OC.

EVALUAR, aplicabilidad y plazo proceden del maestro **actual**; no se reconstruyó su estado al 31/07/2026. El alcance reproduce el filtro EVALUAR del informe de insumos; no demuestra evaluación completa de todos los proveedores de servicios/críticos.

## Archivos y validación

En `outputs/evaluacion_proveedores_20260101_20260731/`:

- `Evaluacion_proveedores_2026_01_01_al_07_31.pdf`: tres páginas, resumen, reglas, advertencias y ranking completo. Renderizadas e inspeccionadas todas las páginas finales.
- `Evaluacion_proveedores_2026_01_01_al_07_31.xlsx`: Ranking, Recepciones (519 filas), Excluidas (17 filas) y Metodo. Cálculos por recepción y promedio por proveedor mediante fórmulas, sin errores de Excel; todas las fórmulas de puntaje y agregados se contrastaron con cálculo independiente Decimal. Revisadas vistas de las cuatro hojas. Fuente y procedencia visibles.
- `evaluacion.json`: extracción y cálculo reproducibles, con identidad original conservada.

Script de extracción/cálculo/PDF: `scripts/dev/evaluar_proveedores_reunion.py`. Pruebas: `tests/test_evaluacion_reunion.py` (7 aprobadas); Ruff aprobado. Constructor de Excel: `tmp/reunion_20260731/build.mjs`, con Artifact Tool del runtime y dependencia enlazada por junction; sin alterar dependencias. PDF mediante reportlab del runtime. Se utilizaron las skills PDF y hojas de cálculo.

No se ejecutaron pruebas de interfaz/API ni se reinició servidor porque no hubo cambios funcionales. No se guardaron resultados de negocio, no se emitieron correos ni se dieron bajas de proveedores. Próximo paso: usar los archivos en reunión y revisar fechas OC e identidad pendiente antes de adoptar acciones o persistir calificaciones.
# Actualización del criterio — 17/11/2026

El usuario indicó considerar dentro del plazo todas las recepciones sin OC. Se aplica cuando falta FECHA EMISION OC: base entrega 100 y aporte 45/45, sin inventar fechas ni modificar Access. La ausencia de certificado sigue aportando cero. PDF y Excel regenerados; 519 recepciones/36 proveedores: 35 aprobados, 1 condicional, 0 no aptos. SAITTA 11316 pasa de 52,39 a 73,93. Los resultados anteriores que siguen documentados corresponden a la versión previa, ya reemplazada para el cálculo vigente.
