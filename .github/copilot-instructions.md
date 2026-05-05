Estas instrucciones quedan reducidas a un puntero para evitar divergencia.

Fuente canónica para el workspace: [AGENTS.md](../agents.md)

Reglas mínimas que siguen vigentes aquí:

- Leer [database/schema.sql](../database/schema.sql) antes de asumir estructura de datos.
- Mantener `endpoint -> service -> database`.
- Para cambios grandes, planificar primero tablas, endpoints, services y validaciones.
- En UI, respetar el patrón Jinja2 + fetch + CSS global existente.

Si hace falta detalle adicional, enlazar documentación existente en vez de duplicarla.
