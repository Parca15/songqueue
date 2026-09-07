"""
Configuracion centralizada del proyecto usando Pydantic Settings.
Permite cargar variables desde .env y validar tipos automaticamente.

Seguridad: no hay defaults para secretos. SECRET_KEY es obligatorio
(min 32 chars y fuera de la blocklist de placeholders). Con extra="forbid"
cualquier variable desconocida en .env falla al arrancar en vez de
silenciarse.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholders conocidos que nunca deben usarse como SECRET_KEY real.
_BLOCKED_SECRETS = {
    "change-me-in-production",
    "change-me-in-production-use-openssl-rand-hex-32",
    "change-this-in-production-use-openssl-rand-hex-32",
    "test",
    "secret",
}


class Settings(BaseSettings):
    """Configuracion de la aplicacion."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # ── App ──
    app_name: str = "SongQueue"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    version: str = "1.0.0"

    # ── Base de Datos ──
    # Default solo para desarrollo local (nunca expone prod: compose lo sobreescribe).
    database_url: str = (
        "mysql+aiomysql://songqueue:songqueue_pass@localhost:3306/songqueue"
    )
    # Solo para interpolación en docker-compose (la app usa database_url).
    db_password: str | None = None

    # ── Seguridad ──
    secret_key: str = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── CORS: orígenes extra (coma-separados) para deploys split.
    # Vacío = solo mismo origen (nginx/tunnel sirven web+api juntas).
    cors_origins: str = ""

    # ── YouTube ──
    youtube_api_key: str | None = None

    # ── URLs públicas (QR) ──
    server_base_url: str | None = None

    # ── Super admin (bootstrap: se crea solo si no existe ninguno) ──
    super_admin_username: str | None = None
    super_admin_password: str | None = None

    @field_validator("secret_key")
    @classmethod
    def _reject_placeholder_secrets(cls, v: str) -> str:
        if v.strip().lower() in _BLOCKED_SECRETS:
            raise ValueError(
                "SECRET_KEY usa un valor placeholder. Genera uno con: "
                "openssl rand -hex 32"
            )
        return v

    @property
    def async_database_url(self) -> str:
        """Retorna la URL de la base de datos para uso async."""
        return self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        """Orígenes CORS como lista limpia."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton de configuracion."""
    return Settings()
