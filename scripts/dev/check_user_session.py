"""Comprueba si la tabla `user_session` existe en la base de datos configurada."""
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from app.db import _engine


def main():
    try:
        inspector = inspect(_engine)
        tables = inspector.get_table_names()
        if "user_session" in tables:
            print("user_session: EXISTS")
        else:
            print("user_session: NOT FOUND")
            print("Tablas en la BD:\n", tables)
    except SQLAlchemyError as e:
        print("Error al inspeccionar la base de datos:", e)


if __name__ == "__main__":
    main()
