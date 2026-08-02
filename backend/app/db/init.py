from app.db.config import db_settings
from app.db.base import Base
from app.db.session import engine


def initialize_database() -> None:
    """Create the PostgreSQL schema used by the API."""
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
