from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TicketStatus = Literal["open", "triaged", "in_progress", "resolved"]


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class TicketOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    status: TicketStatus
    priority: str | None = None
    ai_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: str | None = None
    ai_summary: str | None = None


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class MessageOut(BaseModel):
    ticket_id: str
    sender: str
    text: str
    created_at: datetime
