from plugin_manager import hookimpl 
from plugins.baseplugin.baseplugin import Baseplugin
from context_manager import context_manager
from datetime import datetime
import locale
import os, shutil
from dotenv import load_dotenv
load_dotenv()
import asyncio,json
from fastapi import APIRouter
from fastapi.responses import FileResponse

# Create router for shortcuts plugin endpoints
router = APIRouter(prefix="/plugins/shortcuts")

@router.get("/alerte.wav")
async def get_alert_sound():
    """Serve the alerte.wav audio file"""
    try:
        # Get path to the copied alerte.wav file
        appdata_path = os.getenv('APPDATA')
        app_name = __import__('version').__appname__
        alert_file_path = os.path.join(appdata_path, app_name, 'web', 'alerte.wav')
        
        if os.path.exists(alert_file_path):
            return FileResponse(alert_file_path, media_type="audio/wav")
        else:
            # Try fallback to original plugin location
            from utils import resource_path
            fallback_path = resource_path('plugins/shortcuts/alerte.wav')
            if os.path.exists(fallback_path):
                return FileResponse(fallback_path, media_type="audio/wav")
            return {"error": "Alert sound file not found"}, 404
    except ConnectionResetError:
        # Browser closed connection after buffering audio - normal behavior, ignore
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}, 500

