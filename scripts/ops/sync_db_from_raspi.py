#!/usr/bin/env python3
"""
Script para sincronizar la base de datos local desde la Raspberry (compras-dev).

Uso:
    python scripts/ops/sync_db_from_raspi.py

Requisitos:
    - pip install paramiko
"""

import subprocess
import sys
import os
from pathlib import Path
import getpass
from datetime import datetime


PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKUPS_DIR = PROJECT_ROOT / "backups"


def get_env(name, default=None):
    """Obtiene una variable de entorno con valor por defecto opcional."""
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    if value == "":
        return default
    return value


def get_secret(name, prompt_text):
    """Obtiene un secreto de entorno o lo solicita por consola sin eco."""
    value = get_env(name)
    if value is not None:
        return value
    return getpass.getpass(prompt_text)


def load_config():
    """Carga configuración desde variables de entorno y prompts seguros."""
    raspi_host = get_env("RASPI_HOST", "compras-dev")
    raspi_user = get_env("RASPI_USER", "acepeda")
    raspi_db_name = get_env("RASPI_DB_NAME", "compras_db")
    raspi_db_user = get_env("RASPI_DB_USER", "compras")
    raspi_db_pass = get_secret("RASPI_DB_PASS", "Password MySQL en Raspberry: ")
    raspi_ssh_pass = get_secret("RASPI_SSH_PASS", f"Password SSH para {raspi_user}@{raspi_host}: ")

    local_db_host = get_env("LOCAL_DB_HOST", "127.0.0.1")
    local_db_port = int(get_env("LOCAL_DB_PORT", "3306"))
    local_db_name = get_env("LOCAL_DB_NAME", "compras_db")
    local_db_user = get_env("LOCAL_DB_USER", "root")
    local_db_pass = get_secret("LOCAL_DB_PASS", "Password MySQL local: ")

    return {
        "raspi_host": raspi_host,
        "raspi_user": raspi_user,
        "raspi_db_name": raspi_db_name,
        "raspi_db_user": raspi_db_user,
        "raspi_db_pass": raspi_db_pass,
        "raspi_ssh_pass": raspi_ssh_pass,
        "local_db_host": local_db_host,
        "local_db_port": local_db_port,
        "local_db_name": local_db_name,
        "local_db_user": local_db_user,
        "local_db_pass": local_db_pass,
    }


def run_command(cmd, description, capture=False):
    """Ejecuta un comando y maneja errores."""
    print(f"\n▶ {description}...")
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=True
            )
            return result.stdout
        else:
            subprocess.run(cmd, shell=True, check=True)
            return None
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        if e.stderr:
            print(f"  Detalles: {e.stderr}")
        sys.exit(1)


def main():
    cfg = load_config()

    print("=" * 60)
    print("SINCRONIZAR BD LOCAL DESDE RASPBERRY (compras-dev)")
    print("=" * 60)
    print("\nConfiguración:")
    print(f"  Raspberry:     {cfg['raspi_host']} (usuario: {cfg['raspi_user']})")
    print(f"  BD Raspberry:  {cfg['raspi_db_name']} (usuario MySQL: {cfg['raspi_db_user']})")
    print(
        f"  BD Local:      {cfg['local_db_name']}@{cfg['local_db_host']}:{cfg['local_db_port']} "
        f"(usuario: {cfg['local_db_user']})"
    )
    print(f"  Backup dir:    {BACKUPS_DIR}")

    # Crear directorio de backups si no existe
    BACKUPS_DIR.mkdir(exist_ok=True)

    # Nombre del archivo temporal
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_file = BACKUPS_DIR / f"compras_db_sync_{timestamp}.sql"

    print(f"\n📦 Archivo temporal: {dump_file}")

    # Paso 1: Crear dump en la Raspberry vía SSH usando Paramiko
    print("\n1️⃣  Generando dump desde Raspberry...")
    try:
        # Importar del mismo directorio
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from sync_db_paramiko import download_dump_via_ssh
        
        download_dump_via_ssh(
            host=cfg["raspi_host"],
            user=cfg["raspi_user"],
            password=cfg["raspi_ssh_pass"],
            db_name=cfg["raspi_db_name"],
            db_user=cfg["raspi_db_user"],
            db_password=cfg["raspi_db_pass"],
            output_file=str(dump_file),
        )
    except Exception as e:
        print(f"✗ Error conectando a Raspberry: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Paso 2: Restaurar en BD local
    return restore_local_db(dump_file, cfg)


def restore_local_db(dump_file, cfg):
    """Restaura el dump en la BD local."""
    print("\n2️⃣  Restaurando en BD local...")

    mysql_cmd = [
        "mysql",
        "-h",
        cfg["local_db_host"],
        "-P",
        str(cfg["local_db_port"]),
        "-u",
        cfg["local_db_user"],
        cfg["local_db_name"],
    ]
    mysql_env = os.environ.copy()
    mysql_env["MYSQL_PWD"] = cfg["local_db_pass"]

    print("\n▶ Restaurando BD local...")
    try:
        with open(dump_file, "rb") as dump_stream:
            subprocess.run(mysql_cmd, stdin=dump_stream, env=mysql_env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"✗ Error restaurando BD local: {e}")
        sys.exit(1)

    print("\n✅ SINCRONIZACIÓN COMPLETADA")
    print(f"   BD {cfg['local_db_name']} actualizada desde {cfg['raspi_host']}")
    print(f"   Backup guardado en: {dump_file}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠ Cancelado por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
