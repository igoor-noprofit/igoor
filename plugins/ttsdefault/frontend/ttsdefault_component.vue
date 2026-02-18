<template>
    <div class="ttsdefault plugin">
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import TTSClient from '/js/TTSClient.js';

module.exports = {
    name: "ttsdefault",
    mixins: [BasePluginComponent],
    data() {
        return {
            voices: [],
            currentVoiceId: 0
        };
    },
    created() {
        // Initialize TTSClient
        TTSClient.init();
        
        // Set up callbacks
        TTSClient.onVoicesLoaded = (voices) => {
            this.voices = voices;
            console.log('TTSClient voices loaded:', voices.length);
        };
        
        TTSClient.onSpeakStart = () => {
            // Notify backend that speech started
            this.sendMsgToBackend({ action: 'speech_started' });
        };
        
        TTSClient.onSpeakEnd = () => {
            // Notify backend that speech ended
            this.sendMsgToBackend({ action: 'speech_ended' });
        };
        
        TTSClient.onSpeakError = (error) => {
            console.error('TTSClient error:', error);
            this.sendMsgToBackend({ action: 'speech_error', error: error });
        };
        
        // Load initial voices
        this.voices = TTSClient.getVoices();
    },
    methods: {
        handleIncomingMessage(event) {
            // Let base component handle common messages first
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) {
                return true;
            }
            
            try {
                const data = JSON.parse(event.data);
                
                // Handle TTS speak action from backend
                if (data.action === 'speak') {
                    this.$_handleSpeak(data);
                    return true;
                }
                
                // Handle voice list request
                if (data.action === 'get_voices') {
                    this.sendMsgToBackend({
                        action: 'voices_list',
                        voices: this.voices
                    });
                    return true;
                }
                
            } catch (e) {
                console.error('Error parsing TTS message:', e);
            }
            
            return false;
        },
        
        async $_handleSpeak(data) {
            const message = data.message;
            const voiceId = data.voice_id !== undefined ? data.voice_id : this.currentVoiceId;
            const rate = data.rate || 1.0;
            const pitch = data.pitch || 1.0;
            const volume = data.volume || 1.0;
            
            console.log('TTSClient speaking:', message, { voiceId, rate, pitch, volume });
            
            // Set voice if specified
            if (voiceId !== this.currentVoiceId) {
                TTSClient.setVoice(voiceId);
                this.currentVoiceId = voiceId;
            }
            
            try {
                await TTSClient.speak(message, { rate, pitch, volume, voiceId });
            } catch (error) {
                console.error('TTSClient speak error:', error);
                // Notify backend of error so it can try fallback
                this.sendMsgToBackend({ action: 'speak_failed', error: error.message });
            }
        },
        
        $_setVoice(voiceId) {
            TTSClient.setVoice(voiceId);
            this.currentVoiceId = voiceId;
        },
        
        $_stop() {
            TTSClient.stop();
        },
        
        $_pause() {
            TTSClient.pause();
        },
        
        $_resume() {
            TTSClient.resume();
        }
    }
};
</script>