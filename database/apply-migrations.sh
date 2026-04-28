#!/usr/bin/env bash
# apply-migrations.sh — Aplica migraciones SQL a compras_db
# Uso: ./apply-migrations.sh

set -Eeuo pipefail
shopt -s nullglob

log() { echo "[migrations] $*"; }
fail() { echo "[migrations][error] $*" >&2; exit 1; }

# Detectar credenciales desde variables de entorno o usar defaults
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
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$migration" || fail "Falló migración: $MIGRATION_NAME"

    mysql_exec "
        INSERT INTO schema_migrations (filename, checksum)
        VALUES ('${MIGRATION_ESCAPED}', '${MIGRATION_CHECKSUM}');
    "

    log "✓ $MIGRATION_NAME completada"
    migrations_applied=$((migrations_applied + 1))
done

log "Migraciones finalizadas. aplicadas=$migrations_applied omitidas=$migrations_skipped"
