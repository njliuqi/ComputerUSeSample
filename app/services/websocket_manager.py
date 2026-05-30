import asyncio
from collections import defaultdict

from fastapi import WebSocket

from app.schemas.events import EventRead


class WebSocketConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(session_id)
        if not connections:
            return

        connections.discard(websocket)
        if not connections:
            self._connections.pop(session_id, None)

    async def broadcast_event(self, event: EventRead) -> None:
        async with self._lock:
            connections = list(self._connections.get(event.session_id, set()))

        stale_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except RuntimeError:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(event.session_id, websocket)

    def broadcast_event_nowait(self, event: EventRead) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.broadcast_event(event))

    def clear(self) -> None:
        self._connections.clear()


websocket_manager = WebSocketConnectionManager()


def get_websocket_manager() -> WebSocketConnectionManager:
    return websocket_manager
