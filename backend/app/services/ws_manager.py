from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[UUID, set[WebSocket]] = defaultdict(set)
        self.connection_users: dict[WebSocket, UUID] = {}
        self.connection_locks: dict[WebSocket, set[UUID]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, page_id: UUID, user_id: UUID) -> None:
        await websocket.accept()
        self.rooms[page_id].add(websocket)
        self.connection_users[websocket] = user_id

    def remember_lock(self, websocket: WebSocket, element_id: UUID) -> None:
        self.connection_locks[websocket].add(element_id)

    def disconnect(self, websocket: WebSocket, page_id: UUID) -> set[UUID]:
        self.rooms[page_id].discard(websocket)
        if not self.rooms[page_id]:
            self.rooms.pop(page_id, None)
        self.connection_users.pop(websocket, None)
        return self.connection_locks.pop(websocket, set())

    async def broadcast(self, page_id: UUID, message: dict, *, exclude: WebSocket | None = None) -> None:
        for connection in list(self.rooms.get(page_id, set())):
            if connection is exclude:
                continue
            try:
                await connection.send_json(message)
            except RuntimeError:
                self.rooms[page_id].discard(connection)


manager = ConnectionManager()
