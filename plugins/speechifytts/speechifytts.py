from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
import asyncio
import os
from speechify import Speechify
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import io
import base64
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
                
    @hookimpl
    def startup(self):
        self.supported_lang = ['en', 'fr-FR', 'de-DE', 'es-ES', 'pt-BR', 'pt-PT']
        self.settings = self.get_my_settings()
        print ("SPEECHIFY settings", self.settings)
        try:
            self.api_key = self.settings.get("api_key")
            self.voice_id = self.settings.get("voice_id")  
            if (not self.api_key):
                self.logger.error("Speechify API token not set in settings,cannot generate speech")
                return False
            if (not self.voice_id):
                self.logger.error("Speechify Voice ID not set in settings,cannot generate speech")
                return False
            self.lang_code = self.lang.replace("_", "-")
            if self.lang_code not in self.supported_lang:
                self.logger.warning(f"Configured language '{self.lang_code}' is not officially supported by Speechify plugin. Check documentation for compatibility.")
            try:
                self.client = Speechify(token=self.api_key)
                self.is_loaded = True
                return True
            except Exception as e:
                self.logger.error(f"Error occurred while creating Speechify client : {e}")
                return False
        except Exception as e:
            self.logger.error(f"Error occurred while setting user : {e}")
            return False
        
    @hookimpl
    def speak(self, message):
        print("§§§§ SPEECHIFY SPEAKING *********************************************** :", message)
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
        try:
            result = await self.speak_func(message)
            if not result:
                self.logger.warning("Speak function encountered an issue but handled gracefully.")
                await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
            return False

    def get_ssml(self,message, **kwargs):
        '''Generate SSML with the message and optional voice settings
        Example:
            <speak>
                This is a normal speech pattern.
                <prosody pitch="high" rate="fast" volume="+20%">
                    I'm speaking with a higher pitch, faster than usual, and louder!
                </prosody>
                Back to normal speech pattern.
            </speak>
        '''
        import html
        
        # Escape XML special characters in message
        safe_message = html.escape(message)
        
        # Get voice settings from kwargs or use defaults
        pitch = kwargs.get('pitch', 'medium')
        rate = kwargs.get('rate', 'medium') 
        volume = kwargs.get('volume', 'medium')
        
        # Build SSML with f-string formatting
        ssml = f"""
        <speak>
            <prosody pitch="{pitch}" rate="{rate}" volume="{volume}">
                {safe_message}
            </prosody>
        </speak>"""
        
        return ssml.strip()
        

    async def speak_func(self, message):
        print ("SETTINGS", self.settings)
        print("SPEAK FUNC:" + message)
        try:
            try:
                # Generate SSML with the message
                
                ssml_content = self.get_ssml(message, pitch=self.settings.get('pitch', 'medium'), rate=self.settings.get('rate', 'medium'), volume=self.settings.get('volume', 'medium'))
                print (ssml_content)
                
                
                response = self.client.tts.audio.speech(
                    input=ssml_content,  # Use SSML instead of plain text
                    voice_id=self.voice_id,
                    language=self.lang_code,
                    model="simba-multilingual"
                    # format=OUTPUT_FORMAT # Add if needed/supported
                )
                if not response or not response.audio_data:
                    self.logger.error("Received empty audio data from Speechify")
                    return False
                else:
                    # Decode the Base64-encoded audio data to bytes
                    audio_bytes = base64.b64decode(response.audio_data)
                    print(f"Received {len(audio_bytes)} bytes of audio data. Decoding...")

                    # with open("debug_speechify_output.wav", "wb") as f:
                    #    f.write(audio_bytes)
                    # 2. Decode the audio bytes using pydub
                    audio_file_like = io.BytesIO(audio_bytes)
                    audio_segment = AudioSegment.from_file(audio_file_like)

                    # Convert to 16-bit PCM mono/stereo if needed
                    audio_segment = audio_segment.set_frame_rate(22050).set_sample_width(2).set_channels(1)
                    samples = np.array(audio_segment.get_array_of_samples()).astype(np.int16)
                    sample_rate = audio_segment.frame_rate

                    print("Decoding complete. Preparing for playback...")

                    # 3. Play the audio using pydub playback
                    print("Playing audio...")
                    await self.pm.trigger_hook(hook_name="pause_asr")

                    def play_audio():
                        play(audio_segment)

                    await asyncio.to_thread(play_audio)
                    self.run_restart_asr()
                    print("Playback finished.")
                    
                    return True
            except Exception as inner_e:
                self.logger.warning(f"Error playing back audio data: {inner_e}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error occurred while speaking: {e}")
            await self.pm.trigger_hook(hook_name="speak_fallback",message=message) 
            return False