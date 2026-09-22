"""Centralized settings, loaded from environment / .env (never hardcoded secrets)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Postgres (source of truth: users, tickets, ticket_events)
    postgres_dsn: str = "postgresql+asyncpg://supportpilot:supportpilot@localhost:5432/supportpilot"

    # MongoDB (chat_messages: high-write, flexible schema)
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "supportpilot"

    # Redis (cache + pub/sub event bus + rate limiting)
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "dev-secret-change-me"  # noqa: S105 - overridden via env in real deployments
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS - locked to the frontend origin, not "*"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Rate limiting
    rate_limit_auth_per_minute: int = 10
    rate_limit_ticket_create_per_minute: int = 20

    # gRPC notifier
    notifier_grpc_target: str = "localhost:50051"

    environment: str = "development"


settings = Settings()
