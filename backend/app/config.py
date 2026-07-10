"""Настройки приложения. Читаются из переменных окружения."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Главные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Окружение
    ENVIRONMENT: str = Field(default="development")

    # БД
    DATABASE_URL: str = "sqlite+aiosqlite:///./moneybot.db"

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # JWT
    JWT_SECRET: str  # Обязательно задать в .env — нет дефолта
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7

    # Шифрование API-ключей биржи
    ENCRYPTION_KEY: str  # Обязательно задать в .env — нет дефолта

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # SOCKS proxy для обхода блокировок бирж (Cloudflare WARP)
    SOCKS_PROXY: str = ""

    # Rate limiting
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SEC: int = 900  # 15 минут
    ACCESS_TOKEN_2FA_TTL_MINUTES: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    """Singleton настроек. Кешируется."""
    return Settings()  # type: ignore[call-arg]
