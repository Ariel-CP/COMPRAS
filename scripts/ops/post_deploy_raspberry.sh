#!/usr/bin/env bash
# post_deploy_raspberry.sh
# Aplica migraciones, asegura permisos admin y valida integridad basica en Raspberry.

set -Eeuo pipefail

log() {
  echo "[post-deploy] $*"
}

fail() {
  echo "[post-deploy][error] $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-}"
DB_USER="${DB_USER:-}"
DB_PASS="${DB_PASS:-}"
DB_NAME="${DB_NAME:-}"

load_from_database_url() {
  local env_file="${REPO_ROOT}/.env"
  if [[ -f "$env_file" ]]; then
    local database_url
    database_url="$(grep -E '^DATABASE_URL=' "$env_file" | head -n 1 | sed 's/^DATABASE_URL=//')"
    if [[ -n "$database_url" ]]; then
      eval "$(python3 - "$database_url" <<'PY'
import sys
from urllib.parse import urlparse

url = sys.argv[1].strip()
if not url:
    raise SystemExit(0)
parsed = urlparse(url)
host = parsed.hostname or ""
port = parsed.port or ""
user = parsed.username or ""
password = parsed.password or ""
name = (parsed.path or "").lstrip("/")
print(f'DB_HOST_FROM_URL="{host}"')
print(f'DB_PORT_FROM_URL="{port}"')
print(f'DB_USER_FROM_URL="{user}"')
print(f'DB_PASS_FROM_URL="{password}"')
print(f'DB_NAME_FROM_URL="{name}"')
PY
)"

      DB_HOST="${DB_HOST:-${DB_HOST_FROM_URL:-}}"
      DB_PORT="${DB_PORT:-${DB_PORT_FROM_URL:-}}"
      DB_USER="${DB_USER:-${DB_USER_FROM_URL:-}}"
      DB_PASS="${DB_PASS:-${DB_PASS_FROM_URL:-}}"
      DB_NAME="${DB_NAME:-${DB_NAME_FROM_URL:-}}"
    fi
  fi
}

load_defaults() {
  DB_HOST="${DB_HOST:-127.0.0.1}"
  DB_PORT="${DB_PORT:-3306}"
  DB_USER="${DB_USER:-compras}"
  DB_PASS="${DB_PASS:-matete01}"
  DB_NAME="${DB_NAME:-compras_db}"
}

mysql_exec() {
  local sql="$1"
  mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -e "$sql"
}

mysql_exec_nb() {
  local sql="$1"
  mysql -N -B -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -e "$sql"
}

apply_migrations() {
  local migration_script="${REPO_ROOT}/database/apply-migrations.sh"
  [[ -x "$migration_script" ]] || chmod +x "$migration_script"

  log "Aplicando migraciones SQL..."
  DB_HOST="$DB_HOST" DB_USER="$DB_USER" DB_PASS="$DB_PASS" DB_NAME="$DB_NAME" "$migration_script"
}

ensure_admin_permissions() {
  local required_form_keys=(
    "admin_backups"
    "admin_roles"
    "admin_sistema"
    "admin_usuarios"
    "informes"
    "mbom"
    "plan"
    "precios"
    "proveedores"
    "productos"
    "rubros"
    "stock"
    "tipo_cambio"
    "unidades"
  )

  local role_count
  role_count="$(mysql_exec_nb "SELECT COUNT(*) FROM rol WHERE nombre='admin';")"
  if [[ "$role_count" != "1" ]]; then
    fail "No existe rol admin unico en tabla rol. Resultado: $role_count"
  fi

  log "Asegurando permisos admin (${#required_form_keys[@]} form_keys)..."
  for key in "${required_form_keys[@]}"; do
    mysql_exec "
      INSERT INTO permiso_form (rol_id, form_key, puede_leer, puede_escribir)
      SELECT id, '$key', 1, 1
      FROM rol
      WHERE nombre='admin'
      ON DUPLICATE KEY UPDATE
        puede_leer=VALUES(puede_leer),
        puede_escribir=VALUES(puede_escribir);
    "
  done
}

check_integrity() {
  log "Chequeando integridad relacional basica..."

  local orphan_user orphan_role orphan_perm
  orphan_user="$(mysql_exec_nb "SELECT COUNT(*) FROM usuario_rol ur LEFT JOIN usuario u ON u.id=ur.usuario_id WHERE u.id IS NULL;")"
  orphan_role="$(mysql_exec_nb "SELECT COUNT(*) FROM usuario_rol ur LEFT JOIN rol r ON r.id=ur.rol_id WHERE r.id IS NULL;")"
  orphan_perm="$(mysql_exec_nb "SELECT COUNT(*) FROM permiso_form pf LEFT JOIN rol r ON r.id=pf.rol_id WHERE r.id IS NULL;")"

  echo "usuario_rol_huerfano_usuario=$orphan_user"
  echo "usuario_rol_huerfano_rol=$orphan_role"
  echo "permiso_form_huerfano_rol=$orphan_perm"

  if [[ "$orphan_user" != "0" || "$orphan_role" != "0" || "$orphan_perm" != "0" ]]; then
    fail "Se detectaron huerfanos en tablas de seguridad"
  fi

  log "Corriendo mysqlcheck sobre tablas clave..."
  mysqlcheck -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" usuario rol usuario_rol permiso_form proveedor
}

main() {
  load_from_database_url
  load_defaults

  log "Repo: $REPO_ROOT"
  log "DB: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

  apply_migrations
  ensure_admin_permissions
  check_integrity

  log "Post-deploy completado sin errores"
}

main "$@"
