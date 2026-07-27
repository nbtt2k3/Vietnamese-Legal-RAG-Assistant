from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from app.database_config import db_settings

engine = create_engine(
    db_settings.db_url, 
    connect_args={"check_same_thread": False} if db_settings.db_url.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def initialize_database() -> None:
    """Create new tables and migrate additive SQLite columns for local deployments."""
    # Import models before create_all so SQLAlchemy has registered every table.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if not db_settings.db_url.startswith("sqlite"):
        return

    document_columns = {
        "url": "VARCHAR",
        "checksum": "VARCHAR",
        "verified_at": "VARCHAR",
        "effective_from": "VARCHAR",
        "effective_to": "VARCHAR",
        "repeal_reason": "VARCHAR",
        "source_of_validity": "VARCHAR",
        "source_file": "VARCHAR",
        "source_format": "VARCHAR",
        "source_url": "VARCHAR",
        "source_checksum_sha256": "VARCHAR",
        "source_verification_status": "VARCHAR",
        "source_verified_at": "VARCHAR",
        "validity_basis": "TEXT",
        "validity_confidence": "VARCHAR",
        "validity_checked_at": "VARCHAR",
    }
    relationship_columns = {
        "target_doc_ref": "TEXT",
        "note": "TEXT",
        "relation_source": "VARCHAR",
    }
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("documents")}
    with engine.begin() as connection:
        for name, sql_type in document_columns.items():
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE documents ADD COLUMN {name} {sql_type}")
        existing_relationships = {
            column["name"] for column in inspector.get_columns("document_relationships")
        }
        for name, sql_type in relationship_columns.items():
            if name not in existing_relationships:
                connection.exec_driver_sql(f"ALTER TABLE document_relationships ADD COLUMN {name} {sql_type}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
