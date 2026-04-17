from version import __appname__, __version__, __codename__
from settings_manager import SettingsManager
from status_manager import StatusManager
from plugin_manager import hookimpl, PluginManager
from websocket_server import websocket_server
import os,json,asyncio
from pathlib import Path
from datetime import datetime
from utils import resource_path
from llm_manager import LLMManager
from utils import setup_logger
from db_manager import DatabaseManager

class Baseplugin:
    def __init__(self, plugin_name="baseplugin", pm=None):
        self.is_loaded = False
        self.ready = False
        print ("__init__ plugin : " + plugin_name)
        self.plugin_name = plugin_name
        
        self.logger = setup_logger(
            f'plugins.{plugin_name}', 
            os.path.join(os.getenv('APPDATA'), __appname__),
            separate_plugin_log=False
        )
        
        if pm is None:
            self.logger.warning ("no plugin manager passed")
            # sys.exit()     
        if isinstance(pm, PluginManager):
            self.pm = pm
        else:
            self.logger.warning("Warning: pm is not a PluginManager instance.")
        
        self.plugin_name = plugin_name
        self.settings_manager = SettingsManager()
        self.lang = self.settings_manager.get_lang()
        self.status_manager = StatusManager()
        
        # Load plugin metadata
        self._plugin_metadata = self._load_plugin_metadata()
        
        # Initialize database if needed
        self._db = None
        if self._plugin_metadata.get('requires_db', False):
            self._init_database()
        # self.pm = pm
        # Construct the plugin folder path
        self.app_name = __appname__  # Get the application name from the environment variable
        self.appdata_path = os.getenv('APPDATA')  # Get the APPDATA path from the environment variable
        self.plugin_folder = os.path.join(self.appdata_path, self.app_name, 'plugins', plugin_name)
        # Create the directory if it doesn't exist
        if not os.path.exists(self.plugin_folder):
            self.logger.info(f"CREATING FOLDER {self.plugin_folder}")
            os.makedirs(self.plugin_folder)
        else:
            print("FOLDER EXISTING: " + self.plugin_folder)
        websocket_server.register_message_handler(self.plugin_name, self.process_incoming_message)
        # 
        this_dir = os.path.dirname(os.path.abspath(__file__))  # This will be the plugin folder
        plugin_folder = os.path.abspath(os.path.join(this_dir, '..'))
        self._app_plugin_folder = os.path.join(plugin_folder, self.plugin_name)
        print(f"PLUGIN ROOT = {self._app_plugin_folder}")
    def mark_ready(self):
        self.ready = True
        
    @hookimpl
    def get_frontend_components(self):
        vue_component = self.plugin_name + "_component.vue"
        self.logger.info(f"loading vue component {vue_component}")
        return [
            {
                "vue": vue_component
            }
        ]

    def get_my_settings(self) -> dict:
        """
        Retrieve settings specific to the plugin.
        """
        return self.settings_manager.get_plugin_settings(self.plugin_name)

    
    def get_my_translations(self) -> dict:
        translations_path = os.path.join(self._app_plugin_folder, 'locales', self.lang, self.plugin_name + "_" + self.lang + ".json")
        return self.load_translation_file(translations_path)
    
    # Load prompts from a YAML file (unified at plugin root, with locale fallback)
    def get_my_prompts(self) -> dict:
        import yaml
        # Primary: unified prompts at plugin root
        prompts_path = os.path.join(self._app_plugin_folder, 'prompts.yaml')
        if not os.path.exists(prompts_path):
            # Fallback: legacy locale-specific prompts
            prompts_path = os.path.join(self._app_plugin_folder, 'locales', self.lang, 'prompts.yaml')
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            self.logger.warning(f"Prompts file not found: {prompts_path}")
            return {}
        except Exception as e:
            self.logger.error(f"Error loading prompts from {prompts_path}: {e}")
            return {}

    def get_bio_context(self) -> str:
        """Load biorecorder bio.md and return a formatted context string for LLM prompts.
        Returns an empty string if bio.md does not exist (plugin is optional)."""
        bio_path = Path(self.appdata_path, self.app_name, 'plugins', 'biorecorder', 'bio.md')
        if not bio_path.exists():
            return ""
        try:
            content = bio_path.read_text(encoding='utf-8').strip()
            mtime = datetime.fromtimestamp(bio_path.stat().st_mtime)
            formatted_date = mtime.strftime("%Y-%m-%d %H:%M")
            return (
                f"Biographical information edited by the user or caregiver, "
                f"last updated {formatted_date}:\n\n{content}"
            )
        except Exception as e:
            self.logger.warning(f"Could not load bio context: {e}")
            return ""

    def load_translation_file(self,translation_file_path):
        if not os.path.exists(translation_file_path):
            self.logger.warning(f"Translation file not found: {translation_file_path}")
            return {}
        try:
            with open(translation_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding prompts JSON: {e}")
            return {}
        
    def mass_update_my_settings(self, settings):
        try:
            if isinstance(settings, str):
                json_data = settings
            elif isinstance(settings, dict):
                json_data = json.dumps(settings)
            else:
                self.logger.error("Settings must be a dict or a JSON string.")
                return False
            # Check if the input is a valid JSON object
            parsed_data = json.loads(json_data)
            self.settings_manager.update_plugin_settings(self.plugin_name,parsed_data)
            if (self.settings_manager.save_settings()):
                self.settings_manager.load_settings()
                asyncio.create_task(self.pm.trigger_hook('global_settings_updated'))
                return True
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON data provided for mass update.")
            return False

    def update_my_settings(self, key: str, value: any):
        """
        Update settings for a specific plugin.
        """
        self.logger.info(f"{self.plugin_name} Updating {key} to {value}")
        current_settings = self.get_my_settings()
        current_settings[key] = value
        self.settings_manager.update_plugin_settings(self.plugin_name, current_settings)
        self.settings_manager.save_settings()
        
        
        
    def update_status(self, status):
        self.logger.info(f"Plugin {self.__class__.__name__} received status update: {status}")
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
            self.logger.warning(f"Subfolder {subfolder_path} does not exist or is not a directory.")
            return False
    
    def create_subfolder(self, subfolder_name: str):
        """
        Create a subfolder inside the plugin folder if it doesn't exist.
        Return the full path if created, otherwise return False.
        """
        subfolder_path = os.path.join(self.plugin_folder, subfolder_name)
        try:
            if not os.path.exists(subfolder_path):
                self.logger.debug(f"CREATING SUBFOLDER {subfolder_path}")
                os.makedirs(subfolder_path)
                return subfolder_path
            else:
                self.logger.debug(f"SUBFOLDER ALREADY EXISTS: {subfolder_path}")
                return subfolder_path
        except Exception as e:
            self.logger.error(f"Failed to create subfolder {subfolder_path}: {e}")
            return False
        
    async def wait_for_socket_and_send(self, message, plugin_name=None):
        """
        Waits for the socket to be ready and then sends a message to the frontend.
        
        :param message: The message to be sent once the socket is ready.
        :param plugin_name: (Optional) The plugin name to send the message to. If not provided, uses self.plugin_name.
        """
        target_plugin_name = plugin_name or self.plugin_name
        while not websocket_server.is_socket_open(target_plugin_name):
            await asyncio.sleep(1)  # Wait for 1 second before checking again
            self.logger.info(f"Waiting for socket to open, to send {message} to {target_plugin_name}")
        self.send_message_to_frontend(message, target_plugin_name)

    async def send_status(self, status):
        # Send a JSON message where status=ready
        message = json.dumps({"status": status})
        
        success = await self.wait_for_socket_and_send(message)
        return success
    
    async def send_switch_view_to_app(self,view):
        self.logger.info(f"Switching view to {view}")
        await self.send_message_to_app({"switchview":view})
        
    async def send_message_to_app(self, message):
        """
        Wrapper that sends a message to the Vue app

        :param message: The message to be sent.
        """
        success = await self.wait_for_socket_and_send(message, 'app')
        return success
    
    def handle_llm_error(self, llm_response):
        """
        Common handler for LLM errors across all plugins.
        Returns (is_error: bool, response: Any)
        """
        is_error, error_info = LLMManager.is_error_response(llm_response)
        if is_error:
            if error_info["type"] == "RateLimitError":
                self.logger.error(f"Rate limit reached. Please wait {error_info['wait_time']} seconds before trying again.")
                self.send_error_to_frontend(
                    error_code="rate_limit",
                    error=error_info
                )
            else:
                self.logger.error(f"LLM error: {error_info['message']}")
                self.send_error_to_frontend(
                    error_code="llm_error",
                    error=error_info["message"]
                )
            return True, llm_response
        return False, llm_response
    
    def send_rate_limit_error_to_frontend(self):
        self.send_error_to_frontend('rate_limit')
    
    def send_error_to_frontend(self,error_code,error="",plugin_name=None): 
        target_plugin_name = plugin_name or self.plugin_name
        """
        Wrapper that sends an error message to the frontend.

        :param error: The error message or exception to be sent
        :param error_code: A specific code to identify the type of error (e.g., 'llm_error', 'file_not_found', etc.)
        :param plugin_name: (Optional) The plugin name to send the message to. If not provided, uses self.plugin_name
        """
        # Get the string representation of the error for user display
        error_message = str(error)
        
        # If it's an exception, get the full traceback
        if isinstance(error, Exception):
            import traceback
            detailed_error = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            detailed_error = error_message
        
        # Create error payload
        error_data = {
            "type": "error",
            "error_code": error_code,
            "message": error_message,     # User-friendly message
            "details": detailed_error     # Complete error information
        }
        
        # Send using existing message sending method
        self.send_message_to_frontend(error_data, target_plugin_name)
            
    def send_message_to_frontend(self, message, plugin_name=None):
        """
        Sends a message to the designated plugin's frontend channel with retry mechanism.
        
        :param message: The message to be sent.
        :param plugin_name: (Optional) The plugin name to send the message to. If not provided, uses self.plugin_name.
        """
        import time
        
        # Use the provided plugin_name or default to self.plugin_name
        target_plugin_name = plugin_name or self.plugin_name
        
        # Retry configuration
        max_retries = 5
        retry_delay = 1  # seconds
        
        # Ensure the message is a JSON string
        if isinstance(message, dict):
            message = json.dumps(message)
            
        # Attempt to send the message with retries
        for attempt in range(max_retries + 1):
            if websocket_server.is_socket_open(target_plugin_name):
                try:
                    return websocket_server.send_message(target_plugin_name, message)
                except Exception as e:
                    if attempt < max_retries:
                        self.logger.warning(f"Failed to send message to {target_plugin_name} frontend (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        time.sleep(retry_delay)
                    else:
                        self.logger.error(f"Error while sending message to {target_plugin_name} frontend after {max_retries + 1} attempts: {e}")
                        return False
            else:
                if attempt < max_retries:
                    self.logger.warning(f"{target_plugin_name} frontend is not ready (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"{target_plugin_name} frontend is not ready after {max_retries + 1} attempts")
                    return False
        
        return False
    
    def send_action_to_frontend(self, action, plugin_name=None):
        target_plugin_name = plugin_name or self.plugin_name
        self.send_message_to_frontend(action, target_plugin_name)
    
    def send_settings_to_frontend(self):
        settings = self.get_my_settings()
        self.send_message_to_frontend({
            "type": "settings",
            "settings": settings
        })
            
    def process_incoming_message(self, message):
        try:
            message_dict = json.loads(message)
            if message_dict.get('action') == 'get_settings':
                self.send_settings_to_frontend()
                return
            
            if message_dict.get('action') == 'save_settings':
                settings_payload = message_dict.get('settings')
                if isinstance(settings_payload, dict):
                    # Remove 'action' key from the settings_payload if it exists
                    settings_payload.pop('action', None)
                self.mass_update_settings(settings_payload)
                return
                
            print(f"Default processing message for {self.plugin_name}: {message}")
                
        except json.JSONDecodeError:
            self.logger.error("Received message is not valid JSON.")
            return
            
        # Check if the message is {"socket":"ready"}
        # if message_dict == {"socket": "ready"}:
        #    self.socket_ready = True
        
    def _load_plugin_metadata(self):
        """Load plugin.json metadata"""
        try:
            plugin_json_path = resource_path(os.path.join('plugins', self.plugin_name, 'plugin.json'))
            with open(plugin_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading plugin metadata: {e}")
            return {}
    
    def _init_database(self):
        """Initialize database connection for this plugin"""
        try:
            if not self._plugin_metadata.get('requires_db', False):
                return
                
            db_tables = self._plugin_metadata.get('db_tables', {})
            if not db_tables:
                self.logger.warning(f"Plugin {self.plugin_name} requires database but no tables defined")
                return
                
            self.logger.info(f"Initializing database for plugin {self.plugin_name}")
            db_manager = DatabaseManager()
            db_manager.register_plugin(self.plugin_name, db_tables)
            self._db = db_manager
            self.logger.info(f"Database initialized for plugin {self.plugin_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            self._db = None
    
    @property
    def db(self):
        """Access database connection if available"""
        if self._db is None and self._plugin_metadata.get('requires_db', False):
            self._init_database()
        return self._db
    
    async def db_execute(self, query: str, params: tuple = ()):
        """Execute a database query asynchronously"""
        if self.db is None:
            self.logger.error("Database not initialized")
            return None
            
        return await self.db.execute(self.plugin_name, query, params)
        
    def db_execute_sync(self, query: str, params: tuple = ()):
        """Execute a database query synchronously"""
        if self.db is None:
            self.logger.error("Database not initialized")
            return None
            
        return self.db.execute_sync(self.plugin_name, query, params)

    def debug_db_status(self):
        """Debug method to check database status"""
        if self._db is None:
            self.logger.error("Database is not initialized!")
            return False
            
        if not self._plugin_metadata.get('requires_db', False):
            self.logger.error("Plugin metadata does not have requires_db=true!")
            return False
            
        tables = self._plugin_metadata.get('db_tables', {})
        if not tables:
            self.logger.error("No tables defined in plugin metadata!")
            return False
            
        self.logger.info(f"Database initialized: {self._db is not None}")
        self.logger.info(f"Plugin requires DB: {self._plugin_metadata.get('requires_db', False)}")
        self.logger.info(f"Tables defined: {list(tables.keys())}")
        return True

    # ── Translation helpers ────────────────────────────────────────────────────

    def _load_translation_prompt(self):
        """Load translation prompt from translator plugin's prompts.yaml"""
        import yaml
        try:
            prompts_path = resource_path(os.path.join('plugins', 'translator', 'prompts.yaml'))
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)
            return prompts.get('translate', {})
        except Exception as e:
            self.logger.warning(f"Could not load translation prompts, using defaults: {e}")
            return {
                "system": "You are a translator. Translate the following text from {source_language} to {target_language}.\nRULES:\n- Output ONLY the translated text.\n- No quotes, no explanation, no extra text.\n- PRESERVE THE REGISTER: Match the formality level of the source in the target language.\n- Keep it natural and colloquial.\n{conversation_context}"
            }

    def _translate_text_sync(self, text, target_language, source_language=""):
        """Translate *text* to *target_language* via LLM.
        Synchronous — meant to be called via asyncio.to_thread().
        Always returns a string: the translation on success, the original on failure.
        """
        from context_manager import context_manager
        try:
            sm = self.settings_manager
            ai = sm.get_nested(["plugins", "onboarding", "ai"], default={})
            translator_settings = sm.get_plugin_settings("translator")
            # Allow a dedicated fast model for translation (no reasoning needed)
            model_name = translator_settings.get("translation_model_name") or ai.get("model_name")

            llm = LLMManager(
                ai.get("provider"),
                ai.get("api_key"),
                model_name,
                temperature=0,
            )

            # Include conversation for context-aware translation
            conversation = context_manager.get_context().get("conversation", "")
            conversation_ctx = ""
            if conversation:
                conversation_ctx = (
                    "\n\nConversation context (for reference only — do NOT translate "
                    "this, use it only to understand context and tone):\n" + conversation
                )

            # Get user bio for gender-aware translation
            bio = sm.get_bio()
            bio_name = bio.get("name", "the user")
            health_state = bio.get("health_state", "")
            health_ctx = f"Health context: {health_state}" if health_state else ""

            # Load prompt from translator plugin's prompts.yaml
            prompt_template = self._load_translation_prompt()
            system_prompt = prompt_template.get("system", "").format(
                target_language=target_language,
                source_language=source_language,
                conversation_context=conversation_ctx,
                bio_name=bio_name,
                health_state=health_ctx
            )

            result = llm.invoke(system_prompt, text)
            translated = result.content if hasattr(result, "content") else str(result)
            return translated.strip() if translated else text
        except Exception as e:
            self.logger.error(f"Translation failed, using original text: {e}")
            return text

    async def translate_for_interlocutor(self, text, direction="outgoing"):
        """Translate *text* if the translator plugin is active and configured.

        direction:
            'outgoing' — patient's language → interlocutor's language (pre-TTS)
            'incoming' — interlocutor's language → patient's language (post-ASR)

        Returns the original text immediately (zero cost) when:
        - translator plugin is not activated / not configured
        - the relevant toggle (translate_incoming / translate_outgoing) is off
        - translation fails (fail-safe)
        """
        sm = self.settings_manager
        translator_settings = sm.get_plugin_settings("translator")
        self.logger.info(f"[TRANSLATE] direction={direction}, settings={translator_settings}")

        if not text or not text.strip():
            return text

        target_lang = translator_settings.get("interlocutor_language", "")
        if not target_lang:
            self.logger.info(f"[TRANSLATE] No interlocutor_language set, returning original text")
            return text  # Plugin inactive or not configured — immediate return

        toggle_key = "translate_outgoing" if direction == "outgoing" else "translate_incoming"
        if not translator_settings.get(toggle_key, False):
            self.logger.info(f"[TRANSLATE] {toggle_key} is False, returning original text")
            return text

        # Determine which language to translate into
        if direction == "incoming":
            target_language = sm.get_reply_language()  # patient's language e.g. "Italian"
            source_language = target_lang              # interlocutor's language e.g. "French"
        else:
            target_language = target_lang              # interlocutor's language e.g. "French"
            source_language = sm.get_reply_language()  # patient's language e.g. "Italian"

        self.logger.info(f"[TRANSLATE] Translating from {source_language} to {target_language}: {text}")
        return await asyncio.to_thread(self._translate_text_sync, text, target_language, source_language)
