"""Shared-secret auth for service-to-service calls (notifier -> api), distinct from user JWTs.
Not a substitute for real mTLS/service identity in production - documented as the upgrade path,
same spirit as the other "enterprise-flavored, not production-grade" security notes in agents.md §9.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from core.config import settings


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_token, settings.internal_service_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid internal service token")
