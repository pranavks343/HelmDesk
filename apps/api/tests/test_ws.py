"""WS live-update tests. Starlette's TestClient (sync, its own event loop) drives the socket;
the async `client` fixture drives the REST calls that trigger events onto it."""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


async def _login(client, email="wsuser@example.com"):
    await client.post("/auth/register", json={"email": email, "password": "hunter2pass", "role": "customer"})
    r = await client.post("/auth/login", json={"email": email, "password": "hunter2pass"})
    return r.json()["access_token"]


async def test_ws_rejects_missing_token(client):
    from main import app

    with TestClient(app) as tc, pytest.raises(WebSocketDisconnect) as exc_info:
        with tc.websocket_connect("/ws/tickets/abc"):
            pass
    assert exc_info.value.code == 1008


async def test_ws_rejects_invalid_token(client):
    from main import app

    with TestClient(app) as tc, pytest.raises(WebSocketDisconnect) as exc_info:
        with tc.websocket_connect("/ws/tickets/abc?token=garbage"):
            pass
    assert exc_info.value.code == 1008


async def test_ws_receives_ticket_update_event(client):
    token = await _login(client)
    r = await client.post("/tickets", json={"title": "t"}, headers={"Authorization": f"Bearer {token}"})
    ticket_id = r.json()["id"]

    from main import app
    from ws.manager import manager

    with TestClient(app) as tc, tc.websocket_connect(f"/ws/tickets/{ticket_id}?token={token}"):
        assert manager.connection_count(ticket_id) == 1
        await manager.broadcast(ticket_id, {"ticket_id": ticket_id, "type": "updated", "status": "resolved"})
