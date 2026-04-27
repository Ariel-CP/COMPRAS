# Migración: Tabla Proveedor

## Descripción

Se ha creado la tabla `proveedor` en la base de datos `compras_db` para soportar el módulo de gestión de proveedores.

### Cambios
- **Tabla**: `proveedor` con 14 columnas (id, codigo, nombre, contacto_nombre, email, telefono, cuit, direccion, localidad, provincia, notas, activo, fecha_creacion, fecha_actualizacion)
- **Índices**: Unique en codigo, índices en activo y provincia
- **Datos existentes**: 3,451 proveedores

## Aplicar Migración

### En máquina local (Windows)
```powershell
cd h:\COMPRAS
Get-Content database/migrations/001_create_proveedor_table.sql | mysql -u compras -p"matete01" -h 127.0.0.1 compras_db
```

### En Raspberry Pi (Linux)
```bash
cd compras-api
git pull origin master
bash database/apply-migrations.sh
```

## Verificación

Confirmar que la tabla existe:
```sql
SHOW TABLES LIKE 'proveedor';
DESCRIBE proveedor;
SELECT COUNT(*) FROM proveedor;
```

## Despliegue
- ✅ **Local**: Migración aplicada (3,451 proveedores)
- ⏳ **Raspberry**: Pendiente de ejecutar apply-migrations.sh

## Referencias
- Migración: `database/migrations/001_create_proveedor_table.sql`
- Script de aplicación: `database/apply-migrations.sh`
- Modelo ORM: `app/models/proveedor.py`
- API: `app/api/proveedores.py`
- UI: `app/api/ui_proveedores.py`
