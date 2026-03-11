from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
import asyncio
import os
from speechify import Speechify
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.playback import play
import io
import base64
import json
'''
Language	Code
English	en
French	fr-FR
German	de-DE
Spanish	es-ES
Portuguese (Brazil)	pt-BR
Portuguese (Portugal)	pt-PT
'''

class Speechifytts(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self._ensure_lang_code()

    def _ensure_lang_code(self):
        lang = getattr(self, 'lang', None)
        if not lang:
            lang = 'en_EN'
        if lang == 'en_EN':
            code = 'en'
        else:
            code = lang.replace('_', '-')
        self.lang_code = code
        return code
                
    @hookimpl
    def startup(self):
        # https://docs.sws.speechify.com/docs/features/language-support#beta-languages
        self.supported_lang = ['en', 'fr-FR', 'de-DE', 'es-ES', 'pt-BR', 'pt-PT']
        self.settings = self.get_my_settings()
        ''' print ("SPEECHIFY settings", self.settings) '''
        try:
            self.api_key = self.settings.get("api_key")
            self.voice_id = self.settings.get("voice_id")  
            if (not self.api_key):
                self.logger.warning("Speechify API token not set in settings,cannot generate speech")
                return False
            if (not self.voice_id):
                print("Speechify Voice ID not set in settings,cannot generate speech")
                return False
            self._ensure_lang_code()
            if self.lang_code not in self.supported_lang:
                print(f"Configured language '{self.lang_code}' is not officially supported by Speechify plugin. Check documentation for compatibility.")
            try:
                self.client = Speechify(token=self.api_key)
                self.is_loaded = True
                self.get_voices_list() # Pre-fetch voices list to validate API key and voice ID
                self.mark_ready()
                return True
            except Exception as e:
                self.logger.error(f"Error occurred while creating Speechify client : {e}")
                return False
        except Exception as e:
            self.logger.error(f"Error occurred while setting user : {e}")
            return False
        
    @hookimpl
    def global_settings_updated(self):
        print("RELOADING SPEECHIFY SETTINGS")
        self.startup()
        
    @hookimpl
    def speak(self, message):
        print("§§§§ SPEECHIFY SPEAKING *********************************************** :", message)
        # Schedule the speak_func to run in the background
        asyncio.create_task(self.run_speak_func(message))
        asyncio.create_task(self.pm.trigger_hook(hook_name="reset_conversation_timeout"))
        
    @hookimpl
    def test_speak(self, message, **kwargs):
        pitch = kwargs.get('pitch', '0')
        rate = kwargs.get('rate', '0')  
        volume = kwargs.get('volume', '0')
        voice_id = kwargs.get('voice_id', self.voice_id)
        print(f"TEST SPEAK with pitch={pitch}, rate={rate}, volume={volume}")
        ssml = self.get_ssml(message, **kwargs)
        print ("SSML:", ssml)
        asyncio.create_task(self.call_speechify(input=ssml, voice_id=voice_id, language=self.lang_code, model="simba-multilingual"))
    
    def get_voices_list(self, api_key_override=None):
        try:
            client = getattr(self, 'client', None)

            if api_key_override:
                override_key = api_key_override.strip()
                if not override_key:
                    self.logger.error("Received empty API key override for voice list retrieval")
                    return []
                try:
                    client = Speechify(token=override_key)
                    self.client = client
                    self.api_key = override_key
                except Exception as client_error:
                    self.logger.error(f"Failed to initialize Speechify client with override key: {client_error}")
                    return []
            elif client is None:
                api_key = getattr(self, 'api_key', None)
                if not api_key:
                    self.logger.error("Speechify API token not set; cannot load voices")
                    return []
                try:
                    client = Speechify(token=api_key)
                    self.client = client
                except Exception as client_error:
                    self.logger.error(f"Failed to initialize Speechify client: {client_error}")
                    return []

            voices = client.tts.voices.list()
            # print(voices)
            if not voices:
                self.logger.error("No voices found from Speechify")
                return []
            # Support SDKs that return either a list or an object with a .voices attribute
            if isinstance(voices, list):
                voices_iter = voices
            elif isinstance(voices, dict) and "voices" in voices:
                voices_iter = voices["voices"]
            elif hasattr(voices, "voices"):
                voices_iter = getattr(voices, "voices") or []
            else:
                # Unexpected shape
                self.logger.error("Unexpected voices response shape from Speechify")
                return []

            voice_list = []
            # prefer already-normalized lang_code, fall back to legacy lang property
            lang = self._ensure_lang_code()
            print (f"LANG CODE IS {lang}")
            for v in voices_iter:
                # support both dict and object shapes
                def get_attr(obj, name, default=None):
                    if isinstance(obj, dict):
                        return obj.get(name, default)
                    return getattr(obj, name, default)

                # collect all locale hints for this voice (top-level and model->languages)
                locales = set()
                top_locale = get_attr(v, "locale", None)
                if top_locale:
                    locales.add(top_locale)

                # Normalize models to an iterable (list) even if SDK returns None or a single object
                models = get_attr(v, "models", []) or []
                if not isinstance(models, (list, tuple, set)):
                    models = [models]

                for m in models:
                    if not m:
                        continue
                    # m can be dict or object
                    m_languages = m.get("languages") if isinstance(m, dict) else getattr(m, "languages", None)
                    # ensure m_languages is iterable
                    if not m_languages:
                        continue
                    if not isinstance(m_languages, (list, tuple, set)):
                        m_languages = [m_languages]
                    for l in m_languages or []:
                        if isinstance(l, dict):
                            loc = l.get("locale")
                        else:
                            loc = getattr(l, "locale", None)
                        if loc:
                            locales.add(loc)

                # If a language filter is configured, exclude voices that don't advertise the language
                if lang and len(locales) > 0 and lang not in locales:
                    continue

                type = get_attr(v, "type", "")
                # Normalize tags to a list safely (avoid iterating None)
                raw_tags = get_attr(v, "tags", []) or []
                if isinstance(raw_tags, (list, tuple, set)):
                    tags_list = list(raw_tags)
                elif isinstance(raw_tags, str):
                    tags_list = [raw_tags]
                else:
                    tags_list = []

                # Keep only age tags (e.g. "age:middle-aged")
                age_tags = [t for t in tags_list if isinstance(t, str) and t.startswith("age:")]
                tags = age_tags
                gender = get_attr(v,"gender","")
                display_name = get_attr(v, "display_name", "")
                vid = get_attr(v, "id", get_attr(v, "voice_id", None))
                voice_list.append({"display_name": f"{display_name}", "id": vid, "type": type, "gender": gender, "tags": tags})
            print(f"Found {len(voice_list)} voices matching language '{lang}'")
            self.voice_list = voice_list
            self.update_my_settings('voice_list',voice_list)
            self.settings=self.get_my_settings()
            return voice_list
        except Exception as e:
            self.logger.error(f"Error occurred while fetching voices: {e}")
            return []        

    def run_restart_asr(self):
        asyncio.create_task(self.restart_asr())
        
    async def restart_asr(self):
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def run_speak_func(self, message):
        success = await self.safe_speak_func(message)

    async def safe_speak_func(self, message):
        try:
            result = await self.speak_func(message)
            if not result:
                self.logger.warning("Speak function encountered an issue but handled gracefully.")
                await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
            return False

    def process_incoming_message(self, message):
        """Extend the base plugin's message handler with ASR-specific actions"""
        try:
            # Normalize incoming message: it can be a dict already, a JSON string,
            # or even a double-encoded JSON string. Be permissive and robust.
            data = message
            # decode bytes
            if isinstance(message, (bytes, bytearray)):
                try:
                    data = message.decode('utf-8')
                except Exception:
                    data = message

            # if it's a string, try to parse JSON
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    # leave as-is (plain string)
                    pass

            # handle the case where json.loads returned a JSON string (double-encoded)
            if isinstance(data, str):
                try:
                    data2 = json.loads(data)
                    data = data2
                except Exception:
                    pass

            print("INCOMING MESSAGE DATA:", data)

            # If we ended up with a dict, handle actions
            if isinstance(data, dict) and 'action' in data:
                # Handle ASR-specific actions
                if data.get('action', '') == 'test_speak':
                    # Build kwargs from the payload but remove keys we don't want to pass
                    payload = data.copy()
                    payload.pop('action', None)
                    # Allow the frontend to optionally pass a 'message' field; otherwise use a default
                    msg = payload.pop('message', None) or "Hello, how are you doing? I feel better today!"
                    # Call test_speak with a string message and keyword args
                    # Ensure numeric values are passed as numbers
                    try:
                        # convert any numeric-like strings to numbers where sensible
                        for k in ('pitch', 'rate', 'volume'):
                            if k in payload:
                                v = payload[k]
                                if isinstance(v, str) and v.strip() != '':
                                    try:
                                        payload[k] = int(float(v))
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                    self.test_speak(msg, **payload)
                    return
                elif data.get('action', '') == 'get_voice_list':
                    override_key = data.get('api_key')
                    voice_list = self.get_voices_list(api_key_override=override_key)
                    response = {
                        "type": "voice_list",
                        "voice_list": voice_list
                    }
                    if not voice_list:
                        response["error"] = "voice_list_empty"
                    self.send_message_to_frontend(response, plugin_name='speechifyttsSettings')
                    return voice_list
            # fallback to base behaviour
            super().process_incoming_message(message)
        except Exception as e:  
            self.logger.error(f"Error processing incoming message: {e}")


    def get_ssml(self,message, **kwargs):
        import html
        
        # Escape XML special characters in message
        safe_message = html.escape(message)
        
        # Get voice settings from kwargs or use defaults
        pitch = kwargs.get('pitch', '0')
        rate = kwargs.get('rate', '0') 
        volume = kwargs.get('volume', '0')

        def fmt_percent(v):
            """Return a string suitable for prosody attributes.
            If v is numeric (int/float or numeric string) return signed percent like '+10%'/ '-5%'/ '0%'.
            Otherwise return the original string unchanged (e.g., 'medium').
            """
            # try numeric conversion
            try:
                # convert booleans to int as well? avoid True/False
                if isinstance(v, bool):
                    return str(v)
                n = int(float(v))
                sign = '+' if n > 0 else ''
                return f"{sign}{n}%"
            except Exception:
                return str(v)
        
        # Format numeric settings as signed percentages when possible
        pitch_attr = fmt_percent(pitch)
        rate_attr = fmt_percent(rate)
        volume_attr = fmt_percent(volume)

        # Build SSML with f-string formatting
        ssml = f"""
        <speak>
            <prosody pitch="{pitch_attr}" rate="{rate_attr}" volume="{volume_attr}">
                {safe_message}
            </prosody>
        </speak>"""
        return ssml.strip()

    async def call_speechify(self,input,voice_id,language,model="simba-multilingual"):
        response = self.client.tts.audio.speech(
            input=input,  # Use SSML instead of plain text
            voice_id=voice_id,
            language=language,
            model=model
            # format=OUTPUT_FORMAT # Add if needed/supported
        )
        if not response or not response.audio_data:
            self.logger.error("Received empty audio data from Speechify")
            return False
        else:
            # Decode the Base64-encoded audio data to bytes
            audio_bytes = base64.b64decode(response.audio_data)
            print(f"Received {len(audio_bytes)} bytes of audio data. Decoding...")

            '''
            debug_path = os.path.join(self.plugin_folder, "debug_speechify_output.wav")
            with open(debug_path, "wb") as f:
                f.write(audio_bytes)
            '''
            # 2. Decode the audio bytes using pydub
            audio_file_like = io.BytesIO(audio_bytes)
            try:
                if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
                    print("Decoding Speechify audio as WAV without ffmpeg")
                    audio_segment = AudioSegment.from_wav(audio_file_like)
                else:
                    raise CouldntDecodeError("Non-WAV header detected", audio_file_like)
            except CouldntDecodeError:
                audio_file_like.seek(0)
                print("Falling back to AudioSegment.from_file (ffmpeg may be required)")
                audio_segment = AudioSegment.from_file(audio_file_like)
    

            # Convert to 16-bit PCM mono/stereo if needed
            audio_segment = audio_segment.set_frame_rate(22050).set_sample_width(2).set_channels(1)
            samples = np.array(audio_segment.get_array_of_samples()).astype(np.int16)
            sample_rate = audio_segment.frame_rate

            print("Decoding complete. Preparing for playback...")

            # 3. Play the audio using pydub playback
            print("Playing audio...")
            await self.pm.trigger_hook(hook_name="pause_asr")
            await asyncio.sleep(0.1)  # Ensure pause message reaches frontend

            def play_audio():
                play(audio_segment)

            await asyncio.to_thread(play_audio)
            self.run_restart_asr()
            print("Playback finished.")
            
            return True


    async def speak_func(self, message):
        print("SPEAK FUNC:" + message)
        try:
            try:
                # Generate SSML with the message
                if (self.settings.get("use_ssml")): # Changed from .lower() == "true"
                    ssml_content = self.get_ssml(message, pitch=self.settings.get('pitch', 'medium'), rate=self.settings.get('rate', 'medium'), volume=self.settings.get('volume', 'medium'))
                else:
                    ssml_content=message
                print (ssml_content)                
                return await self.call_speechify(input=ssml_content, voice_id=self.voice_id, language=self.lang_code, model="simba-multilingual")
             
            except Exception as inner_e:
                self.logger.warning(f"Error playing back audio data: {inner_e}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error occurred while speaking: {e}")
            await self.pm.trigger_hook(hook_name="speak_fallback",message=message) 
            return False