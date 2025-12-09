from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
import threading
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from typing import Any, Dict
from settings_manager import SettingsManager
import asyncio
import json
from fastapi import APIRouter, HTTPException

class Elevenlabstts(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        super().__init__(plugin_name,pm)
                
    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/elevenlabstts", tags=["elevenlabstts"])

        # Debug endpoints for development/testing
        @self.router.get("/get_voices")
        async def get_voices(api_key: str):
            """Get list of available voices for an API key"""
            try:
                client = self.createClient(api_key)
                # Use the correct ElevenLabs API syntax
                response = client.voices.get_all()
                voices = response.voices
                
                print(f"DEBUG: Total voices retrieved: {len(voices) if voices else 0}")
                voice_list = []
                for voice in voices:
                    # Debug the voice object structure
                    print(f"DEBUG: Voice object attributes: {[attr for attr in dir(voice) if not attr.startswith('_')]}")
                    voice_data = {
                        "id": getattr(voice, 'voice_id', getattr(voice, 'id', 'unknown')),
                        "display_name": getattr(voice, 'name', str(voice)),
                        "gender": getattr(voice, 'gender', 'unknown'),
                        "age": getattr(voice, 'age', 'unknown'),
                        "language": getattr(voice, 'language', 'unknown')
                    }
                    voice_list.append(voice_data)
                return {"voices": voice_list, "count": len(voice_list)}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to get voices: {str(e)}")

        @self.router.get("/debug_voice")
        async def debug_single_voice(api_key: str, voice_name: str = "Rachel"):
            """Debug endpoint to inspect single voice object"""
            try:
                client = self.createClient(api_key)
                response = client.voices.get_all()
                voices = response.voices
                
                # Find specific voice
                target_voice = None
                for voice in voices:
                    if hasattr(voice, 'name') and voice.name == voice_name:
                        target_voice = voice
                        break
                
                if target_voice is None:
                    return {"error": f"Voice '{voice_name}' not found"}
                
                # Return detailed info about the voice object
                return {
                    "voice_name": getattr(target_voice, 'name', 'No name'),
                    "voice_id": getattr(target_voice, 'voice_id', getattr(target_voice, 'id', 'No id')),
                    "all_attributes": {attr: str(getattr(target_voice, attr)) for attr in dir(target_voice) if not attr.startswith('_')},
                    "available_methods": [attr for attr in dir(client) if 'voice' in attr.lower()],
                    "user_methods": [attr for attr in dir(client) if not attr.startswith('_')],
                    "subscription_data": client.get_subscription_data()
                }
            except Exception as e:
                return {"error": str(e)}

        @self.router.post("/test_speak")
        async def test_speak(payload: dict):
            """Test a voice with provided settings"""
            try:
                print(f"DEBUG: test_speak called with payload: {payload}")
                
                api_key = payload.get("api_key")
                voice_id = payload.get("voice_id")
                message = payload.get("message", "Hello, how are you doing? I feel better today!")
                
                if not api_key or not voice_id:
                    raise HTTPException(status_code=400, detail="api_key and voice_id are required")
                
                client = self.createClient(api_key)
                
                audio = client.text_to_speech.convert(
                    text=message,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )

                play(audio)
                
                return {
                    "status": "success",
                    "message": "Audio generated successfully"
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to test voice: {str(e)}")
                
    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        self.settings = self.get_my_settings()
        try:
            self.api_key = self.settings.get("api_key")
            self.voice_id = self.settings.get("voice_id")  
            if (not self.api_key):
                self.logger.warning("Speechify API token not set in settings,cannot generate speech")
                return False
            if (not self.voice_id):
                print("Speechify Voice ID not set in settings,cannot generate speech")
                return False
            try:
                self.client = self.createClient(self.api_key)
                self.is_loaded = True
                return True
            except Exception as e:
                self.logger.error(f"Error occurred while creating Elevenlabs client : {e}")
                return False    
        except Exception as e:
            self.logger.error(f"Error occurred while retrieving settings : {e}")
            return False
    
    def createClient(self,ak):
        try: 
            return ElevenLabs(api_key=ak)
        except Exception as e:
            self.logger.error(f"Error occurred while creating Elevenlabs client : {e}")
            return False
    
    '''
    @hookimpl
    def register_fastapi_routes(self):
        """Register plugin routes with FastAPI app"""
        self._ensure_router()
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        self.settings = self.get_my_settings()
        print ("ELEVENLABSTTS settings", self.settings)
        
        # Set default values for new settings if they don't exist
        default_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": 1.0,
            "latency_optimization": 0,
            "model_id": "eleven_multilingual_v2"
        }
        
        for key, default_value in default_settings.items():
            if key not in self.settings:
                self.settings[key] = default_value
        
        try:
            # Initialize settings first
            self.settings = self.get_my_settings()
            
            self.client = self.createClient()
            # Voice object is not needed with new API, just store voice_id
            self.voice_id = self.settings.get("voice_id")
            self.is_loaded = True
            # self.input_streamer=ReusableInputStreamer(self.voice)
        except Exception as e:
            print(f"Error occurred while setting user : {e}")
            # DEFAULT SYSTEMATICALLY TO TTSDEFAULT
            return False
    '''
    
    @hookimpl
    def on_websocket_message(self, message):
        """Handle websocket messages from the frontend settings UI"""
        try:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "get_voice_list":
                api_key = data.get("api_key")
                if api_key:
                    self._get_voice_list(api_key)
                    
            elif action == "test_speak":
                test_message = data.get("message", "Hello, how are you doing? I feel better today!")
                # Use current settings for test
                self._test_speak(test_message, data)
                
        except Exception as e:
            print(f"Error handling websocket message: {e}")
            self.send_error_to_frontend(str(e))
    
    def _get_voice_list(self, api_key):
        """Retrieve and send voice list to frontend"""
        try:
            client = self.createClient(api_key)
            response = client.voices.get_all()
            voices = response.voices
            print (response.voices)
            voice_list = []
            for voice in voices:
                voice_data = {
                    "id": getattr(voice, 'voice_id', getattr(voice, 'id', 'unknown')),
                    "display_name": getattr(voice, 'name', str(voice)),
                    "gender": getattr(voice, 'gender', 'unknown'),
                    "age": getattr(voice, 'age', 'unknown'),
                    "language": getattr(voice, 'language', 'unknown')
                }
                voice_list.append(voice_data)
            
            response = {
                "type": "voice_list",
                "voice_list": voice_list
            }
            self.send_message_to_frontend(json.dumps(response))
            
        except Exception as e:
            print(f"Error getting voice list: {e}")
            self.send_error_to_frontend(f"Failed to retrieve voice list: {str(e)}")
    
    def _test_speak(self, message, test_settings):
        """Test speak with provided settings"""
        try:
            # Create a temporary voice with test settings
            api_key = test_settings.get("api_key", self.settings.get("api_key"))
            if not api_key:
                self.send_error_to_frontend("API key is required for testing")
                return
                
            client = self.createClient(api_key)
            voice_id = test_settings.get("voice_id")
            
            # Generate and play audio using official SDK
            audio_data = client.text_to_speech.convert(
                text=message,
                voice_id=voice_id,
                model_id=test_settings.get("model_id", self.settings.get("model_id", "eleven_multilingual_v2"))
            )
            
            # Use the already imported elevenlabs_play function
            play(audio_data)
            
        except Exception as e:
            print(f"Error in test speak: {e}")
            self.send_error_to_frontend(f"Test failed: {str(e)}")
    

        
    @hookimpl
    def speak(self, message):
        print("§§§§ ELEVENLABS SPEAKING *********************************************** :", message)
        # Schedule the speak_func to run in the background
        asyncio.create_task(self.run_speak_func(message))
        asyncio.create_task(self.pm.trigger_hook(hook_name="reset_conversation_timeout"))

    def run_restart_asr(self):
        asyncio.create_task(self.restart_asr())
        
    async def restart_asr(self):
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def run_speak_func(self, message):
        success = await self.safe_speak_func(message)

    async def safe_speak_func(self, message):
        print("SAFE SPEAK FUNC:", message)
        try:
            result = await self.speak_func(message)
            print(f"RESULT OF SPEAK FUNC: {result}")
            if not result:
                print("Speak function encountered an issue but handled gracefully.")
                await self.call_fallback(message=message)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            await self.call_fallback(message=message)

    async def speak_func(self, message):
        print("SPEAK FUNC:" + message)
        try:
            # Ensure settings are initialized
            if not hasattr(self, 'settings'):
                self.settings = self.get_my_settings()
            
            try:
                # Generate audio using official SDK
                audio = self.client.text_to_speech.convert(
                    text=message,
                    voice_id=self.voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                await self.pm.trigger_hook(hook_name="pause_asr")
                play(audio)
            except Exception as inner_e:
                print(f"Error generating audio data: {inner_e}")
                await self.call_fallback(message=message) 
                return False    
            
            # Play it back
            await self.pm.trigger_hook(hook_name="pause_asr")
            self.run_restart_asr()
            return True

        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            await self.call_fallback(message=message) 
            return False
        
    async def call_fallback(self,message):
        await self.pm.trigger_hook(hook_name="speak_fallback",message=message) 