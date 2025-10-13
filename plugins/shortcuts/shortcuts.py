from plugin_manager import hookimpl 
from plugins.baseplugin.baseplugin import Baseplugin
from context_manager import context_manager
from datetime import datetime
import locale
from dotenv import load_dotenv
load_dotenv()
import asyncio,json

class Shortcuts(Baseplugin):    
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.is_loaded = True
        self.is_onboarding_on = False
        self._ensure_usage_schema()
        
    @hookimpl
    def startup(self):
        print("STARTUP")
        
    
    @hookimpl
    def onboarding_toggled(self,is_onboarding):
        if is_onboarding:
            action="shrink"
            self.is_onboarding_on = True
        else:
            action="unshrink"
            self.is_onboarding_on = False
        self.send_action_to_frontend(action)

        
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
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return

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
