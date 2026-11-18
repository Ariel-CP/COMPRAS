# Ranking e historia de proveedores

## Informe de Calidad con formato de la imagen · 18/11/2026

El usuario confirmó que se deben usar **los datos actuales del período seleccionado**,
con la distribución del informe de referencia, sin reproducir su resultado histórico.
El botón **Informe de Calidad** abre una vista independiente y autónoma con:

- Encabezado «Objetivos de la Calidad / Proveedores», año y período reales.
- Gráfico vertical de **todos** los proveedores, ordenado de mayor a menor, con
  umbrales 70/55 y escala 0–100. Los nombres completos/puntajes están en los títulos SVG.
- Tabla de los siete menores puntajes (o todos si hay menos), mostrando código,
  proveedor, puntaje y categoría; el pie usa el promedio general de todas las recepciones.
- Recuadro del período, medidor general 0–100, tabla de categorías y pie de empresa/fecha.
- Notas breves de cobertura, metodología y límites de comparación entre años.

Incluye **Imprimir / guardar PDF** con A4 horizontal. El informe principal ocupa una
hoja; si se consultó una historia y sigue visible, se conserva como apéndice en página
separada. **Preparar email** adjunta este mismo HTML, sin servicios externos ni envíos.
La referencia de 77,83 del dashboard no sustituye los datos actuales en el informe.
Los cuatrimestres/semestres solo se rotulan como tales si sus fechas están completas;
enero–julio se muestra con sus fechas exactas.

Módulo `app/static/js/evaluacion_informe_calidad.js`, integrado en plantilla y JS del
ranking, con recursos versionados. Genera el documento desde el resultado consultado,
sin modificar fuentes, cálculos, tablas ni endpoints. Escapa nombres/códigos y no
carga recursos de red. El botón se invalida al cambiar fechas, como el anterior.
La ruta de impresión formal anterior no fue reemplazada.

Validación: seis pruebas Node (cuatro del informe y dos de email), sintaxis de ambos
JS, Jinja/orden de scripts y revisión visual de PDF renderizado con Edge sin ventana.
Una página 842×595 puntos, dato general 88,84 y 36 barras verificados con datos reales
01/01–31/07/2026; captura en `tmp/pdfs/informe_calidad-1.png`. PDF y HTML entregables
en `output/pdf/evaluacion_proveedores_20260101_20260731.*` (excluidos de Git).
No se verificó sesión autenticada ni apertura del borrador en Outlook; no se envió correo.

## Puntaje general y referencia histórica · 18/11/2026

Se agregó arriba del ranking un medidor de 0 a 100 con porcentaje/puntaje y categoría
general. La agregación reproduce la del medidor del PBIX inspeccionado:
`Avg(CONTROL DE RECEPCION.PuntajeTotalProveedor)` (visual `gauge` en
`outputs/evaluacion_powerbi/visuales.json`). Se promedian **todas las recepciones
evaluadas**, cada una con el mismo peso; no es el porcentaje de proveedores aprobados,
ni la media simple de los promedios por proveedor, ni solo los 20 mejores/peores.
Excluidos no participan; sin recepciones evaluables devuelve null y «Sin calificación».
Se mantiene Decimal y clasificación sin redondeo; la pantalla muestra dos decimales.

La imagen aportada por el usuario informa 77,83 para el 3.º cuatrimestre 2024. Se
muestra como **referencia histórica informada**, no recalculada ni guardada como
evaluación formal. La diferencia se expresa en puntos sobre 100. El período y el
valor histórico son editables; se conservan como preferencia del navegador en
`evaluacion-ranking-referencia-v1`. No alteran fuentes ni puntajes. El medidor y la
comparación se incluyen al imprimir y al preparar el email.

Para comparar años se requieren períodos equivalentes y los mismos criterios.
La agregación del medidor coincide con la del PBIX inspeccionado, pero los ajustes
actuales de OC sin fecha, certificados e identificación de proveedores difieren de
los históricos. No se comprobó el cálculo de 77,83 ni se declara una mejora comparable
con ese dato. La pantalla conserva esta distinción junto al resultado.

