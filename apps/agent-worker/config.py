from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "apps/agent-worker/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    notifier_grpc_target: str = "localhost:50051"

    # LLM provider: "fake" (default, deterministic, offline) or "anthropic" (opt-in, needs a key).
    llm_provider: str = "fake"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    auto_resolve_confidence: float = 0.75


settings = Settings()
