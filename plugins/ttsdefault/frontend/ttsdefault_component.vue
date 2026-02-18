<template>
    <div class="ttsdefault plugin">
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

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
        // Load voices from Web Speech API
        this.loadVoices();
        
        // Some browsers load voices asynchronously
        if (typeof speechSynthesis !== 'undefined' && speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = () => {
                this.loadVoices();
            };
        }
    },
    methods: {
        loadVoices() {
            if (typeof speechSynthesis === 'undefined') {
                console.warn('Web Speech API not supported');
                return;
            }
            const browserVoices = speechSynthesis.getVoices();
            this.voices = browserVoices.map((voice, index) => ({
                id: index,
                name: voice.name,
                lang: voice.lang
            }));
            console.log('Loaded', this.voices.length, 'voices');
        },
        
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
            
            console.log('Web Speech API speaking:', message, { voiceId, rate, pitch, volume });
            
            if (typeof speechSynthesis === 'undefined') {
                console.error('Web Speech API not supported');
                this.sendMsgToBackend({ action: 'playback_failed', error: 'Web Speech API not supported' });
                return;
            }
            
            try {
                // Cancel any ongoing speech
                speechSynthesis.cancel();
                
                const utterance = new SpeechSynthesisUtterance(message);
                
                // Set voice if available
                const browserVoices = speechSynthesis.getVoices();
                if (browserVoices[voiceId]) {
                    utterance.voice = browserVoices[voiceId];
                }
                
                // Set speech parameters
                utterance.rate = rate;
                utterance.pitch = pitch;
                utterance.volume = volume;
                
                // Create a promise that resolves when speech ends
                const speechPromise = new Promise((resolve, reject) => {
                    utterance.onend = () => resolve();
                    utterance.onerror = (e) => reject(new Error(`Speech error: ${e.error}`));
                });
                
                // Start speech
                speechSynthesis.speak(utterance);
                
                // Wait for speech to complete
                await speechPromise;
                
                // Notify backend that speech is complete
                this.sendMsgToBackend({ action: 'playback_complete' });
                
            } catch (error) {
                console.error('Web Speech API error:', error);
                this.sendMsgToBackend({ action: 'playback_failed', error: error.message });
            }
        },
        
        $_stop() {
            if (typeof speechSynthesis !== 'undefined') {
                speechSynthesis.cancel();
            }
        }
    }
};
</script>