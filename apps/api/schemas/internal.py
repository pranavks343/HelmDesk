from __future__ import annotations

from pydantic import BaseModel


class InternalTicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    ai_summary: str | None = None


class InternalMessageCreate(BaseModel):
    text: str
    sender: str = "ai_agent"
