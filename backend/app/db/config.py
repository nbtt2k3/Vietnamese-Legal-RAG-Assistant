from app.core.config import settings


class DBSettings:
    @property
    def db_url(self) -> str:
        if settings.database_url:
            return settings.database_url
        sqlite_path = settings.data_dir / "legal_rag.db"
        return f"sqlite:///{sqlite_path}"


db_settings = DBSettings()
