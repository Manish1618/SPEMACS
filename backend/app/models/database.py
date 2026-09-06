from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Bring the database to the latest Alembic revision.

    Run at startup so a fresh clone or a new deployment needs no separate step,
    and so the schema has exactly one definition (alembic/versions) rather than
    create_all() and a hand-written ALTER list drifting apart.
    """
    from alembic import command
    from alembic.config import Config

    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(ini_path.parent / "alembic"))
    command.upgrade(config, "head")
