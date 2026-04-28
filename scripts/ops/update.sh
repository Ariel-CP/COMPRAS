#!/usr/bin/env bash
# update.sh — Actualiza el sistema compras desde GitHub y reinicia el servicio.
#
# Uso:
#   ./scripts/ops/update.sh
#
# Variables opcionales de entorno:
#   REPO_URL   — URL del repositorio (default: https://github.com/Ariel-CP/COMPRAS.git)
#   BRANCH     — Rama a desplegar (default: master)
#   APP_DIR    — Directorio del proyecto (default: el padre del script)
#   RUN_POST_DEPLOY — Ejecuta post deploy de BD/permisos (default: 1)

set -Eeuo pipefail

log()  { echo "[update] $*"; }
fail() { echo "[update][error] $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
REPO_URL="${REPO_URL:-https://github.com/Ariel-CP/COMPRAS.git}"
BRANCH="${BRANCH:-master}"
RUN_POST_DEPLOY="${RUN_POST_DEPLOY:-1}"

log "Directorio: ${APP_DIR}"
log "Repositorio: ${REPO_URL}  rama: ${BRANCH}"

# ── 1. Actualizar código ──────────────────────────────────────────────────────
cd "${APP_DIR}"

if [[ -d ".git" ]]; then
    log "Repositorio git encontrado. Ejecutando git pull..."
    git fetch origin "${BRANCH}"
    git reset --hard "origin/${BRANCH}"
else
    log "No hay repositorio git. Clonando..."
    command -v git >/dev/null 2>&1 || { sudo apt-get install -y git; }
    tmpdir=$(mktemp -d)
    git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${tmpdir}"
    rsync -a --delete \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='.env' \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        "${tmpdir}/" "${APP_DIR}/"
    rm -rf "${tmpdir}"
fi

# ── 2. Actualizar dependencias si requirements.txt cambió ────────────────────
if [[ -f ".venv/bin/python" ]]; then
    log "Actualizando dependencias Python..."
    .venv/bin/pip install --quiet -r requirements.txt
else
    fail "Entorno virtual no encontrado en .venv. Ejecutá install_raspberry.sh primero."
fi

# ── 3. Reiniciar servicio ─────────────────────────────────────────────────────
# ── 3. Post-deploy (migraciones + permisos + integridad) ────────────────────
if [[ "${RUN_POST_DEPLOY}" == "1" ]]; then
    if [[ -x "scripts/ops/post_deploy_raspberry.sh" ]]; then
        log "Ejecutando post-deploy..."
        scripts/ops/post_deploy_raspberry.sh
    else
        log "post_deploy_raspberry.sh no encontrado o sin permisos de ejecucion; se omite."
    fi
else
    log "Post-deploy deshabilitado (RUN_POST_DEPLOY=${RUN_POST_DEPLOY})."
fi

# ── 4. Reiniciar servicio ─────────────────────────────────────────────────────
log "Reiniciando compras-api..."
sudo systemctl restart compras-api
sudo systemctl is-active compras-api

# ── 5. Health check con reintentos ───────────────────────────────────────────
log "Verificando respuesta HTTP..."
code="000"
for i in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ui/login || true)
    if [[ "${code}" == "200" ]]; then
        break
    fi
    sleep 1
done

if [[ "${code}" == "200" ]]; then
    log "Sistema actualizado y respondiendo correctamente (HTTP ${code})."
else
    fail "El sistema reinició pero no respondió en tiempo esperado (último HTTP: ${code})."
fi
