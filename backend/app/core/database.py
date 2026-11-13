"""SQLAlchemy setup. All database ownership stays inside the backend."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def create_database(url: str) -> Engine:
    database = make_url(url).database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"poolclass": StaticPool} if database == ":memory:" else {}
    engine = create_engine(
        url, connect_args={"check_same_thread": False, "timeout": 5}, **kwargs
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine
