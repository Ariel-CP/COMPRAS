---
mode: agent
description: "Diagnostica y corrige bugs o pequeños cambios en COMPRAS siguiendo la arquitectura real del repo y la validación mínima necesaria."
tools: ["codebase", "search", "editFiles", "runCommands"]
---

# Tarea

Resuelve el problema o cambio solicitado en este workspace de COMPRAS.

## Entrada

- Descripción del problema / feature: $input
- Contexto adicional o archivos relevantes: $selection

## Objetivo

Implementar la corrección o mejora con el menor alcance posible, preservando la arquitectura del proyecto y evitando cambios innecesarios.

## Reglas obligatorias

1. Leer [database/schema.sql](../../database/schema.sql) antes de asumir tablas, enums, checks o relaciones.
2. Mantener el flujo endpoint -> service -> database; no poner lógica de negocio sustancial en routers.
3. Revisar [app/main.py](../../app/main.py) y [app/api/router.py](../../app/api/router.py) cuando se toque autenticación, middleware, rutas o registro de endpoints.
4. Si el cambio afecta UI, respetar el patrón del repo: Jinja2 en [app/templates](../../app/templates), fetch a API y estilos globales en [app/static/css/estilos.css](../../app/static/css/estilos.css).
5. Mantener los scripts y migraciones en la estructura indicada por [scripts/README.md](../../scripts/README.md).
6. Si no existe una prueba focalizada, validar con la comprobación más directa posible: `ruff check`, arranque de la API o una verificación localizada del flujo afectado.
7. No inventar tablas, columnas o procesos si ya existen en el schema o en la lógica actual.

## Flujo recomendado

- Revisar el problema real y localizar el punto de entrada correcto.
- Confirmar si la lógica pertenece a router, service o script antes de editar.
- Buscar referencias relevantes en código y schema.
- Hacer el cambio mínimo y verificable.
- Validar el comportamiento con la comprobación más directa y documentar el resultado.

## Salida esperada

Entregar:

- un resumen breve del problema y la solución,
- los archivos principales tocados,
- la validación ejecutada y su resultado,
- y una nota si faltan pruebas automatizadas o si hay un riesgo de follow-up.

## Ejemplos de uso

- "Corrige el error de autenticación al entrar a /ui/proveedores; no debe redirigir al login cuando la sesión es válida."
- "Agrega validación al endpoint de recepciones para rechazar cantidades negativas cuando el proveedor no está activo."
- "Revisa una pantalla de inventario y ajusta el fetch y el render del template para que muestre los datos correctos."

## Sugerencias adicionales

- Crear prompts derivados para tareas más específicas, por ejemplo: migraciones SQL, importación de datos, validación de UI, o debugging de auth.
- Si se necesita más detalle, convertir este prompt en una versión más estricta por módulo o por tipo de cambio.