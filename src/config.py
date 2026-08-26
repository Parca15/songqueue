"""
Configuración centralizada del proyecto usando Pydantic Settings.
Permite cargar variables desde .env y validar tipos automáticamente.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──
    app_name: str = "SongQueue"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Base de Datos ──
    database_url: str = "mysql+aiomysql://songqueue:songqueue_pass@localhost:3306/songqueue"

    # ── Seguridad ──
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── YouTube ──
    youtube_api_key: str | None = None

    @property
    def async_database_url(self) -> str:
        """Retorna la URL de la base de datos para uso async."""
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Singleton de configuración."""
    return Settings()
