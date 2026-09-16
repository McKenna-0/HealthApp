from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


settings.db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    # Two long holders of a write lock now coexist: a scheduled sync bulk-upserts
    # for tens of seconds, and an agent turn keeps a connection across several
    # tool calls plus a streamed reply. Observed a "database is locked" at 5s
    # when a request arrived during the startup catch-up sync, so wait longer -
    # a slow response beats a 500, and with one user contention is rare enough
    # that the wait is never actually paid.
    cursor.execute("PRAGMA busy_timeout=20000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """create_all only creates missing tables; additive schema changes to
    existing tables need ALTER TABLE. Adds any mapped column that doesn't
    exist yet (nullable / defaulted columns only, which is all we ever add)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}'
                if col.default is not None and getattr(col.default, "arg", None) is not None:
                    arg = col.default.arg
                    if isinstance(arg, (int, float)):
                        ddl += f" DEFAULT {arg}"
                    elif isinstance(arg, str):
                        ddl += f" DEFAULT '{arg}'"
                conn.execute(text(ddl))
        # uq_foodlog_mfp used to enforce MFP sync idempotency, but sync_date()
        # already does that itself (delete-then-insert per day). The index
        # instead broke on a real MFP diary: the same food logged twice in one
        # meal has identical (date, meal, description, source), which is a
        # legitimate duplicate, not a re-sync collision.
        conn.execute(text("DROP INDEX IF EXISTS uq_foodlog_mfp"))
