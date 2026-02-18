<template>
    <div class="elevenlabstts">
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "elevenlabstts",
    mixins: [BasePluginComponent],
    methods: {
        handleIncomingMessage(event) {
            // Let base component handle common messages first
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) {
                return true;
            }
            
            try {
                const data = JSON.parse(event.data);
                
                // Handle audio playback action from backend (LAN mode)
                if (data.action === 'play_audio') {
                    this.$_handlePlayAudio(data.audio_url);
                    return true;
                }
                
                // Handle voice list response
                if (data.type === 'voice_list') {
                    console.log('Received voice list:', data.voice_list);
                    return true;
                }
                
            } catch (e) {
                console.error('Error parsing elevenlabs message:', e);
            }
            
            return false;
        },
        
        async $_handlePlayAudio(audioUrl) {
            console.log('ElevenLabs: Playing audio from', audioUrl);
            try {
                // Play audio and wait for it to finish
                const audio = new Audio(audioUrl);
                
                // Create a promise that resolves when audio ends
                const playbackPromise = new Promise((resolve, reject) => {
                    audio.onended = () => resolve();
                    audio.onerror = (e) => reject(new Error(`Audio error: ${e.type}`));
                });
                
                // Start playback
                await audio.play();
                
                // Wait for playback to complete
                await playbackPromise;
                
                // Notify backend that playback is complete
                this.sendMsgToBackend({ action: 'playback_complete' });
            } catch (error) {
                console.error('ElevenLabs audio playback error:', error);
                // Notify backend of error so it can try fallback
                this.sendMsgToBackend({ action: 'playback_failed', error: error.message });
            }
        },
        
        async $_speak(msg) {
            try {
                console.log("triggering speak hook with message " + msg);
                const result = pywebview.api.trigger_hook("speak", { message: msg });
            } catch (error) {
                console.error('Error triggering speak hook: ', error);
            }
        }
    }
};
</script>