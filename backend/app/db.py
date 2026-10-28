from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    # Local SQLite remains self-starting for the project demo. Production
    # deployments should run `alembic upgrade head` and disable this fallback.
    if settings.schema_auto_create:
        Base.metadata.create_all(bind=engine)
        if settings.database_url.startswith("sqlite"):
            existing = {column["name"] for column in inspect(engine).get_columns("measurements")}
            with engine.begin() as connection:
                for name, sql_type in (("site_latitude", "FLOAT"), ("site_longitude", "FLOAT"), ("site_accuracy_m", "FLOAT"), ("location_updated_at", "DATETIME")):
                    if name not in existing:
                        connection.execute(text(f"ALTER TABLE measurements ADD COLUMN {name} {sql_type}"))

