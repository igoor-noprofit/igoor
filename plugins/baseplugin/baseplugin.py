from settings_manager import SettingsManager
from status_manager import StatusManager
from plugin_manager import hookimpl, PluginManager
from websocket_server import websocket_server
import os,json,asyncio
class Baseplugin:
    def __init__(self, plugin_name="baseplugin", pm=None):
        print ("__init__ plugin : " + plugin_name)
        self.plugin_name = plugin_name
        if pm is None:
            print ("no plugin manager passed")
            # sys.exit()     
        if isinstance(pm, PluginManager):
            print("Valid PluginManager instance passed.")
            self.pm = pm
        else:
            print("Warning: pm is not a PluginManager instance.")
        
        self.plugin_name = plugin_name
        self.settings_manager = SettingsManager()
        self.status_manager = StatusManager()
        
        # self.pm = pm
        # Construct the plugin folder path
        self.app_name = os.getenv('IGOOR_APPNAME')  # Get the application name from the environment variable
        self.appdata_path = os.getenv('APPDATA')  # Get the APPDATA path from the environment variable
        self.plugin_folder = os.path.join(self.appdata_path, self.app_name, 'plugins', plugin_name)
        # Create the directory if it doesn't exist
        if not os.path.exists(self.plugin_folder):
            print("CREATING FOLDER ", self.plugin_folder)
            os.makedirs(self.plugin_folder)
        else:
            print("FOLDER EXISTING: " + self.plugin_folder)
        websocket_server.register_message_handler(self.plugin_name, self.process_incoming_message)

        
    @hookimpl
    def get_frontend_components(self):
        vue_component = self.plugin_name + "_component.vue"
        print("loading vue component ",vue_component)
        return [
            {
                "vue": vue_component
            }
        ]

    def get_my_settings(self) -> dict:
        """
        Retrieve settings specific to the plugin.
        """
        print("getting settings for ", self.plugin_name)
        return self.settings_manager.get_plugin_settings(self.plugin_name)

    def update_my_settings(self, key: str, value: any):
        """
        Update settings for a specific plugin.
        """
        current_settings = self.get_my_settings()
        current_settings[key] = value
        self.settings_manager.update_plugin_settings(self.plugin_name, current_settings)
        self.settings_manager.save_settings()
        
    def update_status(self, status):
        print(f"Plugin {self.__class__.__name__} received status update: {status}")
        # Implement specific status handling logic here

    def cleanup(self):
        self.status_manager.unregister_observer(self)
        
    def subfolder_exists(self, subfolder_name: str):
        subfolder_path = os.path.join(self.plugin_folder, subfolder_name)
        if not os.path.exists(subfolder_path):
            return False
        return True    
    
    def is_folder_empty(self, subfolder_name: str) -> bool:
        """
        Check if the specified subfolder is empty.

        :param subfolder_name: The name of the subfolder to check.
        :return: True if the subfolder is empty, False otherwise.
        """
        subfolder_path = os.path.join(self.plugin_folder, subfolder_name)
        if os.path.exists(subfolder_path) and os.path.isdir(subfolder_path):
            return not any(os.listdir(subfolder_path))
        else:
            print(f"Subfolder {subfolder_path} does not exist or is not a directory.")
            return False
    
    def create_subfolder(self, subfolder_name: str):
        """
        Create a subfolder inside the plugin folder if it doesn't exist.
        Return the full path if created, otherwise return False.
        """
        subfolder_path = os.path.join(self.plugin_folder, subfolder_name)
        try:
            if not os.path.exists(subfolder_path):
                print(f"CREATING SUBFOLDER {subfolder_path}")
                os.makedirs(subfolder_path)
                return subfolder_path
            else:
                print(f"SUBFOLDER ALREADY EXISTS: {subfolder_path}")
                return subfolder_path
        except Exception as e:
            print(f"Failed to create subfolder {subfolder_path}: {e}")
            return False
        
    async def wait_for_socket_and_send(self, message, plugin_name=None):
        """
        Waits for the socket to be ready and then sends a message to the frontend.
        
        :param message: The message to be sent once the socket is ready.
        :param plugin_name: (Optional) The plugin name to send the message to. If not provided, uses self.plugin_name.
        """
        target_plugin_name = plugin_name or self.plugin_name
        print(f"Wait for socket CALLED to send message: {message} to: {target_plugin_name}")
        while not websocket_server.is_socket_open(target_plugin_name):
            await asyncio.sleep(1)  # Wait for 1 second before checking again
            print(f"Waiting for socket to open, to send {message} to {target_plugin_name}")
        self.send_message_to_frontend(message, target_plugin_name)

    async def send_status(self, status):
        # Send a JSON message where status=ready
        message = json.dumps({"status": status})
        
        success = await self.wait_for_socket_and_send(message)
        return success
    
    async def send_switch_view_to_app(self,view):
        print("Switching view to " + view)
        await self.send_message_to_app({"switchview":view})
        
    async def send_message_to_app(self, message):
        """
        Wrapper that sends a message to the Vue app

        :param message: The message to be sent.
        """
        success = await self.wait_for_socket_and_send(message, 'app')
        return success 
            
    def send_message_to_frontend(self, message, plugin_name=None):
        """
        Sends a message to the designated plugin's frontend channel.

        :param message: The message to be sent.
        :param plugin_name: (Optional) The plugin name to send the message to. If not provided, uses self.plugin_name.
        """
        # Use the provided plugin_name or default to self.plugin_name
        target_plugin_name = plugin_name or self.plugin_name

        if websocket_server.is_socket_open(target_plugin_name):
            if not (target_plugin_name=='app'):
                print(f"{target_plugin_name} BACKEND starts sending message to FRONTEND via ws")
            else:
                print(f"BACKEND starts sending message to APP via ws")
            try:
                # Ensure the message is a JSON string
                if isinstance(message, dict):
                    message = json.dumps(message)
                return websocket_server.send_message(target_plugin_name, message)
            except Exception as e:
                print(f"Error while sending message to {target_plugin_name} frontend: {e}")
        else:
            print(f"{target_plugin_name} frontend is not ready")
            
    def process_incoming_message(self, message):
        """
        Process the incoming message.
        
        :param message: The message received from the WebSocket.
        """
        # Implement your message processing logic here
        print(f"Default processing message for {self.plugin_name}: {message}")
        
        # Check if the message is {"socket":"ready"}
        try:
        # Attempt to parse the message as JSON
            message_dict = json.loads(message)
        except json.JSONDecodeError:
                print("Received message is not valid JSON.")
                return
            
        # Check if the message is {"socket":"ready"}
        # if message_dict == {"socket": "ready"}:
        #    self.socket_ready = True