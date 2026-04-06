# Orden de archivos (micro-plan de 10 minutos)

Objetivo: ordenar el sistema por capas sin mover archivos de forma riesgosa.

## Reglas simples (desde ahora)

1. Endpoints: solo validan entrada/salida y delegan a servicios.
2. Servicios: contienen la logica de negocio y transacciones.
3. Schemas: contratos Pydantic de request/response.
4. Modelos: acceso a datos/estructuras internas.
5. Base de datos: `database/schema.sql` es fuente de verdad; cambios solo con migracion.
6. Scripts: separar operativos de debug/pruebas manuales.

## Estructura objetivo

- `app/api/` routers HTTP y vistas UI.
- `app/services/` reglas de negocio por dominio (`auth`, `mbom`, `stock`, `plan`, `precios`).
- `app/schemas/` contratos API.
- `app/models/` modelos internos/datos.
- `database/migrations/` cambios versionados de SQL.
- `scripts/ops/` scripts de operacion (deploy, backup, seed).
- `scripts/dev/` scripts de debug/prueba local.

## Checklist rapido (30-60 min por bloque)

1. Crear subcarpetas: `scripts/ops` y `scripts/dev`.
2. Mover primero scripts obvios de debug a `scripts/dev` (sin renombrar).
3. Dejar un `README.md` corto en `scripts/` con que corre en prod y que no.
4. En cada endpoint nuevo, prohibir SQL directo y usar siempre `services/`.
5. Agregar validacion minima en PR: lint + tests.

## Criterio de exito

- Cualquier archivo nuevo cae en un lugar evidente.
- Se reduce la mezcla entre codigo productivo y scripts de desarrollo.
- Nadie necesita adivinar donde vive una regla de negocio.
