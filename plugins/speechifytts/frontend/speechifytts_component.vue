<template>
    <div class="speechifytts">
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "speechifytts",
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
                console.error('Error parsing speechifytts message:', e);
            }
            
            return false;
        },
        
        async $_handlePlayAudio(audioUrl) {
            console.log('Speechify: Playing audio from', audioUrl);
            try {
                // Use window.TTSPlayer (loaded globally)
                if (window.TTSPlayer) {
                    await window.TTSPlayer.play(audioUrl);
                } else {
                    console.error('TTSPlayer not available on window');
                    // Fallback to direct Audio API
                    const audio = new Audio(audioUrl);
                    await audio.play();
                }
                // Notify backend that playback is complete
                this.sendMsgToBackend({ action: 'playback_complete' });
            } catch (error) {
                console.error('Speechify audio playback error:', error);
                // Notify backend of error so it can try fallback
                this.sendMsgToBackend({ action: 'playback_failed', error: error.message });
            }
        },
        
        async $_speak(msg) {
            try {
                console.log("triggering speak hook with message " + msg);
                const api = await window.ensureBackendApi();
                const result = await api.triggerHook("speak", { message: msg });
                return result;
            } catch (error) {
                console.error('Error triggering speak hook: ', error);
            }
        }
    }
};
</script>