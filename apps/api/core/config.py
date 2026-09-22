"""Centralized settings, loaded from environment / .env (never hardcoded secrets)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_HERE = Path(__file__).resolve()
# Local dev: core/config.py -> apps/api -> apps -> <repo root> is 3 levels up. Inside the Docker
# image the layout is flattened (WORKDIR /app *is* apps/api's content, with no repo-root wrapper
# above it), so that 4th parent doesn't exist - `.parents[3]` raised IndexError and crashed the
# container on startup. Docker sets every setting via real environment variables anyway (see
# infra/docker-compose.yml), so the root .env lookup is a local-dev-only convenience; fall back to
# apps/api's own directory when the repo-root guess isn't available rather than crashing.
REPO_ROOT = _HERE.parents[3] if len(_HERE.parents) > 3 else _HERE.parents[-1]
_LOCAL_ENV = _HERE.parents[1] / ".env"  # apps/api/.env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", _LOCAL_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    # Shared secret for service-to-service calls (notifier -> api), not a user JWT. See
    # routers/internal.py.
    internal_service_token: str = "dev-internal-token-change-me"  # noqa: S105

    environment: str = "development"


settings = Settings()
