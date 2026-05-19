"""
Single source of truth for all CareerOS configuration.

All values are read from environment variables or a .env file.
No secrets or URLs are hardcoded anywhere else in the codebase.
Import the module-level `settings` singleton instead of instantiating Settings directly.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/careeros",
        alias="DATABASE_URL",
    )

    # ── LLM — Groq (primary, free tier) ──────────────────────────────────────
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        alias="GROQ_BASE_URL",
    )

    # ── LLM — Anthropic (optional) ───────────────────────────────────────────
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # ── LLM — OpenAI (embeddings, Phase 4) ───────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # ── LLM runtime settings ─────────────────────────────────────────────────
    llm_provider: str = Field(
        default="groq",
        alias="LLM_PROVIDER",
        description="Active LLM provider: groq | anthropic | ollama",
    )
    llm_model: str = Field(
        default="llama-3.3-70b-versatile",
        alias="LLM_MODEL",
    )
    llm_max_concurrency: int = Field(
        default=2,
        alias="LLM_MAX_CONCURRENCY",
        description="Max parallel LLM calls during batch normalization",
    )
    normalizer_max_concurrency: int = Field(
        default=20,
        alias="NORMALIZER_MAX_CONCURRENCY",
        description="Max parallel normalize() calls during batch normalization",
    )
    llm_request_delay_seconds: float = Field(
        default=5.0,
        alias="LLM_REQUEST_DELAY_SECONDS",
    )

    llm_description_char_limit: int = Field(
        default=1500,
        alias="LLM_DESCRIPTION_CHAR_LIMIT",
    )
    llm_max_output_tokens: int = Field(
        default=180,
        alias="LLM_MAX_OUTPUT_TOKENS",
    )

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(
        default=1536,
        alias="EMBEDDING_DIMENSIONS",
    )

    # ── Scraping ──────────────────────────────────────────────────────────────
    scraping_concurrency: int = Field(
        default=10,
        alias="SCRAPING_CONCURRENCY",
        description="Max simultaneous HTTP connections during scraping",
    )

    # ── Database write tuning ─────────────────────────────────────────────────
    db_batch_size: int = Field(
        default=50,
        alias="DB_BATCH_SIZE",
        description="Number of rows per bulk insert batch",
    )

    # ── Pipeline freshness ────────────────────────────────────────────────────
    freshness_window_hours: int = Field(
        default=168,
        alias="FRESHNESS_WINDOW_HOURS",
        description="Jobs older than this are considered stale and re-fetched",
    )

    # ── Curated feed URLs ─────────────────────────────────────────────────────
    simplify_feed_url: str = Field(
        default="https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
        alias="SIMPLIFY_FEED_URL",
    )
    hiringcafe_feed_url: str = Field(
        default="https://hiring.cafe/",
        alias="HIRINGCAFE_FEED_URL",
    )

    # ── Scheduler (APScheduler daily trigger) ─────────────────────────────────
    scheduler_hour: int = Field(
        default=2,
        alias="SCHEDULER_HOUR",
        description="UTC hour for the daily pipeline trigger",
    )
    scheduler_minute: int = Field(
        default=0,
        alias="SCHEDULER_MINUTE",
        description="UTC minute for the daily pipeline trigger",
    )


settings = Settings()
