from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SQLMON_", env_file=".env", extra="ignore")

    app_name: str = "SQLMon API"
    env: str = "dev"
    secret_key: str = "dev-secret-key"
    database_url: str = "postgresql+asyncpg://sqlmon:password@127.0.0.1:5432/sqlmon"
    encryption_key: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    default_retention_days: int = 7
    collect_connect_timeout_seconds: int = 5
    collect_query_timeout_seconds: int = 3
    min_killable_session_id: int = Field(default=50, ge=1)

    @property
    def debug(self) -> bool:
        return self.env.lower() in {"dev", "local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