Lectura real 01/01–31/07/2026: 519 recepciones/36 proveedores; promedio
88,84248554913294797687861272 → **88,84/100, Aprobado**; diferencia aritmética
respecto de 77,83: **+11,01 puntos**. Evidencia local en
`outputs/ranking_ui/ranking_general_2026.json`. Sin escrituras Access/MariaDB.
Service/schema de ranking ampliados; endpoint existente, sin migración ni cambios
en los puntajes individuales. Recursos CSS/JS versionados. Verificados 45 tests
Python (incluyen pesos distintos por proveedor, exclusiones y ausencia de datos),
Ruff, Black por API, Jinja/IDs, sintaxis JS y dos pruebas Node de email. No se hizo
revisión visual autenticada: la conexión al navegador agotó el tiempo de espera.

## Detalles contraíbles · 18/11/2026

El bloque de recepciones, faltantes, asociaciones, certificados, exclusiones y enlaces
a controles queda contraído inicialmente bajo «Detalles y advertencias de la evaluación».
Se abre/cierra con el control nativo `details/summary`, también por teclado. Conserva
el estado al recalcular dentro de la página; impresión lo abre temporalmente y restaura
el estado después. El adjunto del borrador de email incluye el bloque abierto.
Verificados sintaxis JS, render Jinja/HTML y estado inicial contraído; sin revisión
visual autenticada. No se alteran datos ni cálculo.

## Evidencia de certificado · 18/11/2026

Metodología actual: `PBIX-45-45-10-CERTIFICADO-EVIDENCIA-V2-SIN-OC-EN-PLAZO`.
El ranking y la historia reconocen el certificado por cualquiera de estas fuentes de
`CONTROL DE RECEPCION`: `TieneCertificado`, `ADJUNTO` no vacío o `NOTA` que documenta
recepción/entrega/adjunto o uso concreto del certificado (por ejemplo, dureza informada
mediante el certificado de calidad). El usuario confirmó expresamente que **todos los
adjuntos son certificados**, incluidos escaneos/fotos de nombre genérico. Se leen los
nombres que devuelve ODBC; no se abren archivos ni se valida su contenido.

«Cumple con los requisitos del certificado de calidad y especificaciones técnicas» y
leyendas similares solas no acreditan recepción. Tampoco instrucciones futuras ni
referencias a instrumentos en certificación. Los patrones contemplan acentos y
mayúsculas y descartan notas de ausencia; no hacen interpretación libre de todo texto.
Cuando una nota negativa contradice un adjunto o la casilla, se reconoce esa evidencia
y se muestra advertencia con enlaces al control por `ID_INT`, bajo los permisos existentes.
Fuentes y conflicto se conservan por recepción en el resultado interno para auditoría.
El resumen público muestra cantidades por fuente (pueden superponerse) y controles
con contradicciones. No se duplican puntos. Continúan 10 puntos solo si aplica según el
maestro; ausencia/no aplicabilidad aportan cero, sin redistribuir pesos.

Comparación real 01/01–31/07/2026: 536 controles, 519 evaluados y 36 proveedores,
sin cambios de identidad/exclusiones. Antes, ninguna casilla activa; ahora hay 39
recepciones evaluadas con evidencia (31 adjuntos, 8 notas). Cambian cinco proveedores:
CHEMISA 90→100; Poliuretano y Plástico Proyectado 90→100; Vibrantz 90→100;
Ánodos Magnalum 90→99,09; Akzo Nobel 69,90→76,57. Resultado: 36 aprobados.
Las ocho notas no generan puntos cuando el maestro dice que no aplica.
Control 20787: adjunto presente y nota previa de falta, conservados y señalados.
Comparación y evidencia local en `outputs/ranking_ui/certificados_comparacion.json`.
No se reescribieron Access, evaluaciones formales, archivos PDF/Excel anteriores ni PBIX.

