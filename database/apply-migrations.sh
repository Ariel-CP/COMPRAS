#!/usr/bin/env bash
# apply-migrations.sh — Aplica migraciones SQL a compras_db
# Uso: ./apply-migrations.sh

set -Eeuo pipefail

log() { echo "[migrations] $*"; }
fail() { echo "[migrations][error] $*" >&2; exit 1; }

# Detectar credenciales desde variables de entorno o usar defaults
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_USER="${DB_USER:-compras}"
DB_PASS="${DB_PASS:-matete01}"
DB_NAME="${DB_NAME:-compras_db}"

log "Conectando a $DB_HOST / $DB_NAME como $DB_USER..."

# Verificar que mysql está disponible
if ! command -v mysql &> /dev/null; then
    fail "mysql client no encontrado. Instala mysql-client."
fi

# Aplicar migraciones
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="${SCRIPT_DIR}/migrations"

if [[ ! -d "$MIGRATIONS_DIR" ]]; then
    fail "Directorio $MIGRATIONS_DIR no encontrado"
fi

for migration in "${MIGRATIONS_DIR}"/*.sql; do
    if [[ -f "$migration" ]]; then
        MIGRATION_NAME=$(basename "$migration")
        log "Aplicando: $MIGRATION_NAME..."
        
        mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$migration" || fail "Falló migración: $MIGRATION_NAME"
        log "✓ $MIGRATION_NAME completada"
    fi
done

log "Todas las migraciones aplicadas correctamente"
