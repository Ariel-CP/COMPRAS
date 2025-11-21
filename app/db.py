from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .core.config import get_settings

_settings = get_settings()
_engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=_settings.mysql_pool_size,
    max_overflow=_settings.mysql_max_overflow,
    future=True,
)
SessionLocal = sessionmaker(
    bind=_engine, autocommit=False, autoflush=False, future=True
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
