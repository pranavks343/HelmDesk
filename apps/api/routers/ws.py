"""`GET /ws/tickets/{id}` - live status + agent-drafted-reply stream.

Auth note: browsers can't set an Authorization header on a WebSocket handshake, so the access
token is passed as a query param (?token=...) here instead - a documented, common pattern, but
worth flagging as weaker than a header (tokens can end up in server access logs / browser history).
The production upgrade path is a short-lived, single-use WS ticket minted by an authenticated REST
call just before connecting.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from core.security import decode_token
from ws.manager import manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws/tickets/{ticket_id}")
async def ticket_ws(websocket: WebSocket, ticket_id: str, token: str | None = None) -> None:
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing token")
        return
    try:
        decode_token(token, expected_type="access")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="invalid token")
        return

    await manager.connect(ticket_id, websocket)
    try:
        while True:
            # Clients don't need to send anything; we just need the recv loop to detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ticket_id, websocket)
