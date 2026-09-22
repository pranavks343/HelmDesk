"""Service-to-service endpoints, called by `notifier` after it relays an agent-worker triage
result (agents.md §2, §7). Gated by a shared secret (core/internal_auth.py), not a user JWT -
these mutate any ticket regardless of who owns it, which is correct for a trusted internal caller
and would be a serious bug if exposed to end users."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.internal_auth import require_internal_token
from core.redis_client import CHANNEL_TICKET_MESSAGE, CHANNEL_TICKET_UPDATED, get_redis
from models.ticket import Ticket
from mongo.client import ChatMessageRepo
from routers.tickets import _log_event, _parse_uuid
from schemas.internal import InternalMessageCreate, InternalTicketUpdate
from schemas.ticket import MessageOut, TicketOut

router = APIRouter(
    prefix="/internal/tickets", tags=["internal"], dependencies=[Depends(require_internal_token)]
)


@router.patch("/{ticket_id}", response_model=TicketOut)
async def internal_update_ticket(
    ticket_id: str, payload: InternalTicketUpdate, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    tid = _parse_uuid(ticket_id)
    ticket = await db.get(Ticket, tid)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(ticket, field, value)
    await _log_event(db, tid, "agent_updated", changes)
    await db.commit()
    await db.refresh(ticket)

    redis = get_redis()
    event = json.dumps({"ticket_id": str(tid), "type": "updated", **changes})
    await redis.publish(CHANNEL_TICKET_UPDATED, event)
    return TicketOut.model_validate(ticket)


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def internal_post_message(
    ticket_id: str, payload: InternalMessageCreate, db: AsyncSession = Depends(get_db)
) -> MessageOut:
    tid = _parse_uuid(ticket_id)
    ticket = await db.get(Ticket, tid)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")

    repo = ChatMessageRepo()
    doc = await repo.add_message(ticket_id=str(tid), sender=payload.sender, text=payload.text)

    redis = get_redis()
    await redis.publish(
        CHANNEL_TICKET_MESSAGE,
        json.dumps({"ticket_id": str(tid), "type": "message", "sender": doc["sender"], "text": doc["text"]}),
    )
    return MessageOut(
        ticket_id=str(tid), sender=doc["sender"], text=doc["text"], created_at=doc["created_at"]
    )
