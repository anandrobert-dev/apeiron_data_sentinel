"""Apeiron Data Sentinel — Configuration via environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # --- General ---
    app_name: str = "Apeiron Data Sentinel"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    # --- FastAPI ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    allowed_origins: str = "http://localhost,http://localhost:80"

    # --- PostgreSQL (via PgBouncer) ---
    postgres_user: str = "sentinel"
    postgres_password: str = "sentinel_secure_pwd_change_me"
    postgres_db: str = "apeiron_sentinel"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    pgbouncer_host: str = "pgbouncer"
    pgbouncer_port: int = 5432

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- JWT Auth ---
    jwt_secret_key: str = "CHANGE_THIS_TO_A_RANDOM_64_CHAR_STRING"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- File Upload ---
    upload_max_size_mb: int = 100
    upload_dir: str = "/app/uploads"

    # --- Ollama (GRACE AI) ---
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "mistral"

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        """Database URL pointing through PgBouncer."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.pgbouncer_host}:{self.pgbouncer_port}/{self.postgres_db}"
        )

    @property
    def database_url_direct(self) -> str:
        """Direct PostgreSQL URL (for migrations)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous DB URL for Alembic migrations."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
