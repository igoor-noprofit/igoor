'''
Websocket server is used to communicate from plugin backend to to its Vue frontend (or Vue app) 
'''
import asyncio
import threading
from websockets import serve, WebSocketServerProtocol

class WebSocketServer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WebSocketServer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'initialized') and self.initialized:
            return
        self.active_connections = {}
        self.loop = asyncio.new_event_loop()
        self.initialized = True
        self.server_thread = threading.Thread(target=self.run_server_thread)

    async def websocket_handler(self, websocket: WebSocketServerProtocol, path: str):
        plugin_name = path.strip("/")
        if plugin_name not in self.active_connections:
            self.active_connections[plugin_name] = set()
        self.active_connections[plugin_name].add(websocket)
        
        try:
            async for message in websocket:
                # Process incoming messages if needed
                pass
        finally:
            self.active_connections[plugin_name].remove(websocket)
            if not self.active_connections[plugin_name]:
                del self.active_connections[plugin_name]

    async def start_server(self):
        # Initialize the WebSocket server
        self.server = await serve(self.websocket_handler, "localhost", 9715)
        await self.server.wait_closed()

    def run_server_thread(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.start_server())

    def start(self):
        if not self.server_thread.is_alive():
            self.server_thread.start()
    
    def stop(self):
        print("Stopping server")
        # Stop the server and close all connections
        if self.server:
            self.loop.call_soon_threadsafe(self.server.close)
            self.loop.call_soon_threadsafe(self.loop.stop)
        for plugin_name, connections in self.active_connections.items():
            for websocket in connections:
                asyncio.run_coroutine_threadsafe(websocket.close(), self.loop)
        self.server_thread.join()

    def send_message(self, plugin_name: str, message: str):
        print ("Sending message " + message + " to plugin " + plugin_name)
        # Sends a message to all connections registered under a specific plugin name
        if plugin_name in self.active_connections:
            for websocket in self.active_connections[plugin_name]:
                asyncio.run_coroutine_threadsafe(websocket.send(message), self.loop)
        else:
            print("plugin is not actively connected")

# Instantiate and start the server
websocket_server = WebSocketServer()
websocket_server.start()