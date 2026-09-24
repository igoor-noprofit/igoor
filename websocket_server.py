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
        # Single-recipient traffic (streamed TTS audio: play_stream, binary
        # chunks, play_stream_end) goes to the PRIMARY connection of a plugin
        # name - the most recently connected websocket. Broadcasting it made
        # every open page play the same voice on top of each other, heard as a
        # doubled voice with a reverb-like artifact.
        self.primary_connections: Dict[str, WebSocket] = {}
        self._connect_seq: Dict[WebSocket, int] = {}
        self._next_seq = 0
        self.message_handlers: Dict[str, Callable[[str], None]] = {}
        self._on_primary_change: Optional[Callable[[str], None]] = None
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
            self._connect_seq[websocket] = self._next_seq
            self._next_seq += 1
            self.primary_connections[plugin_name] = websocket
        print(f"WebSocket connected for plugin: {plugin_name}")
        # the new connection just became the primary
        self._fire_primary_change(plugin_name)

    async def disconnect(self, plugin_name: str, websocket: WebSocket) -> None:
        primary_changed = False
        with self._lock:
            connections = self.active_connections.get(plugin_name)
            if connections and websocket in connections:
                connections.remove(websocket)
                if not connections:
                    self.active_connections.pop(plugin_name, None)
            self._connect_seq.pop(websocket, None)
            if self.primary_connections.get(plugin_name) is websocket:
                self._promote_primary_locked(plugin_name)
                primary_changed = True
        print(f"WebSocket disconnected for plugin: {plugin_name}")
        if primary_changed:
            self._fire_primary_change(plugin_name)

    def _promote_primary_locked(self, plugin_name: str) -> None:
        """Caller holds self._lock. Pick a new primary - the most recently
        connected remaining socket - or clear the slot when none remain."""
        connections = self.active_connections.get(plugin_name)
        if connections:
            self.primary_connections[plugin_name] = max(
                connections, key=lambda ws: self._connect_seq.get(ws, -1)
            )
        else:
            self.primary_connections.pop(plugin_name, None)

    def _primary(self, plugin_name: str) -> Optional[WebSocket]:
        """The primary websocket, re-resolved (and re-promoted) when the
        previous one disappeared without a clean disconnect."""
        with self._lock:
            primary = self.primary_connections.get(plugin_name)
            connections = self.active_connections.get(plugin_name)
            if primary is None or not connections or primary not in connections:
                self._promote_primary_locked(plugin_name)
                primary = self.primary_connections.get(plugin_name)
            return primary

    def register_message_handler(self, plugin_name: str, handler: Callable[[str], None]) -> None:
        with self._lock:
            self.message_handlers[plugin_name] = handler
        print(f"Registered message handler for plugin: {plugin_name}")

    def set_on_primary_change(self, handler: Callable[[str], None]) -> None:
        """Install a handler fired whenever the primary connection of a plugin
        name changes: a new page connects, or the primary disconnects / is
        pruned and another connection is promoted. Fired fire-and-forget from
        hub internals (possibly from the hub loop thread - handlers must not
        block); exceptions are logged and swallowed."""
        self._on_primary_change = handler

    def _fire_primary_change(self, plugin_name: str) -> None:
        handler = self._on_primary_change
        if handler is None:
            return
        try:
            handler(plugin_name)
        except Exception as exc:
            print(f"ERROR: primary-change handler failed for {plugin_name}: {exc}")

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

    def _send_to(self, plugin_name: str, sockets, sender) -> bool:
        """Schedule sender(ws) on the hub loop for every alive socket; prune
        dead ones from the hub (promoting a new primary if needed). True when
        at least one send was scheduled."""
        if self.loop is None:
            raise RuntimeError("WebSocket event loop is not initialized")

        stale: list[WebSocket] = []
        scheduled = 0
        for websocket in sockets:
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    asyncio.run_coroutine_threadsafe(sender(websocket), self.loop)
                    scheduled += 1
                except Exception as exc:
                    print(f"ERROR: Error sending message to {plugin_name}: {exc}")
                    stale.append(websocket)
            else:
                stale.append(websocket)

        if stale:
            promoted = False
            with self._lock:
                connections = self.active_connections.get(plugin_name)
                for ws in stale:
                    if connections:
                        connections.discard(ws)
                    self._connect_seq.pop(ws, None)
                if connections is not None and not connections:
                    self.active_connections.pop(plugin_name, None)
                if any(self.primary_connections.get(plugin_name) is ws for ws in stale):
                    self._promote_primary_locked(plugin_name)
                    promoted = True
            if promoted:
                self._fire_primary_change(plugin_name)

        return scheduled > 0

    def send_message(self, plugin_name: str, message: str) -> bool:
        with self._lock:
            connections = list(self.active_connections.get(plugin_name, set()))

        if not connections:
            print(f"WARNING: Plugin {plugin_name} is not actively connected. Cannot send message.")
            return False

        return self._send_to(plugin_name, connections, lambda ws: ws.send_text(message))

    def send_bytes(self, plugin_name: str, data: bytes) -> bool:
        with self._lock:
            connections = list(self.active_connections.get(plugin_name, set()))

        if not connections:
            print(f"WARNING: Plugin {plugin_name} is not actively connected. Cannot send binary data.")
            return False

        return self._send_to(plugin_name, connections, lambda ws: ws.send_bytes(data))

    def send_message_primary(self, plugin_name: str, message: str) -> bool:
        """Send a text message to the primary connection only. Streamed-audio
        control messages (play_stream / play_stream_end) use this so secondary
        pages never start a player for audio they must not play."""
        primary = self._primary(plugin_name)
        if primary is None:
            print(f"WARNING: Plugin {plugin_name} is not actively connected. Cannot send message.")
            return False
        return self._send_to(plugin_name, [primary], lambda ws: ws.send_text(message))

    def send_bytes_primary(self, plugin_name: str, data: bytes) -> bool:
        """Send binary data to the primary connection only. Streamed TTS audio
        chunks go here: broadcasting them made every open page play the same
        voice simultaneously."""
        primary = self._primary(plugin_name)
        if primary is None:
            print(f"WARNING: Plugin {plugin_name} is not actively connected. Cannot send binary data.")
            return False
        return self._send_to(plugin_name, [primary], lambda ws: ws.send_bytes(data))

    def send_message_by_role(self, plugin_name: str, primary_message: str, secondary_message: str) -> bool:
        """Send primary_message to the primary connection and
        secondary_message to every other connection. Used to tell each
        connected page its role (e.g. audio_role primary/secondary) so
        single-recipient behaviors - streamed TTS playback, the microphone -
        stay owned by exactly one page. True when at least one page received
        its message."""
        primary = self._primary(plugin_name)
        with self._lock:
            connections = self.active_connections.get(plugin_name, set())
            others = [ws for ws in connections if ws is not primary]

        sent = False
        if primary is not None:
            sent = self._send_to(plugin_name, [primary], lambda ws: ws.send_text(primary_message))
        if others:
            sent = self._send_to(plugin_name, others, lambda ws: ws.send_text(secondary_message)) or sent
        return sent

    async def _close_all(self) -> None:
        with self._lock:
            snapshot = {
                name: list(connections)
                for name, connections in self.active_connections.items()
            }
            self.active_connections.clear()
            self.primary_connections.clear()
            self._connect_seq.clear()

        for name, connections in snapshot.items():
            for websocket in connections:
                if websocket.application_state != WebSocketState.DISCONNECTED:
                    try:
                        await websocket.close()
                    except Exception as exc:
                        print(f"WARNING: Failed closing websocket for {name}: {exc}")

    def stop(self, timeout: float = 1.0) -> None:
        if self.loop and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._close_all(), self.loop)
            try:
                # Wait briefly for the closes to land so the endpoint
                # receive-loops finish before the server is asked to exit.
                future.result(timeout=timeout)
            except Exception:
                pass  # loop died or a close hung - caller force-exits anyway


websocket_server = WebSocketHub()