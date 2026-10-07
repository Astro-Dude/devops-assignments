"""Runtime configuration.

Non-secret settings come from a ConfigMap (APP_ENV, LOG_LEVEL, DB_HOST ...),
credentials come from a Secret (DB_USER, DB_PASSWORD). DATABASE_URL, when set,
overrides the individual parts (used by tests and docker compose).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TicketHub API"
    app_env: str = "local"
    app_version: str = "dev"
    log_level: str = "INFO"
    default_team: str = "L1 Support"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tickethub"
    db_user: str = "tickethub"
    db_password: str = ""
    database_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
