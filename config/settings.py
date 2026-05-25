# 2.1 config/settings.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/lumia_dev"

    # Embeddings (no LLM‑style generation)
    EMBEDDING_PROVIDER: str = "huggingface_embedding"
    EMBEDDING_MODEL_NAME: str = "Supabase/bge-small-en"
    EMBEDDING_DEVICE: str = "auto"  # or "cpu", "cuda"

    # Job API
    REMOTIVE_API_URL: str = "https://remotive.com/api/remote-jobs"

    # Optional: on‑demand LLM (only when user wants “AI‑explanations”)
    LLM_ENABLED: bool = True              # can be False for dev‑only / no‑API modes
    LLM_PROVIDER: str = "huggingface_api" # or ollama / local once you choose
    LLM_MODEL: str = "meta-llama/Meta-Llama-3-8B-Instruct"

    # General
    DEBUG: bool = True

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


settings = Settings()