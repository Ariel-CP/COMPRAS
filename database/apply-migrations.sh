#!/usr/bin/env bash
# apply-migrations.sh — Aplica migraciones SQL a compras_db
# Uso: ./apply-migrations.sh

set -Eeuo pipefail
shopt -s nullglob

log() { echo "[migrations] $*"; }
fail() { echo "[migrations][error] $*" >&2; exit 1; }

# Detectar credenciales desde variables de entorno o usar defaults.
# Si no están seteadas, intenta derivarlas desde DATABASE_URL en .env.
DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-}"
DB_USER="${DB_USER:-}"
DB_PASS="${DB_PASS:-}"
DB_NAME="${DB_NAME:-}"

load_db_from_dotenv() {
    local repo_root env_file
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    env_file="${repo_root}/.env"

    if [[ ! -f "$env_file" ]]; then
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        return
    fi

    eval "$(python3 - "$env_file" <<'PY'
import shlex
import sys
from urllib.parse import urlparse

env_file = sys.argv[1]
database_url = ""
with open(env_file, "r", encoding="utf-8") as fh:
    for line in fh:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "DATABASE_URL":
            database_url = value.strip().strip('"').strip("'")
            break

if not database_url:
    raise SystemExit(0)

parsed = urlparse(database_url)
host = parsed.hostname or "127.0.0.1"
port = str(parsed.port or 3306)
user = parsed.username or "compras"
password = parsed.password or ""
name = (parsed.path or "/compras_db").lstrip("/") or "compras_db"

print(f"DOTENV_DB_HOST={shlex.quote(host)}")
print(f"DOTENV_DB_PORT={shlex.quote(port)}")
print(f"DOTENV_DB_USER={shlex.quote(user)}")
print(f"DOTENV_DB_PASS={shlex.quote(password)}")
print(f"DOTENV_DB_NAME={shlex.quote(name)}")
PY
)"

    DB_HOST="${DB_HOST:-${DOTENV_DB_HOST:-}}"
    DB_PORT="${DB_PORT:-${DOTENV_DB_PORT:-}}"
    DB_USER="${DB_USER:-${DOTENV_DB_USER:-}}"
    DB_PASS="${DB_PASS:-${DOTENV_DB_PASS:-}}"
    DB_NAME="${DB_NAME:-${DOTENV_DB_NAME:-}}"
}

load_db_from_dotenv

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-compras}"
DB_PASS="${DB_PASS:-matete01}"
DB_NAME="${DB_NAME:-compras_db}"

log "Conectando a $DB_HOST:$DB_PORT / $DB_NAME como $DB_USER..."

# Verificar que mysql está disponible
if ! command -v mysql &> /dev/null; then
    fail "mysql client no encontrado. Instala mysql-client."
fi

if ! command -v sha256sum &> /dev/null; then
    fail "sha256sum no encontrado. Instala coreutils."
fi

mysql_exec() {
    local query="$1"
    mysql -N -B -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$query"
}

sql_escape() {
    local s="$1"
    s="${s//\'/\'\'}"
    printf "%s" "$s"
}

# Aplicar migraciones
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="${SCRIPT_DIR}/migrations"

if [[ ! -d "$MIGRATIONS_DIR" ]]; then
    fail "Directorio $MIGRATIONS_DIR no encontrado"
fi

# Tabla de control para evitar reaplicar migraciones ya ejecutadas.
mysql_exec "
CREATE TABLE IF NOT EXISTS schema_migrations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    filename VARCHAR(255) NOT NULL,
    checksum CHAR(64) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_schema_migrations_filename (filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"

migrations=("${MIGRATIONS_DIR}"/*.sql)
if [[ ${#migrations[@]} -eq 0 ]]; then
    log "No se encontraron migraciones en $MIGRATIONS_DIR"
    exit 0
fi

migrations_applied=0
migrations_skipped=0

for migration in "${migrations[@]}"; do
    MIGRATION_NAME="$(basename "$migration")"
    MIGRATION_ESCAPED="$(sql_escape "$MIGRATION_NAME")"
    MIGRATION_CHECKSUM="$(sha256sum "$migration" | awk '{print $1}')"

    applied_checksum="$(mysql_exec "SELECT checksum FROM schema_migrations WHERE filename='${MIGRATION_ESCAPED}' LIMIT 1;")"

    if [[ -n "$applied_checksum" ]]; then
        if [[ "$applied_checksum" == "$MIGRATION_CHECKSUM" ]]; then
            log "↷ Omitida (ya aplicada): $MIGRATION_NAME"
            migrations_skipped=$((migrations_skipped + 1))
            continue
        fi

        fail "Migración ya registrada con distinto checksum: $MIGRATION_NAME. Crea una nueva migración incremental en lugar de editar una ya aplicada."
    fi

    log "Aplicando: $MIGRATION_NAME..."
    migration_output="$(mktemp)"
    if ! mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$migration" >"$migration_output" 2>&1; then
        if grep -Eq "Duplicate column name|Duplicate key name|already exists|Table '.*' already exists|Duplicate entry" "$migration_output"; then
            log "↷ Se detectó objeto ya existente en $MIGRATION_NAME; se marca como aplicada."
        else
            cat "$migration_output" >&2
            rm -f "$migration_output"
            fail "Falló migración: $MIGRATION_NAME"
        fi
    fi
    rm -f "$migration_output"

    mysql_exec "
        INSERT INTO schema_migrations (filename, checksum)
        VALUES ('${MIGRATION_ESCAPED}', '${MIGRATION_CHECKSUM}');
    "

    log "✓ $MIGRATION_NAME completada"
    migrations_applied=$((migrations_applied + 1))
done

log "Migraciones finalizadas. aplicadas=$migrations_applied omitidas=$migrations_skipped"