class Shortcuts(Baseplugin):    
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.is_loaded = True
        self.is_onboarding_on = False
        self._ensure_usage_schema()
        
        # Load alert settings
        self.help_mode = self.get_my_settings().get('help_mode', 'speak')
        self.alert_repetitions = self.get_my_settings().get('alert_repetitions', 3)
        self.alert_interval = self.get_my_settings().get('alert_interval', 15)
        
        # Assign router to instance
        self.router = router
        
    @hookimpl
    def startup(self):
        print("STARTUP")
        self._copy_alert_sound()
        # Register router with main FastAPI app if available
        if hasattr(self.pm, 'fastapi_app') and self.pm.fastapi_app:
            self.pm.fastapi_app.include_router(self.router)
            self.logger.info("Registered shortcuts API routes")
            self.mark_ready()
        else:
            self.logger.warning("FastAPI app not available; shortcuts endpoints not registered")
        
    @hookimpl
    def abandon_conversation(self):
        self._stop_alert()
        
    @hookimpl
    def after_conversation_end(self):
        self._stop_alert()
        
    @hookimpl
    def new_conversation(self):
        self._stop_alert()
        
    def _stop_alert(self):
        """Send stop alert command to frontend"""
        self.send_message_to_frontend({
            "action": "stop_alert"
        })
        
    def _copy_alert_sound(self):
        """Copy alerte.wav to /web folder for direct frontend access"""
        try:
            # Source file in plugin folder
            source_path = os.path.join(self._app_plugin_folder, 'alerte.wav')
            
            # Get APPDATA path and construct /web folder path
            appdata_path = os.getenv('APPDATA')
            app_name = __import__('version').__appname__
            web_folder = os.path.join(appdata_path, app_name, 'web')
            
            # Debug logging
            self.logger.info(f"Copying alert sound from: {source_path}")
            self.logger.info(f"To: {web_folder}")
            self.logger.info(f"Source exists: {os.path.exists(source_path)}")
            
            # Ensure /web folder exists
            if not os.path.exists(web_folder):
                self.logger.info(f"Creating /web folder at {web_folder}")
                os.makedirs(web_folder)
            
            # Destination path
            dest_path = os.path.join(web_folder, 'alerte.wav')
            
            # Copy file if source exists
            if os.path.exists(source_path):
                shutil.copy2(source_path, dest_path)
                self.logger.info(f"Successfully copied alerte.wav to {dest_path}")
                self.logger.info(f"Destination exists after copy: {os.path.exists(dest_path)}")
            else:
                self.logger.warning(f"Source alerte.wav not found at {source_path}")
        except Exception as e:
            self.logger.error(f"Error copying alerte.wav to /web folder: {e}")

    @hookimpl
    def onboarding_toggled(self,is_onboarding):
        if is_onboarding:
            action={"action": "shrink"}
            self.is_onboarding_on = True
        else:
            action={"action": "unshrink"}
            self.is_onboarding_on = False
        self.send_message_to_frontend(action)

        
    def process_incoming_message(self, message):
        try:
            print("Received msg: " + message)
            # Attempt to parse the message as JSON
            message_dict = json.loads(message)
            # Output the JSON variables and values
            for key, value in message_dict.items():
                print(f"Key: {key}, Value: {value}")
            # Ensure message_dict is a dictionary
            if isinstance(message_dict, dict):
                action = message_dict.get("action")
                if action == "speak":
                    msg = message_dict.get("msg")
                    bid = message_dict.get("bid")
                    print (f"Speaking {msg}")
                    if msg:
                        asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
                        onboarding_flag = 1 if self.is_onboarding_on else 0
                        if bid is None:
                            self.logger.warning("Shortcut speak action missing bid; defaulting to -1")
                            bid_value = -1
                        else:
                            try:
                                bid_value = int(bid)
                            except (TypeError, ValueError):
                                self.logger.warning(f"Invalid bid value '{bid}' received; defaulting to -1")
                                bid_value = -1
                        timestamp = datetime.utcnow().isoformat()
                        try:
                            if self.db is None:
                                self.logger.error("Database not initialized; cannot store shortcut usage")
                            else:
                                self.db_execute_sync(
                                    "INSERT INTO usage (msg, datetime, onboarding, bid) VALUES (?, ?, ?, ?)",
                                    (msg, timestamp, onboarding_flag, bid_value)
                                )
                        except Exception as exc:
                            self.logger.error(f"Failed to store shortcut usage: {exc}")
                        # asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master",msg_input="shortcuts"))
                    else:
                        print("Speak action is present but msg is empty.")
                        
                # Handle help button specially based on settings
                if action == "help":
                    self.logger.info(f"Help button pressed, mode: {self.help_mode}")
                    if self.help_mode == "speak":
                        # Log to database
                        help_msg = "Please help me, it's urgent!"
                        onboarding_flag = 1 if self.is_onboarding_on else 0
                        timestamp = datetime.utcnow().isoformat()
                        try:
                            if self.db is not None:
                                self.db_execute_sync(
                                    "INSERT INTO usage (msg, datetime, onboarding, bid) VALUES (?, ?, ?, ?)",
                                    (help_msg, timestamp, onboarding_flag, 6)  # 6 is help button index
                                )
                        except Exception as exc:
                            self.logger.error(f"Failed to store help usage: {exc}")
                        # Send alert playback command to frontend for repeated speaking
                        self.send_message_to_frontend({
                            "action": "play_alert_speak",
                            "repetitions": self.alert_repetitions,
                            "interval": self.alert_interval
                        })
                    elif self.help_mode == "sound":
                        # Send alert playback command to frontend
                        self.send_message_to_frontend({
                            "action": "play_alert",
                            "repetitions": self.alert_repetitions,
                            "interval": self.alert_interval
                        })
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return

    def _reload_alert_settings(self):
        """Reload alert settings from disk and update instance variables"""
        settings = self.get_my_settings()
        self.help_mode = settings.get('help_mode', 'speak')
        self.alert_repetitions = settings.get('alert_repetitions', 3)
        self.alert_interval = settings.get('alert_interval', 15)
        self.logger.info(f"Reloaded alert settings: help_mode={self.help_mode}, repetitions={self.alert_repetitions}, interval={self.alert_interval}")
    
    @hookimpl
    def global_settings_updated(self):
        """Handle global settings updated hook to reload alert settings"""
        self._reload_alert_settings()

    def _ensure_usage_schema(self):
        if self.db is None:
            self.logger.warning("Database not initialized when ensuring usage schema")
            return
        table_name = f"{self.plugin_name}_usage"
        try:
            columns = self.db_execute_sync(f"PRAGMA table_info({table_name})") or []
            column_names = {column.get('name') for column in columns if isinstance(column, dict)}
            if "bid" not in column_names:
                self.logger.info("Adding bid column to shortcuts usage table")
                self.db_execute_sync(f"ALTER TABLE {table_name} ADD COLUMN bid INTEGER DEFAULT 0")
                self.db_execute_sync(f"UPDATE {table_name} SET bid = 0 WHERE bid IS NULL")
        except Exception as exc:
            self.logger.error(f"Failed to ensure shortcuts usage schema: {exc}")