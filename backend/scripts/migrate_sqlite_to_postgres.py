"""Migrate the legacy SQLite application database into PostgreSQL.

The script is intentionally explicit and refuses to write to SQLite or to a
non-empty PostgreSQL database, preventing accidental duplicate imports.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.base import Base
from app.db.config import db_settings
from app.db.models import ChatMessage, Conversation, Document, DocumentRelationship, User


COPY_ORDER = (User, Document, Conversation, DocumentRelationship, ChatMessage)


def copy_database(source_url: str, target_url: str) -> dict[str, int]:
    if not source_url.startswith("sqlite"):
        raise ValueError("Source database must be SQLite")
    if target_url.startswith("sqlite"):
        raise ValueError("Target database must be PostgreSQL")

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)
    source_tables = set(inspect(source_engine).get_table_names())
    required_tables = {model.__tablename__ for model in COPY_ORDER}
    missing = required_tables - source_tables
    if missing:
        raise RuntimeError(f"SQLite database is missing tables: {sorted(missing)}")

    Base.metadata.create_all(bind=target_engine)
    with Session(target_engine) as target_session:
        existing = {
            model.__tablename__: target_session.query(model).count()
            for model in COPY_ORDER
        }
        if any(existing.values()):
            raise RuntimeError(f"Target PostgreSQL database is not empty: {existing}")

        copied: dict[str, int] = {}
        with Session(source_engine) as source_session:
            for model in COPY_ORDER:
                rows = source_session.scalars(select(model)).all()
                columns = [column.name for column in model.__table__.columns]
                target_session.add_all(
                    [model(**{column: getattr(row, column) for column in columns}) for row in rows]
                )
                target_session.flush()
                copied[model.__tablename__] = len(rows)
        target_session.commit()
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy SQLite data to PostgreSQL")
    parser.add_argument(
        "--source",
        default=str(PROJECT_ROOT / "data" / "legal_rag.db"),
        help="Path to the legacy SQLite database",
    )
    args = parser.parse_args()
    source_url = f"sqlite:///{Path(args.source).resolve()}"
    counts = copy_database(source_url, db_settings.db_url)
    print(f"Migrated successfully: {counts}")


if __name__ == "__main__":
    main()
