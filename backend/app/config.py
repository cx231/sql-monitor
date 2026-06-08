from functools import lru_cache

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "dev-secret-key"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SQLMON_", env_file=".env", extra="ignore")

    app_name: str = "SQLMon API"
    env: str = "dev"
    secret_key: str = DEFAULT_SECRET_KEY
    database_url: str = "postgresql+asyncpg://sqlmon:password@127.0.0.1:5432/sqlmon"
    encryption_key: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    default_retention_days: int = 7
    collect_connect_timeout_seconds: int = 5
    collect_query_timeout_seconds: int = 3
    index_collect_database_concurrency: int = Field(default=4, ge=1, le=16)
    index_collect_database_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    min_killable_session_id: int = Field(default=50, ge=1)

    @property
    def debug(self) -> bool:
        return self.env.lower() in {"dev", "local", "test"}

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        if not self.debug and (
            self.secret_key == DEFAULT_SECRET_KEY or len(self.secret_key) < 32
        ):
            raise ValueError("生产环境必须配置长度不少于 32 字符的安全 SQLMON_SECRET_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
