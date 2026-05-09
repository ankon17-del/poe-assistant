from functools import lru_cache

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/poe_ai",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    default_league_name: str = Field(default="POE2 Standard", alias="DEFAULT_LEAGUE_NAME")
    tracking_poll_interval_seconds: int = Field(default=60, alias="TRACKING_POLL_INTERVAL_SECONDS")
    poe_api_base_url: str = Field(default="https://api.pathofexile.com", alias="POE_API_BASE_URL")
    poe_api_user_agent: str = Field(
        default="OAuth poe-telegram-assistant/0.1.0 (contact: you@example.com)",
        alias="POE_API_USER_AGENT",
    )
    poe_api_access_token: str = Field(default="", alias="POE_API_ACCESS_TOKEN")
    poe_oauth_authorize_url: str = Field(
        default="https://www.pathofexile.com/oauth/authorize",
        alias="POE_OAUTH_AUTHORIZE_URL",
    )
    poe_oauth_token_url: str = Field(
        default="https://www.pathofexile.com/oauth/token",
        alias="POE_OAUTH_TOKEN_URL",
    )
    poe_oauth_client_id: str = Field(default="", alias="POE_OAUTH_CLIENT_ID")
    poe_oauth_client_secret: str = Field(default="", alias="POE_OAUTH_CLIENT_SECRET")
    poe_oauth_redirect_uri: str = Field(default="", alias="POE_OAUTH_REDIRECT_URI")
    poe_oauth_default_account_scopes: str = Field(
        default="account:profile",
        alias="POE_OAUTH_DEFAULT_ACCOUNT_SCOPES",
    )
    poe_oauth_default_service_scopes: str = Field(
        default="service:leagues",
        alias="POE_OAUTH_DEFAULT_SERVICE_SCOPES",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)

        if value.startswith("postgresql://") and not value.startswith("postgresql+asyncpg://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
