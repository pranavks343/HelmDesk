from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.db import get_db
from core.rate_limit import enforce_rate_limit
from core.redis_client import CHANNEL_TICKET_CREATED, CHANNEL_TICKET_MESSAGE, get_redis
from core.security import CurrentUser, require_role
from models.ticket import Ticket, TicketEvent
from mongo.client import ChatMessageRepo
from schemas.ticket import MessageCreate, MessageOut, TicketCreate, TicketOut, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _parse_uuid(raw: str, what: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid {what}: {raw!r}") from exc


async def _log_event(db: AsyncSession, ticket_id: uuid.UUID, event_type: str, payload: dict) -> None:
    db.add(TicketEvent(ticket_id=ticket_id, type=event_type, payload_json=payload))


async def _get_owned_ticket(db: AsyncSession, ticket_id: uuid.UUID, user: CurrentUser) -> Ticket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
    if user.role == "customer" and str(ticket.user_id) != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your ticket")
    return ticket


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: Request, payload: TicketCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    await enforce_rate_limit(request, "ticket-create", settings.rate_limit_ticket_create_per_minute)
    ticket = Ticket(user_id=uuid.UUID(user.user_id), title=payload.title, status="open")
    db.add(ticket)
    await db.flush()
    await _log_event(db, ticket.id, "created", {"title": payload.title})
    await db.commit()
    await db.refresh(ticket)

    redis = get_redis()
    await redis.publish(
        CHANNEL_TICKET_CREATED,
        json.dumps({"ticket_id": str(ticket.id), "type": "created", "title": ticket.title}),
    )
    return TicketOut.model_validate(ticket)


@router.get("", response_model=list[TicketOut])
async def list_tickets(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[TicketOut]:
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if user.role == "customer":
        stmt = stmt.where(Ticket.user_id == uuid.UUID(user.user_id))
    rows = (await db.scalars(stmt)).all()
    return [TicketOut.model_validate(t) for t in rows]


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)) -> TicketOut:
    ticket = await _get_owned_ticket(db, _parse_uuid(ticket_id), user)
    return TicketOut.model_validate(ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketOut,
    dependencies=[Depends(require_role("agent", "admin"))],
)
async def update_ticket(
    ticket_id: str, payload: TicketUpdate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> TicketOut:
    tid = _parse_uuid(ticket_id)
    ticket = await db.get(Ticket, tid)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(ticket, field, value)
    await _log_event(db, tid, "updated", changes)
    await db.commit()
    await db.refresh(ticket)

    redis = get_redis()
    await redis.publish(
        "ticket.updated",
        json.dumps({"ticket_id": str(tid), "type": "updated", **changes}),
    )
    return TicketOut.model_validate(ticket)


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def post_message(
    ticket_id: str, payload: MessageCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> MessageOut:
    tid = _parse_uuid(ticket_id)
    await _get_owned_ticket(db, tid, user)  # 404/403 without leaking existence to strangers

    repo = ChatMessageRepo()
    doc = await repo.add_message(ticket_id=str(tid), sender=user.role, text=payload.text)

    redis = get_redis()
    await redis.publish(
        CHANNEL_TICKET_MESSAGE,
        json.dumps(
            {
                "ticket_id": str(tid),
                "type": "message",
                "sender": doc["sender"],
                "text": doc["text"],
            }
        ),
    )
    return MessageOut(
        ticket_id=str(tid), sender=doc["sender"], text=doc["text"], created_at=doc["created_at"]
    )


@router.get("/{ticket_id}/messages", response_model=list[MessageOut])
async def list_messages(
    ticket_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[MessageOut]:
    tid = _parse_uuid(ticket_id)
    await _get_owned_ticket(db, tid, user)
    repo = ChatMessageRepo()
    docs = await repo.list_messages(str(tid))
    return [
        MessageOut(ticket_id=d["ticket_id"], sender=d["sender"], text=d["text"], created_at=d["created_at"])
        for d in docs
    ]
