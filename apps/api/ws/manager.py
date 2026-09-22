"""In-process WebSocket connection registry, keyed by ticket_id.

Single-process only (fine for this project's scale, per §13's non-goals): with multiple `api`
replicas you'd need connections to be process-agnostic, e.g. by having every replica subscribe to
Redis and only push to the sockets it personally holds (which is exactly what this manager does -
see ws/redis_bridge.py - so it already generalizes to that case for free)."""

from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, ticket_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[ticket_id].add(websocket)

    def disconnect(self, ticket_id: str, websocket: WebSocket) -> None:
        self._connections[ticket_id].discard(websocket)
        if not self._connections[ticket_id]:
            self._connections.pop(ticket_id, None)

    async def broadcast(self, ticket_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(ticket_id, ()):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - a dead socket shouldn't break the broadcast
                dead.append(ws)
        for ws in dead:
            self.disconnect(ticket_id, ws)

    def connection_count(self, ticket_id: str) -> int:
        return len(self._connections.get(ticket_id, ()))


manager = ConnectionManager()