Verificado: 44 pruebas Python, dos Node de email, Ruff, formato Black por API directa,
sintaxis JS, Jinja y diff; API reiniciada, `/health` 200, campos nuevos en OpenAPI y
endpoint protegido 401 sin sesión. Black CLI se detuvo por bloqueo del proceso; la
verificación directa confirmó el formato de los tres Python. Sin revisión visual
autenticada contra servidor. Recargar la página y volver a analizar el período.

### Comprobación de archivos incrustados

A pedido del usuario se verificó el contenido real por DAO: `ADJUNTO` es tipo 101
(Attachment), no un campo de texto/vínculo. `OpenDatabase` con ReadOnly=True y
recordset snapshot, leyendo `FileData` sin extraer/abrir documentos. Enero–julio 2026:
536 controles revisados, 39 con adjunto, 53 archivos, ninguno vacío. Los 31 controles
con ADJUNTO incluidos en la evaluación tienen bytes incrustados; no hay faltantes.
El resto corresponde a controles excluidos de la evaluación por las reglas existentes.
Control 20787: archivo `iso-plus PM  Lote 19011.pdf`, tipo PDF, 370.954 bytes.
Evidencia local en `outputs/ranking_ui/adjuntos_verificados_dao.json`. Se comprobó
existencia y tamaño; no se interpretó ni validó el contenido de los certificados.
Sin escrituras en Access ni cambios del cálculo.

## Disposición de gráficos · 18/11/2026

El ranking muestra barras verticales con puntajes sobre cada barra y nombres inclinados;
los 20 mejores ocupan el panel superior y los 20 peores el siguiente, ambos a todo el ancho.
En móvil los gráficos permiten desplazamiento horizontal. Se conserva la selección de
historia por clic/teclado, las tablas y el orden del servicio. La impresión y el borrador
de email reutilizan los gráficos verticales. Recursos CSS/JS versionados en la plantilla.
Verificados sintaxis JS, geometría SVG de 20 barras (incluido puntaje cero), selección
por clic/teclado y dos pruebas de email. No se hizo revisión visual autenticada.

## Rechazos de los 20 peores

La tabla muestra la cantidad de controles con Estado `RECHAZADO` (sin distinguir mayúsculas ni espacios extremos) en las recepciones evaluadas del período. Desplegar la celda permite abrir cada control por `ID_INT` en `/ui/recepcion/historial-access?access_id=...`, en otra pestaña. El historial abre directamente sus observaciones y cotas/mediciones. Conserva los permisos existentes de historial Access; no se transforma el ID en número interno ni se enlaza a una recepción canónica distinta. La asociación al proveedor reutiliza la identidad del ranking, incluido nombre exacto único ante código 0. La cantidad de rechazos no cambia el puntaje PBIX.

Verificado con 37 pruebas focalizadas, Ruff y sintaxis de ambos JS. Lectura Access real enero–julio 2026: dentro de los 20 peores, SAITTA tiene un rechazo, ID_INT 20752, entrega 09/03/2026; comprobado detalle con Estado RECHAZADO. Edge con respuestas locales reales verificó celda, enlace exacto, gráficos e historia sin errores JS y sin desbordamiento móvil. No se comprobó la navegación con sesión autenticada del usuario en servidor.

## Preparar email

El botón **Preparar email** descarga un borrador `.eml` para abrir con Outlook u otro cliente compatible. El usuario completa el destinatario y realiza el envío desde su cliente. No se configuró SMTP ni se envían correos desde el servidor. La apertura como borrador depende del cliente instalado y su asociación con `.eml`; no se probó Outlook real.

El adjunto HTML autónomo incluye el período analizado, reglas, advertencias, rankings, gráficos y la historia únicamente si está visible. Se genera desde los resultados ya consultados, sin solicitudes a servicios de correo. No adjunta el PDF fijo de enero–julio a otros períodos. El botón se desactiva ante cambios de fechas o sin proveedores evaluables. Se conserva UTF-8 y MIME base64. Archivos: `app/static/js/evaluacion_email.js`, `app/static/js/evaluacion_ranking.js`, plantilla de ranking y `tests/evaluacion_email.test.cjs`. Validado con dos pruebas Node y Edge sin interfaz: descarga `.eml`, adjunto con gráficos/historia sin scripts ni formularios, sin errores JS y bloqueo de resultados obsoletos. No se enviaron mensajes reales.

