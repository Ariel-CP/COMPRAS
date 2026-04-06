# Scripts del proyecto

Esta carpeta esta separada por uso para evitar confusiones:

- `scripts/ops`: scripts operativos o de administracion (seed, sync, deploy, migracion).
- `scripts/dev`: scripts de debug, inspeccion y pruebas manuales locales.

## Regla de uso

1. Si un script se ejecuta en entornos productivos o de mantenimiento controlado, va a `ops`.
2. Si es para diagnostico local, pruebas puntuales o exploracion, va a `dev`.
3. Evitar referenciar rutas absolutas en scripts nuevos.

## Nota

Si tenias comandos guardados con rutas anteriores (por ejemplo `scripts/seed_admin.py`), actualizalos a la nueva ubicacion (`scripts/ops/seed_admin.py` o `scripts/dev/...`).
