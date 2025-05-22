'''
Websocket server is used to communicate from plugin backend to to its Vue frontend (or to the Vue app) 
'''
import asyncio
import threading
from websockets import serve, WebSocketServerProtocol
# Removed: import os
# Removed: from utils import setup_logger

# Removed: __appname__ = "igoor"

class WebSocketServer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WebSocketServer, cls).__new__(cls)
        return cls._instance
    
    def is_socket_open(self, plugin_name: str) -> bool:
        """
        Check if a specific WebSocket connection is open for a given plugin.
        """
        if plugin_name in self.active_connections:
            return any(websocket.open for websocket in self.active_connections[plugin_name])
        return False
    
    def __init__(self):
        if hasattr(self, 'initialized') and self.initialized:
            return
        
        print("Initializing WebSocketServer...") # Reverted to print

        self.active_connections = {}
        self.message_handlers = {}
        self.loop = asyncio.new_event_loop()
        self.initialized = True
        self.server_thread = threading.Thread(target=self.run_server_thread, daemon=True)
        print("WebSocketServer initialized.") # Reverted to print

    async def websocket_handler(self, websocket: WebSocketServerProtocol, path: str):
        plugin_name = path.strip("/")
        print(f"New WebSocket connection for plugin: {plugin_name} from {websocket.remote_address}") # Reverted to print
        if plugin_name not in self.active_connections:
            self.active_connections[plugin_name] = set()
        self.active_connections[plugin_name].add(websocket)
        
        try:
            async for message in websocket:
                print(f"DEBUG: Received message from {plugin_name} ({websocket.remote_address}): {message[:200]}") # Reverted to print
                # Process incoming messages if needed
                if plugin_name in self.message_handlers:
                    try:
                        self.message_handlers[plugin_name](message)
                    except Exception as e:
                        print(f"ERROR: Error processing message for {plugin_name} from {websocket.remote_address}: {e}") # Reverted to print
                        # For more detailed traceback with print:
                        # import traceback
                        # traceback.print_exc()
                else:
                    print(f"WARNING: No message handler registered for plugin: {plugin_name}") # Reverted to print
        except Exception as e:
            print(f"ERROR: WebSocket error for {plugin_name} ({websocket.remote_address}): {e}") # Reverted to print
            # import traceback
            # traceback.print_exc()
        finally:
            print(f"WebSocket connection closed for plugin: {plugin_name} from {websocket.remote_address}") # Reverted to print
            if plugin_name in self.active_connections and websocket in self.active_connections[plugin_name]:
                self.active_connections[plugin_name].remove(websocket)
                if not self.active_connections[plugin_name]:
                    del self.active_connections[plugin_name]
                    print(f"All connections for plugin {plugin_name} closed. Removing from active connections.") # Reverted to print
                
    def register_message_handler(self, plugin_name, handler):
        """
        Register a message handler for a specific plugin.
        """
        print(f"Registering message handler for plugin: {plugin_name}") # Reverted to print
        self.message_handlers[plugin_name] = handler

    async def start_server(self):
        # Initialize the WebSocket server
        print("Starting WebSocket server on localhost:9715") # Reverted to print
        try:
            self.server = await serve(self.websocket_handler, "localhost", 9715)
            print("WebSocket server started successfully.") # Reverted to print
            await self.server.wait_closed()
        except Exception as e:
            print(f"ERROR: Failed to start WebSocket server: {e}") # Reverted to print
            # import traceback
            # traceback.print_exc()
            raise

    def run_server_thread(self):
        print("WebSocket server thread started.") # Reverted to print
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start_server())
        except Exception as e:
            print(f"ERROR: Exception in server thread: {e}") # Reverted to print
            # import traceback
            # traceback.print_exc()
        finally:
            print("WebSocket server thread finished.") # Reverted to print


    def start(self):
        if not self.server_thread.is_alive():
            print("Attempting to start WebSocket server thread.") # Reverted to print
            self.server_thread.start()
        else:
            print("WebSocket server thread is already alive.") # Reverted to print
    
    def stop(self):
        print("Stopping WebSocket server...") # Reverted to print
        # Stop the server and close all connections
        if hasattr(self, 'server') and self.server:
            self.loop.call_soon_threadsafe(self.server.close)
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        active_connections_copy = dict(self.active_connections) 
        for plugin_name, connections in active_connections_copy.items():
            print(f"Closing connections for plugin: {plugin_name}") # Reverted to print
            for websocket in list(connections): 
                if websocket.open:
                    asyncio.run_coroutine_threadsafe(websocket.close(), self.loop)
        
        if self.server_thread.is_alive():
            print("Waiting for server thread to join...") # Reverted to print
            self.server_thread.join(timeout=5.0) 
            if self.server_thread.is_alive():
                print("WARNING: Server thread did not join in time.") # Reverted to print
            else:
                print("Server thread joined.") # Reverted to print
        print("WebSocket server stopped.") # Reverted to print

    def send_message(self, plugin_name: str, message: str):
        print(f"DEBUG: Sending message to plugin {plugin_name}: {message[:200]}") # Reverted to print
        # Sends a message to all connections registered under a specific plugin name
        if plugin_name in self.active_connections:
            connections = list(self.active_connections[plugin_name]) 
            if not connections:
                print(f"WARNING: No active websockets for plugin {plugin_name} though plugin key exists.") # Reverted to print
                return False
            for websocket in connections:
                if websocket.open:
                    try:
                        asyncio.run_coroutine_threadsafe(websocket.send(message), self.loop)
                    except Exception as e:
                        print(f"ERROR: Error sending message to {plugin_name} ({websocket.remote_address}): {e}") # Reverted to print
                        # import traceback
                        # traceback.print_exc()
                else:
                    print(f"WARNING: Websocket for {plugin_name} ({websocket.remote_address}) is not open. Cannot send message.") # Reverted to print
            return True
        else:
            print(f"WARNING: Plugin {plugin_name} is not actively connected. Cannot send message.") # Reverted to print
            return False

# Instantiate and start the server
websocket_server = WebSocketServer()
websocket_server.start() # Ensured this is active for direct script execution