Actualización 17/11/2026: por pedido expreso, toda recepción sin emisión OC se considera dentro del plazo (base 100, aporte 45/45). Se conserva el aviso y la fecha vacía en origen. Es una adaptación adicional del PBIX, identificada como `PBIX-45-45-10-CERTIFICADO-AUSENTE-0-SIN-OC-EN-PLAZO`. Con este criterio enero–julio 2026 tiene 35 aprobados, 1 condicional y 0 no aptos; SAITTA obtiene 73,93. Los resultados de la validación inicial descrita abajo corresponden al criterio anterior.

Implementado el 17/11/2026 en `/ui/evaluaciones/ranking`. El período inicial es 01/01/2026–31/07/2026; se puede cambiar Desde/Hasta. Muestra hasta 20 mejores y 20 peores con gráficos, tablas y selección del proveedor. Si hay menos de 40, ambos listados pueden compartir proveedores. El selector incluye todos los evaluados del período. Exporta el ranking completo a CSV y permite imprimir la vista.

La historia se agrupa por año o mes, para todo lo disponible hasta la fecha final o solo el período seleccionado. Es una reconstrucción con los criterios PBIX y el maestro actual; no representa evaluaciones formales guardadas ni reconstruye versiones anteriores del maestro. Los períodos sin recepciones no reciben puntaje. Ver [criterios Power BI](EVALUACION_POWERBI.md) y [conciliación del informe](EVALUACION_REUNION_20260731.md).

## Implementación

- Servicio `app/services/evaluacion_powerbi_service.py`: lectura Access parametrizada, conexión cerrada y lock compartido; caché de 60 segundos con hasta seis períodos. Sin migraciones ni escrituras en Access o MariaDB.
- GET `/api/evaluaciones/powerbi/ranking?desde=2026-01-01&hasta=2026-07-31` devuelve resumen, lista completa y ambos rankings.
- GET `/api/evaluaciones/powerbi/proveedor/{codigo}/historial?hasta=2026-07-31&agrupacion=anual` admite `desde` opcional y agrupación `mensual`.
- Ranking exige permiso de lectura `ui_evaluaciones_ranking`; historia admite también `ui_evaluaciones_evolucion`. Se mantienen los endpoints de evaluaciones formales.
- Plantilla Jinja, JS y CSS locales versionados. Cambiar fechas oculta resultados anteriores; aborta consultas reemplazadas. Gráficos SVG con tablas alternativas. CSV escapa contenido y protege celdas de texto contra fórmulas.

## Validación

51 pruebas focalizadas aprobadas, Ruff aprobado y sintaxis JS comprobada. Lectura real del período conciliada proveedor por proveedor contra el informe: 536 recepciones, 519 incluidas, 17 excluidas, 36 proveedores; 7 aprobados, 28 condicionales y 1 no apto. Cero diferencias de puntaje.

Edge sin interfaz comprobó 20 filas por ranking, historia anual de siete períodos y mensual de cuatro para el proveedor 11316, cambio de fechas sin resultados obsoletos, ausencia de errores JS y ancho móvil de 390 px sin desbordamiento de página. Se usó HTML renderizado por la aplicación y respuestas locales capturadas de Access real. Capturas en `outputs/ranking_ui/`. No se verificó una sesión autenticada del usuario contra el servidor en navegador.

Servidor del proyecto reiniciado; `/health` 200, ambos endpoints presentes en OpenAPI y petición sin sesión rechazada con 401. Los avisos de datos incompletos se conservan: 415 recepciones incluidas sin emisión OC para el período inicial. Antes de decisiones comerciales, revisar esas fechas y la identidad ambigua excluida.
