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
        
    async def wait_for_socket_and_send(self, message):
        """
        Waits for the socket to be ready and then sends a message to the frontend.
        
        :param message: The message to be sent once the socket is ready.
        """
        while not websocket_server.is_socket_open(self.plugin_name):
            await asyncio.sleep(1)  # Wait for 1 second before checking again
            print(".")
        self.send_message_to_frontend(message)

    async def send_status(self, status):
        # Send a JSON message where status=ready
        message = json.dumps({"status": status})
        
        success = await self.wait_for_socket_and_send(message)
        return success
        
    def send_message_to_frontend(self, message):
        if websocket_server.is_socket_open(self.plugin_name):
            print(self.plugin_name + " BACKEND starts sending message to FRONTEND via ws")
            """
            Sends a message to the designated plugin's frontend channel.
            
            :param message: The message to be sent.
            """
            try:
                # Ensure the message is a JSON string
                if isinstance(message, dict):
                    message = json.dumps(message)
                return websocket_server.send_message(self.plugin_name, message)
            except Exception as e:
                print(f"Error while sending message to {self.plugin_name} frontend: {e}")
        else:
            print(f" {self.plugin_name} frontend is not ready")
            
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