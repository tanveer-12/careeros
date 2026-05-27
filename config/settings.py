"""
Single source of truth for all Lumia configuration.

All values are read from environment variables or a .env file.
No secrets or URLs are hardcoded anywhere else in the codebase.
Import the module-level `settings` singleton instead of instantiating Settings directly.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/lumia_dev",
    )

    # ── Embeddings ───────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = Field(
        default="huggingface_embedding",
    )

    EMBEDDING_MODEL_NAME: str = Field(
        default="Supabase/bge-small-en",
    )

    EMBEDDING_DEVICE: str = Field(
        default="auto",
    )

    # ── Job API ──────────────────────────────────────────────────────────────
    REMOTIVE_API_URL: str = Field(
        default="https://remotive.com/api/remote-jobs",
    )

    HIMALAYAS_API_URL: str = Field(
        default="https://himalayas.app/jobs/api",
    )

    HIMALAYAS_PAGE_LIMIT: int = Field(
        default=20,  # API hard cap is 20 per request
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    LLM_ENABLED: bool = Field(
        default=True,
    )

    LLM_PROVIDER: str = Field(
        default="huggingface_api",
    )

    LLM_MODEL: str = Field(
        default="meta-llama/Meta-Llama-3-8B-Instruct",
    )

    # ── General ──────────────────────────────────────────────────────────────
    DEBUG: bool = Field(
        default=True,
    )


settings = Settings()