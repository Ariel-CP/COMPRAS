import json
import os
from dataclasses import dataclass
from typing import Optional

try:
    # Cargar variables desde .env si existe
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover - dependencia opcional
    load_dotenv = None  # type: ignore


@dataclass
class Settings:
    database_url: str
    mysql_pool_size: int = 10
    mysql_max_overflow: int = 10
    max_upload_mb: int = 10
    # 'anthropic' | 'openai' | 'azure-openai'
    ai_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None


def _load_json_config() -> dict:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # app/ -> project root
    project_root = os.path.dirname(base_dir)
    config_path = os.path.join(project_root, "app", "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def get_settings() -> Settings:
    # Intentar cargar .env del raíz del proyecto
    if load_dotenv is not None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(base_dir)
        dotenv_path = os.path.join(project_root, ".env")
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)

    cfg = _load_json_config()

    # Preferir variables de entorno si están presentes
    database_url = (
        os.environ.get("DATABASE_URL")
        or cfg.get("database_url")
        or (
            "mysql+pymysql://root:root@127.0.0.1:3306/"
            "compras_db?charset=utf8mb4"
        )
    )

    mysql_pool_size = int(
        os.environ.get("MYSQL_POOL_SIZE", cfg.get("mysql_pool_size", 10))
    )
    mysql_max_overflow = int(
        os.environ.get("MYSQL_MAX_OVERFLOW", cfg.get("mysql_max_overflow", 10))
    )
    max_upload_mb = int(
        os.environ.get("MAX_UPLOAD_MB", cfg.get("max_upload_mb", 10))
    )

    ai_provider = os.environ.get("AI_PROVIDER") or cfg.get("ai_provider")

    openai_api_key = (
        os.environ.get("OPENAI_API_KEY") or cfg.get("openai_api_key")
    )
    openai_model = os.environ.get("OPENAI_MODEL") or cfg.get("openai_model")

    anthropic_api_key = (
        os.environ.get("ANTHROPIC_API_KEY") or cfg.get("anthropic_api_key")
    )
    anthropic_model = (
        os.environ.get("ANTHROPIC_MODEL") or cfg.get("anthropic_model")
    )

    return Settings(
        database_url=database_url,
        mysql_pool_size=mysql_pool_size,
        mysql_max_overflow=mysql_max_overflow,
        max_upload_mb=max_upload_mb,
        ai_provider=ai_provider,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        anthropic_api_key=anthropic_api_key,
        anthropic_model=anthropic_model,
    )
