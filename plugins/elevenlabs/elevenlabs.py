from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
import threading
from elevenlabs import ElevenLabs, VoiceSettings, play
from typing import Any, Dict
from settings_manager import SettingsManager
import asyncio
import json
from fastapi import APIRouter, HTTPException

class Elevenlabs(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        super().__init__(plugin_name,pm)
                
    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/elevenlabs", tags=["elevenlabs"])

        # Debug endpoints for development/testing
        @self.router.get("/get_voices")
        async def get_voices(api_key: str):
            """Get list of available voices for an API key"""
            try:
                user = User(api_key)
                # Try different method names for ElevenLabs API
                try:
                    voices = user.get_all_voices()
                except AttributeError:
                    try:
                        voices = user.get_voices()
                    except AttributeError:
                        try:
                            voices = user.get_voice_list()
                        except AttributeError:
                            # Get user subscription data as fallback
                            subscription_data = user.get_subscription_data()
                            print(f"DEBUG: Available subscription data: {subscription_data}")
                            return {
                                "voices": [],
                                "count": 0,
                                "debug_info": {
                                    "subscription_data": subscription_data,
                                "available_methods": [attr for attr in dir(user) if 'voice' in attr.lower()]
                            }
                        }
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
                client = elevenlabs.ElevenLabs(api_key=api_key)
                voices = client.voices.get_all()
                
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
                api_key = payload.get("api_key")
                voice_id = payload.get("voice_id")
                message = payload.get("message", "Hello, how are you doing? I feel better today!")
                
                if not api_key or not voice_id:
                    raise HTTPException(status_code=400, detail="api_key and voice_id are required")
                
                client = elevenlabs.ElevenLabs(api_key=api_key)
                voice = client.voices.get(voice_id)
                
                from elevenlabs import play
                from elevenlabslib import GenerationOptions, PlaybackOptions
                
                # Build generation options with current plugin settings
                voice_settings = elevenlabs.VoiceSettings(
                    model=self.settings.get("model_id", "eleven_multilingual_v2"),
                    stability=self.settings.get("stability", 0.5),
                    similarity_boost=self.settings.get("similarity_boost", 0.75),
                    style=self.settings.get("style", 0.0),
                    use_speaker_boost=self.settings.get("use_speaker_boost", True),
                    speed=self.settings.get("speed", 1.0)
                )
                
                # Generate and play audio
                audio_future = voice.generate(text=message, voice=voice_settings)
                generation_info = generation_info_future.result()
                audio_data = audio_future.result()
                play(audio_data)
                
                return {
                    "status": "success",
                    "generation_info": {
                        "model_id": generation_info.get("model_id"),
                        "text": generation_info.get("text"),
                        "voice_id": generation_info.get("voice_id")
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to test voice: {str(e)}")
                
    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
                
    @hookimpl
    def register_fastapi_routes(self):
        """Register plugin routes with FastAPI app"""
        self._ensure_router()
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        self.settings = self.get_my_settings()
        print ("ELEVENLABS settings", self.settings)
        
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
            self.user = User(self.settings.get("api_key"))
            self.voice= self.user.get_voice_by_ID(self.settings.get("voice_id"))   
            self.is_loaded = True
            # self.input_streamer=ReusableInputStreamer(self.voice)
        except Exception as e:
            print(f"Error occurred while setting user : {e}")
            # DEFAULT SYSTEMATICALLY TO TTSDEFAULT
            return False
    
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
            temp_user = User(api_key)
            voices = temp_user.get_voices()
            
            voice_list = []
            for voice in voices:
                voice_data = {
                    "id": voice.voice_id,
                    "display_name": voice.name,
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
                
            temp_user = User(api_key)
            test_voice = temp_user.get_voice_by_ID(test_settings.get("voice_id"))
            
            # Build generation options from test settings
            generation_options = GenerationOptions(
                model_id=test_settings.get("model_id", self.settings.get("model_id", "eleven_multilingual_v2")),
                latencyOptimizationLevel=test_settings.get("latency_optimization", self.settings.get("latency_optimization", 0)),
                stability=test_settings.get("stability", self.settings.get("stability", 0.5)),
                similarity_boost=test_settings.get("similarity_boost", self.settings.get("similarity_boost", 0.75)),
                style=test_settings.get("style", self.settings.get("style", 0.0)),
                use_speaker_boost=test_settings.get("use_speaker_boost", self.settings.get("use_speaker_boost", True)),
                speed=test_settings.get("speed", self.settings.get("speed", 1.0))
            )
            
            playback_options = PlaybackOptions(
                runInBackground=False
            )
            
            # Generate and play audio
            audio_future, generation_info_future = test_voice.generate_audio_v3(message, generation_options)
            generation_info = generation_info_future.result()
            audio_data = audio_future.result()
            
            play_audio_v2(audio_data)
            
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
            # Set generation options from user settings
            playback_options = PlaybackOptions(
                runInBackground=False,
                onPlaybackEnd=self.run_restart_asr
            )
            generation_options = GenerationOptions(
                model_id=self.settings.get("model_id", "eleven_multilingual_v2"),
                latencyOptimizationLevel=self.settings.get("latency_optimization", 0),
                stability=self.settings.get("stability", 0.5),
                similarity_boost=self.settings.get("similarity_boost", 0.75),
                style=self.settings.get("style", 0.0),
                use_speaker_boost=self.settings.get("use_speaker_boost", True),
                speed=self.settings.get("speed", 1.0)
            )
            # websocket_options = WebsocketOptions(chunk_length_schedule=[125],try_trigger_generation=False)
            # Check if stream_audio_v3 is async
            # result = self.voice.stream_audio_v3(message, playback_options=playback_options, generation_options=generation_options, websocket_options=websocket_options)
            try:
                audio_future, generation_info_future = self.voice.generate_audio_v3(message, generation_options)
                generation_info = generation_info_future.result()
                audio_data = audio_future.result()
            except Exception as inner_e:
                print(f"Error retrieving audio data: {inner_e}")
                await self.call_fallback(message=message) 
                return False    
            # Play it back
            await self.pm.trigger_hook(hook_name="pause_asr")
            play_audio_v2(audio_data)
            self.run_restart_asr()
            return True

        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            await self.call_fallback(message=message) 
            return False
        
    async def call_fallback(self,message):
        await self.pm.trigger_hook(hook_name="speak_fallback",message=message) 