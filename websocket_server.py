import asyncio
import threading
from typing import Callable, Dict, Optional, Set

from starlette.websockets import WebSocket, WebSocketState


class WebSocketHub:
    _instance: Optional["WebSocketHub"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.message_handlers: Dict[str, Callable[[str], None]] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()
        self._initialized = True

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, plugin_name: str, websocket: WebSocket) -> None:
        if self.loop is None:
            self.loop = asyncio.get_running_loop()

        await websocket.accept()
        with self._lock:
            self.active_connections.setdefault(plugin_name, set()).add(websocket)
        print(f"WebSocket connected for plugin: {plugin_name}")

    async def disconnect(self, plugin_name: str, websocket: WebSocket) -> None:
        with self._lock:
            connections = self.active_connections.get(plugin_name)
            if connections and websocket in connections:
                connections.remove(websocket)
                if not connections:
                    self.active_connections.pop(plugin_name, None)
        print(f"WebSocket disconnected for plugin: {plugin_name}")

    def register_message_handler(self, plugin_name: str, handler: Callable[[str], None]) -> None:
        with self._lock:
            self.message_handlers[plugin_name] = handler
        print(f"Registered message handler for plugin: {plugin_name}")

    async def handle_message(self, plugin_name: str, message: str) -> None:
        handler: Optional[Callable[[str], None]]
        with self._lock:
            handler = self.message_handlers.get(plugin_name)

        if handler is None:
            print(f"WARNING: No message handler registered for plugin: {plugin_name}")
            return

        try:
            # Check if handler is async and await it if needed
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
        except Exception as exc:
            print(f"ERROR: Error processing message for {plugin_name}: {exc}")

    def is_socket_open(self, plugin_name: str) -> bool:
        with self._lock:
            sockets = self.active_connections.get(plugin_name, set()).copy()

        for websocket in sockets:
            if websocket.client_state == WebSocketState.CONNECTED:
                return True
        print(f"No open websocket found for plugin: {plugin_name}")
        return False

    def send_message(self, plugin_name: str, message: str) -> bool:
        with self._lock:
            connections = list(self.active_connections.get(plugin_name, set()))

        if not connections:
            print(f"WARNING: Plugin {plugin_name} is not actively connected. Cannot send message.")
            return False

        if self.loop is None:
            raise RuntimeError("WebSocket event loop is not initialized")

        stale: list[WebSocket] = []
        for websocket in connections:
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    asyncio.run_coroutine_threadsafe(websocket.send_text(message), self.loop)
                except Exception as exc:
                    print(f"ERROR: Error sending message to {plugin_name}: {exc}")
                    stale.append(websocket)
            else:
                stale.append(websocket)

        if stale:
            with self._lock:
                current = self.active_connections.get(plugin_name)
                if current:
                    for ws in stale:
                        current.discard(ws)
                    if not current:
                        self.active_connections.pop(plugin_name, None)

        return True

    async def _close_all(self) -> None:
        with self._lock:
            snapshot = {
                name: list(connections)
                for name, connections in self.active_connections.items()
            }
            self.active_connections.clear()

        for name, connections in snapshot.items():
            for websocket in connections:
                if websocket.application_state != WebSocketState.DISCONNECTED:
                    try:
                        await websocket.close()
                    except Exception as exc:
                        print(f"WARNING: Failed closing websocket for {name}: {exc}")

    def stop(self) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._close_all(), self.loop)


websocket_server = WebSocketHub()