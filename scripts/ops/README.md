# Scripts Operativos

Scripts para administración, sincronización, migraciones y operaciones de mantenimiento del proyecto.

## sync_db_from_raspi.py

**Sincroniza la base de datos local desde la Raspberry (compras-dev).**

Este script descarga un dump MySQL de la Raspberry y lo restaura en tu base de datos local, convirtiéndola en un espejo de producción.

### Requisitos

- Acceso SSH a `compras-dev`
- MySQL/MariaDB instalado localmente
- Paramiko instalado: `pip install paramiko`

### Uso

**Opción 1: PowerShell (Windows)**

```powershell
.\scripts\ops\sync_db_from_raspi.ps1
```

**Opción 2: Python directo**

```bash
python scripts/ops/sync_db_from_raspi.py
```

### Configuración (variables de entorno)

El script toma estos valores desde entorno. Si faltan passwords, los pide por consola de forma segura.

| Variable | Default |
|---|---|
| `RASPI_HOST` | `compras-dev` |
| `RASPI_USER` | `acepeda` |
| `RASPI_DB_NAME` | `compras_db` |
| `RASPI_DB_USER` | `compras` |
| `RASPI_DB_PASS` | *(sin default, prompt)* |
| `RASPI_SSH_PASS` | *(sin default, prompt)* |
| `LOCAL_DB_HOST` | `127.0.0.1` |
| `LOCAL_DB_PORT` | `3306` |
| `LOCAL_DB_NAME` | `compras_db` |
| `LOCAL_DB_USER` | `root` |
| `LOCAL_DB_PASS` | *(sin default, prompt)* |

Ejemplo en PowerShell (opcional):

```powershell
$env:RASPI_HOST = "compras-dev"
$env:RASPI_USER = "acepeda"
$env:RASPI_DB_NAME = "compras_db"
$env:RASPI_DB_USER = "compras"
$env:LOCAL_DB_HOST = "127.0.0.1"
$env:LOCAL_DB_PORT = "3306"
$env:LOCAL_DB_NAME = "compras_db"
$env:LOCAL_DB_USER = "root"
```

### Flujo de ejecución

1. **Toma credenciales** desde entorno o solicita passwords por consola
2. **Genera dump MySQL** en la Raspberry
3. **Descarga el dump** vía SSH
4. **Restaura la BD local** usando cliente `mysql` con los datos de la Raspberry
5. **Guarda backup** en `backups/compras_db_sync_YYYYMMDD_HHMMSS.sql`

### Notas importantes

- ⚠️ **Destructivo**: Sobrescribe tu BD local. Asegúrate de tener backup antes.
- El dump se descarga en la carpeta `backups/` para referencia.
- Soporta contraseñas con caracteres especiales.
- Si el dump es muy grande, puede tardar varios minutos.

### Troubleshooting

**Error: "No se encontró Python en .venv"**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Error: "Connection refused" a Raspberry**
- Verifica que `compras-dev` está accesible en la red
- Prueba: `ping compras-dev`
- Verifica credenciales SSH

**Error: "Access denied" MySQL local**
- Verifica que MariaDB/MySQL está corriendo: `mysql -u root -p`
- Verifica contraseña local

---

## Otros scripts operativos

- `seed_admin.py` - Crea usuario administrador inicial
- `seed_roles.py` - Popula roles de usuario
- `sync_tipo_cambio.py` - Sincroniza tipos de cambio con BCRA
- `deploy_raspberry.ps1` - Deploy automático en Raspberry
- `update.sh` - Script de actualización en Raspberry
