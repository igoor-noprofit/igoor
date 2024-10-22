from plugin_manager import hookimpl
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
from elevenlabslib import *
from dotenv import load_dotenv
load_dotenv()
import os
import pyaudio

class Elevenlabs:
    @hookimpl
    def get_frontend_components(self):
        print("loading ELEVENLABS frontend")
        return [
            {
                "vue": "geo_component.vue"
            }
        ]
        
    @hookimpl
    def startup(self):
        print ("ELEVENLABS IS STARTING UP")
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID")
        self.speak("Bonjour, je suis IGOOR!")

    @hookimpl
    def speak(self, message):
        user = User(self.api_key)
        print("VOICE ID ", self.voice_id)
        # print("AVAILABLE VOICES ", user.get_available_voices())
        voice=user.get_voice_by_ID(os.getenv("ELEVENLABS_VOICE_ID"))   
        print ("§§§§ SPEAKING *********************************************** :",message)
        
        # Set generation options
        generation_options = GenerationOptions(
            latencyOptimizationLevel=1,   # Adjusts latency optimization
            stability=0.5,                # Example stability value
            similarity_boost=0.8,         # Example similarity boost
            style="informative",           # Example style
            use_speaker_boost=True,       # Enables speaker boost
            model='eleven_multilingual_v2', # Specifies the model
            output_format='mp3_highest',  # Sets the output format
            seed=42,                      # Random seed for generation
            language_code='fr-FR',        # Language code for the audio
            pronunciation_dictionaries=None # Optional pronunciation dictionaries
        )
        voice.stream_audio_v3(message)
        #None, generation_options
    '''
    @hookimpl
    def speak(self, message):
        voice = os.getenv("ELEVENLABS_VOICE_ID")
        model = os.getenv("ELEVENLABS_MODEL_ID")
        print(f"Speaking: {message}")

        # Generate audio and stream
        audio_stream = self.client.generate(text=message, stream=True)

        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        # Define stream settings. Adjust these to the correct format.
        format = pyaudio.paInt16  # Assuming 16-bit samples
        channels = 2              # Mono audio
        rate = 22050              # Sample rate, adjust accordingly

        # Open a .Stream object to play the audio
        # Open a .Stream object to play the audio
        stream = p.open(format=format,
                    channels=channels,
                    rate=rate,
                    output=True)

        # Read the audio stream and play it
        for chunk in audio_stream:
            stream.write(chunk)

        # Close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()
    '''