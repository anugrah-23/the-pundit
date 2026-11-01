"""Runtime configuration, read from environment variables (or a .env file)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PUNDIT_", extra="ignore")

    # Data
    corpus_dir: Path = BACKEND_DIR / "data" / "corpus"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'pundit.db'}"

    # Embeddings: "sentence-transformers" in production, "hashing" for tests/offline dev
    embedder: str = "sentence-transformers"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # LLM providers: "gemini", "groq" or "mock"
    answer_provider: str = "mock"
    answer_model: str = "gemini-2.5-flash"
    judge_provider: str = "mock"
    judge_model: str = "openai/gpt-oss-120b"
    opponent_provider: str = "mock"
    opponent_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Cache
    cache_threshold: float = 0.88
    cache_max_age_days: int = 14
    negation_guard: bool = True
    entity_guard: bool = True
    judge_gate: bool = True

    # Retrieval
    top_k: int = 4

    # Limits
    ask_per_hour: int = 20
    debate_per_hour: int = 5
    challenge_per_hour: int = 15
    daily_llm_budget: int = 800
    max_question_chars: int = 300
    max_post_chars: int = 1500

    # Guardrails
    fake_secret: str = "PUNDIT-ADMIN-7731"
    allowed_link_domains: list[str] = ["understat.com", "fbref.com"]

    # Web
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
