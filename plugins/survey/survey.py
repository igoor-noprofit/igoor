from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from fastapi import APIRouter, Body
from pydantic import BaseModel
import asyncio
import json
import httpx
from datetime import datetime, timedelta

class UserActionRequest(BaseModel):
    action: str

class Survey(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.router = None
        self._timer_task = None

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/survey", tags=["survey"])

        @self.router.post("/trigger_modal")
        async def trigger_modal():
            """Manually trigger survey modal for testing purposes (bypasses all condition checks)"""
            self.logger.info("Manual trigger of survey modal via API endpoint")
            await self._show_survey_modal()
            return {"status": "modal_triggered"}

        @self.router.post("/user_action")
        async def user_action(request: UserActionRequest):
            """Handle user actions from frontend (remind_in_5, remind_later, already_filled)"""
            action = request.action
            self.logger.info(f"User action via API: {action}")

            if action == "remind_in_5":
                self._handle_remind_in_5_minutes()
                return {"status": "remind_in_5_minutes_set"}

            elif action == "remind_later":
                self._handle_remind_later()
                return {"status": "remind_later_set"}

            elif action == "already_filled":
                self._handle_has_filled()
                return {"status": "marked_as_filled"}

            else:
                return {"error": "Unknown action", "status": "error"}

    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)

    @hookimpl
    async def after_conversation_end(self, last_conversation):
        """Check if survey reminder should be shown after conversation ends"""
        settings = self.get_my_settings()

        # Skip if already filled
        if settings.get("has_filled", False):
            self.logger.info("User has already filled the survey, skipping reminder")
            return

        # Check language (only French)
        onboarding_settings = self.settings_manager.get_plugin_settings("onboarding")
        lang = onboarding_settings.get("prefs", {}).get("lang", "fr_FR")
        if lang != "fr_FR":
            self.logger.info(f"Language is {lang}, not French, skipping survey reminder")
            return

        # Check if enough time has passed since last_reminded (minimum min_interval hours)
        last_reminded = settings.get("last_reminded")
        min_interval = settings.get("min_interval", 12)  # Default 12 hours
        if last_reminded:
            try:
                last_reminded_time = datetime.fromisoformat(last_reminded.replace('Z', '+00:00'))
                hours_since_reminder = (datetime.now() - last_reminded_time).total_seconds() / 3600
                if hours_since_reminder < min_interval:
                    self.logger.info(f"Survey reminded {hours_since_reminder:.1f} hours ago, skipping (min {min_interval} hours)")
                    return
            except Exception as e:
                self.logger.error(f"Error parsing last_reminded timestamp: {e}")

        # Get conversations via API endpoint
        min_conversations = settings.get("min_conversations", 20)
        conversations = await self._get_conversations(
            order_by="start_time ASC",
            limit=min_conversations
        )

        if not conversations:
            self.logger.info("No conversations found, skipping survey reminder")
            return

        # Check conditions: count > min_conversations OR first conversation > min_days old
        min_days = settings.get("min_days", 15)
        should_show = (
            len(conversations) > min_conversations or
            self._is_older_than_days(conversations[0]["start_time"], min_days)
        )

        if should_show:
            self.logger.info("Conditions met, showing survey reminder modal")
            await self._show_survey_modal()
        else:
            self.logger.info(f"Survey conditions not met: {len(conversations)} conversations, first conversation age: {self._get_days_old(conversations[0]['start_time'])} days")

    async def _get_conversations(self, order_by="start_time ASC", limit=20):
        """Get conversations from conversation plugin via FastAPI endpoint"""
        try:
            # Use HTTP client to call conversation plugin's FastAPI endpoint
            async with httpx.AsyncClient() as client:
                url = "http://localhost:9714/api/plugins/conversation/get_conversations"
                params = {"order_by": order_by, "limit": limit}
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    conversations = response.json()
                    self.logger.info(f"Retrieved {len(conversations)} conversations via HTTP API")
                    return conversations
                else:
                    self.logger.error(f"Failed to get conversations: HTTP {response.status_code}")
                    return []
        except Exception as e:
            self.logger.error(f"Error getting conversations via HTTP API: {e}")
            return []

    def _is_older_than_days(self, timestamp_str, days):
        """Check if a timestamp is older than specified days"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            days_old = (datetime.now() - timestamp).days
            return days_old >= days
        except Exception as e:
            self.logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
            return False

    def _get_days_old(self, timestamp_str):
        """Get how many days old a timestamp is"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return (datetime.now() - timestamp).days
        except Exception as e:
            self.logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
            return 0

    async def _show_survey_modal(self):
        """Show the survey reminder modal"""
        self.logger.info("Showing survey modal to user")

        # Send action to frontend to show modal
        self.send_message_to_frontend({"action": "show_survey_modal"})

    def process_incoming_message(self, message):
        """Handle messages from frontend"""
        try:
            if isinstance(message, str):
                message = json.loads(message)

            action = message.get('action')

            if action == 'remind_in_5_minutes':
                self._handle_remind_in_5_minutes()

            elif action == 'remind_later':
                self._handle_remind_later()

            elif action == 'has_filled':
                self._handle_has_filled()

        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _handle_remind_in_5_minutes(self):
        """Handle 'remind in 5 minutes' action"""
        self.logger.info("User requested reminder in 5 minutes")
        
        # Update last_reminded
        self.update_my_settings("last_reminded", datetime.now().isoformat())
        
        # Close modal
        self.send_message_to_frontend({"action": "close_survey_modal"})
        
        # Start 5-minute timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        self._timer_task = asyncio.create_task(self._remind_after_delay(minutes=5))
        self.logger.info("Started 5-minute reminder timer")

    def _handle_remind_later(self):
        """Handle 'remind later' action"""
        self.logger.info("User requested reminder later")
        
        # Update last_reminded
        self.update_my_settings("last_reminded", datetime.now().isoformat())
        
        # Cancel any existing timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        # Close modal
        self.send_message_to_frontend({"action": "close_survey_modal"})

    def _handle_has_filled(self):
        """Handle 'has filled' action"""
        self.logger.info("User has filled the survey")
        
        # Set has_filled to true
        self.update_my_settings("has_filled", True)
        
        # Cancel any existing timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        # Close modal
        self.send_message_to_frontend({"action": "close_survey_modal"})

    async def _remind_after_delay(self, minutes):
        """Remind user after specified delay"""
        try:
            await asyncio.sleep(minutes * 60)  # Convert minutes to seconds
            self.logger.info(f"Reminder timer triggered after {minutes} minutes")
            await self._show_survey_modal()
        except asyncio.CancelledError:
            self.logger.info("Reminder timer was cancelled")
        except Exception as e:
            self.logger.error(f"Error in reminder timer: {e}")
