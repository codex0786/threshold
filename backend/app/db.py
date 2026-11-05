from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# The public deployment reads a bundled SQLite snapshot on a read-only filesystem.
_is_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(settings.database_url, **({"connect_args": {"check_same_thread": False}} if _is_sqlite else {"pool_pre_ping": True}))
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
