/**
 * TTSPlayer - HTML5 Audio wrapper for playing TTS audio from REST endpoints
 * Used by elevenlabstts and speechifytts plugins to stream audio to client
 */
const TTSPlayer = {
    currentAudio: null,
    isPlaying: false,
    onPlayStart: null,
    onPlayEnd: null,
    onPlayError: null,

    /**
     * Play audio from URL using HTML5 Audio API
     * @param {string} audioUrl - URL to the audio file (e.g., /api/plugins/elevenlabstts/audio/uuid)
     * @param {object} options - Optional settings
     * @returns {Promise} Resolves when audio playback is complete
     */
    play(audioUrl, options = {}) {
        return new Promise((resolve, reject) => {
            // Stop any currently playing audio
            this.stop();

            console.log(`TTSPlayer: Playing audio from ${audioUrl}`);

            const audio = new Audio(audioUrl);
            this.currentAudio = audio;

            // Event handlers
            audio.onplay = () => {
                this.isPlaying = true;
                console.log('TTSPlayer: Playback started');
                if (this.onPlayStart) this.onPlayStart();
            };

            audio.onended = () => {
                this.isPlaying = false;
                this.currentAudio = null;
                console.log('TTSPlayer: Playback ended');
                if (this.onPlayEnd) this.onPlayEnd();
                resolve();
            };

            audio.onerror = (event) => {
                this.isPlaying = false;
                this.currentAudio = null;
                const error = `Audio playback error: ${event.type}`;
                console.error('TTSPlayer:', error);
                if (this.onPlayError) this.onPlayError(error);
                reject(new Error(error));
            };

            // Start playback
            audio.play().catch((err) => {
                this.isPlaying = false;
                this.currentAudio = null;
                console.error('TTSPlayer: Failed to start playback:', err);
                if (this.onPlayError) this.onPlayError(err.message);
                reject(err);
            });
        });
    },

    /**
     * Stop current audio playback
     */
    stop() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
            this.isPlaying = false;
            console.log('TTSPlayer: Playback stopped');
        }
    },

    /**
     * Pause current audio playback
     */
    pause() {
        if (this.currentAudio && this.isPlaying) {
            this.currentAudio.pause();
            this.isPlaying = false;
            console.log('TTSPlayer: Playback paused');
        }
    },

    /**
     * Resume paused audio playback
     */
    resume() {
        if (this.currentAudio && !this.isPlaying) {
            this.currentAudio.play().catch(console.error);
            this.isPlaying = true;
            console.log('TTSPlayer: Playback resumed');
        }
    },

    /**
     * Check if audio is currently playing
     * @returns {boolean}
     */
    isCurrentlyPlaying() {
        return this.isPlaying && this.currentAudio !== null;
    },

    /**
     * Set volume (0.0 to 1.0)
     * @param {number} volume
     */
    setVolume(volume) {
        if (this.currentAudio) {
            this.currentAudio.volume = Math.max(0, Math.min(1, volume));
        }
    }
};

// Export for both CommonJS and browser
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TTSPlayer;
}
if (typeof window !== 'undefined') {
    window.TTSPlayer = TTSPlayer;
}
