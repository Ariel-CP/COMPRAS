#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  echo "[install] $*"
}

fail() {
  echo "[install][error] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Falta comando requerido: $1"
}

upsert_env() {
  local file="$1"
  local key="$2"
  local value="$3"

  touch "$file"
  if grep -q "^${key}=" "$file"; then
    sed -i "s#^${key}=.*#${key}=${value}#" "$file"
  else
    echo "${key}=${value}" >>"$file"
  fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_USER="${APP_USER:-$(id -un)}"
DB_NAME="${DB_NAME:-compras_db}"
DB_USER="${DB_USER:-acepeda}"
DB_PASS="${DB_PASS:-2211}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"

DB_INIT_MODE="${DB_INIT_MODE:-schema}"
DB_RESET="${DB_RESET:-false}"
DUMP_FILE="${DUMP_FILE:-${APP_DIR}/backups_local_dump.clean.sql}"

CREATE_SERVICE="${CREATE_SERVICE:-true}"
WRITE_ENV="${WRITE_ENV:-true}"
INSTALL_PACKAGES="${INSTALL_PACKAGES:-true}"

DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}?charset=utf8mb4"

log "APP_DIR=${APP_DIR}"
log "DB_INIT_MODE=${DB_INIT_MODE}"

require_cmd sudo
require_cmd python3
require_cmd systemctl

if [[ "${INSTALL_PACKAGES}" == "true" ]]; then
  log "Instalando paquetes del sistema (python3-venv, mariadb, build deps)..."
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip mariadb-server libmariadb-dev build-essential
fi

log "Habilitando MariaDB..."
sudo systemctl enable mariadb >/dev/null 2>&1 || true
sudo systemctl start mariadb

if [[ "${DB_RESET}" == "true" ]]; then
  log "Recreando base ${DB_NAME}..."
  sudo mysql -e "DROP DATABASE IF EXISTS ${DB_NAME};"
fi

log "Creando base y usuario de MariaDB..."
sudo mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
sudo mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASS}';"
sudo mysql -e "ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
sudo mysql -e "ALTER USER '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASS}';"
sudo mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
sudo mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'%';"
sudo mysql -e "FLUSH PRIVILEGES;"

if [[ "${DB_INIT_MODE}" == "dump" ]]; then
  [[ -f "${DUMP_FILE}" ]] || fail "No existe dump: ${DUMP_FILE}"

  if [[ "${DB_RESET}" != "true" ]]; then
    fail "Para DB_INIT_MODE=dump se recomienda DB_RESET=true para evitar conflictos de objetos."
  fi

  log "Importando dump completo: ${DUMP_FILE}"
  CLEAN_DUMP="$(mktemp)"
  sed '/sandbox mode/d;/NOTE_VERBOSITY/d' "${DUMP_FILE}" >"${CLEAN_DUMP}"
  sudo sh -c "mysql ${DB_NAME} < '${CLEAN_DUMP}'"
  rm -f "${CLEAN_DUMP}"
elif [[ "${DB_INIT_MODE}" == "schema" ]]; then
  [[ -f "${APP_DIR}/database/schema.sql" ]] || fail "No existe database/schema.sql"
  log "Aplicando schema base..."
  sudo sh -c "mysql ${DB_NAME} < '${APP_DIR}/database/schema.sql'"

  if [[ -f "${APP_DIR}/database/migrations/005_add_auth.sql" ]]; then
    log "Aplicando migracion 005_add_auth.sql..."
    sudo sh -c "mysql ${DB_NAME} < '${APP_DIR}/database/migrations/005_add_auth.sql'"
  fi

  if [[ -f "${APP_DIR}/database/migrations/001_add_user_session.sql" ]]; then
    log "Aplicando migracion 001_add_user_session.sql..."
    sudo sh -c "mysql ${DB_NAME} < '${APP_DIR}/database/migrations/001_add_user_session.sql'"
  fi
else
  fail "DB_INIT_MODE invalido. Usar: schema o dump"
fi

log "Configurando entorno Python..."
cd "${APP_DIR}"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ "${WRITE_ENV}" == "true" ]]; then
  log "Actualizando .env con DATABASE_URL"
  upsert_env "${APP_DIR}/.env" "DATABASE_URL" "${DATABASE_URL}"
fi

if [[ "${CREATE_SERVICE}" == "true" ]]; then
  log "Creando servicio systemd compras-api.service"
  sudo tee /etc/systemd/system/compras-api.service >/dev/null <<EOF
[Unit]
Description=Compras FastAPI API
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable compras-api
  sudo systemctl restart compras-api
fi

log "Chequeo rapido de API en localhost"
if command -v curl >/dev/null 2>&1; then
  curl -s -o /dev/null -w "HTTP %{http_code}\n" "http://127.0.0.1:8000/" || true
else
  log "curl no instalado; omitiendo healthcheck HTTP"
fi

log "Instalacion finalizada."
log "URL en red local: http://<IP_RASPBERRY>:8000"
