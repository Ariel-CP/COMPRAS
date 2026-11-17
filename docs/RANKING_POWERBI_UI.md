# Ranking e historia de proveedores

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
