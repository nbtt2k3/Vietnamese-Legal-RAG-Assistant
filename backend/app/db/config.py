from app.core.config import settings


class DBSettings:
    @property
    def db_url(self) -> str:
        if settings.database_url:
            return settings.database_url
        return "postgresql+psycopg2://legal_app:legal_app_password@localhost:5432/legal_assistant"


db_settings = DBSettings()
