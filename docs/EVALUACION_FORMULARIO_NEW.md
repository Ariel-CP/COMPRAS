# Fórmulas recuperadas del formulario confirmado

Fecha: 2026-11-17. El usuario confirmó `EVALUACION DE PROVEEDORESNEW` como formulario de referencia.

## Estado actual

El usuario eligió conservar la fórmula histórica, pero luego solicitó retirar el último desarrollo. La simulación anual 2025 fue retirada el 17/11/2026; esta nota conserva únicamente la investigación y las fórmulas recuperadas. La vista previa histórica anterior permanece disponible.

## Extracción verificada

Se copió el frontend `Gestion de Evaluación de Proveedores Server270622.accdb` a `tmp/access_form_inspection/evaluacion_inspeccion.accdb`. Microsoft Access abrió únicamente la copia, con `AutomationSecurity=3` (macros deshabilitadas). Se ejecutó `SaveAsText` del diseño, sin abrir el formulario ni ejecutar sus eventos, y se cerró la instancia creada sin guardar. No se cambiaron vínculos ni archivos originales.

Diseño completo: `tmp/access_form_inspection/evaluacion_proveedores_new.txt` (UTF-16). Extracto UTF-8 de 21 rutinas de cálculo, sin rutinas de envío ni operaciones de botones: `outputs/evaluacion_proveedores/formulas_formulario_new.bas`. La inspección del código fue estática; no se ejecutó VBA de negocio.

## Escala y ponderación comprobadas

Las respuestas son Excelente = 5, Suficiente = 3, Insuficiente = 0. Los valores vacíos no deben convertirse automáticamente en ninguna respuesta.

| Bloque | Insumos | Servicios | Fórmula fuente |
|---|---:|---:|---|
| Calidad: especificaciones / experiencia en el rubro | 25 | 20 | PV / 5 × peso |
| Calidad: certificado / calidad del personal | 3 | 10 | PV / 5 × peso |
| Calidad: innovación | 2 | 5 | PV / 5 × peso |
| Servicio: cumplimiento (tres criterios) | 35 | 35 | suma PV / 15 × 35 |
| Servicio: asistencia (tres criterios) | 20 | 20 | suma PV / 15 × 20 |
| Servicio: stock y comunicación (dos criterios) | 5 | 5 | suma PV / 10 × 5 |
| Embalaje (cuatro criterios) | 10 | 5 | suma PV / 20 × peso |
| Máximo total | 100 | 100 | Calidad + Servicio + Embalaje |

Las funciones `INS()` y `SER()` cambian pesos y rótulos según tipo de proveedor. Los pesos de Servicio 35/20/5 están en los valores predeterminados de los controles Texto68/69/70; sus rutinas AfterUpdate aplican las fórmulas indicadas.

Insumos, cumplimiento: tiempo de entrega, disponibilidad ante reclamo, relación precio/mercado. Asistencia: asistencia posventa, servicio de entrega, condiciones de pago. Último grupo: stock terminado y comunicación.

Servicios cambia los rótulos a tiempo garantizado, capacidad de diseño y alcance; luego puntos de posventa, garantía y forma de pago; finalmente stock de repuestos e información complementaria. No son exactamente los mismos conceptos aunque se guarden en las mismas columnas.

## Comportamientos que no deben migrarse inadvertidamente

- `P_calSum`, `p_serSum` y `Cal_TotSum` redondean componentes y totales mediante `Round(..., 2)` de VBA. Verificar casos intermedios y representación Double frente a Decimal antes de declarar equivalencia bit a bit.
- `Calificar()` asigna el total decimal a `Temp As Integer` antes de aplicar intervalos 70–100, 55–69 y 0–54. Esto puede cambiar el resultado cerca de 55 y 70; no equivale a comparar directamente el decimal como hace hoy el backend Python.
- Embalaje asigna `P_EMB = Val(Texto152.Value)`. Debe verificarse el comportamiento con separador decimal de Windows; no copiar posibles truncamientos como regla de negocio. Ya existen históricos con PP_Embalaje fraccionario y P_EMB entero.
- El código calcula después de cada cambio de respuesta; un campo almacenado puede estar desactualizado o incompleto. Las diferencias históricas encontradas deben conservarse y explicarse, no corregirse sin auditoría.

## Diferencia documental que requiere decisión

El diseño exportado dice **VERSION 11**, con Calidad/Servicio/Embalaje. El procedimiento aportado V13 define Cumplimiento en insumos/servicios, Gestión y Post contractual y remite al registro B para los criterios. Recuperar la fórmula elimina la incertidumbre sobre este formulario, pero no demuestra su correspondencia con V13.

La consulta quedó resuelta por el usuario: conservar fórmula histórica del formulario confirmado. Se mantiene explícitamente su identificación V11; no se declara equivalencia documental con V13.

## Próximo paso concreto

Tras la decisión documental, versionar el cálculo por tipo de proveedor, construir pruebas con respuestas completas y casos límite, y conectar evidencia 2025 a la captura. Los controles de recepción no permiten responder automáticamente criterios comerciales, experiencia, innovación, stock o posventa. No arrastrar respuestas antiguas a 2025 sin validación del evaluador.
