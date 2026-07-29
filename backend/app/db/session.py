from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import db_settings

engine = create_engine(
    db_settings.db_url,
    connect_args={"check_same_thread": False} if db_settings.db_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
