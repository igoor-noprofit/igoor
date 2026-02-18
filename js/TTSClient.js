/**
 * TTSClient - Web Speech API wrapper for client-side text-to-speech
 * Used by ttsdefault plugin to play audio on the client device
 */
const TTSClient = {
    voices: [],
    currentVoiceIndex: 0,
    isInitialized: false,
    onVoicesLoaded: null,
    onSpeakStart: null,
    onSpeakEnd: null,
    onSpeakError: null,

    /**
     * Initialize the TTS client and load available voices
     */
    init() {
        if (this.isInitialized) return;
        
        // Load voices
        this.loadVoices();
        
        // Some browsers load voices asynchronously
        if (typeof speechSynthesis !== 'undefined' && speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = () => {
                this.loadVoices();
                if (this.onVoicesLoaded) {
                    this.onVoicesLoaded(this.voices);
                }
            };
        }
        
        this.isInitialized = true;
        console.log('TTSClient initialized');
    },

    /**
     * Load available voices from the browser
     */
    loadVoices() {
        if (typeof speechSynthesis === 'undefined') {
            console.warn('Web Speech API not supported in this browser');
            return;
        }
        
        this.voices = speechSynthesis.getVoices();
        console.log(`TTSClient: Loaded ${this.voices.length} voices`);
    },

    /**
     * Get list of available voices
     * @returns {Array} Array of voice objects with id, name, lang
     */
    getVoices() {
        return this.voices.map((voice, index) => ({
            id: index,
            name: voice.name,
            lang: voice.lang,
            native: voice.localService
        }));
    },

    /**
     * Set the voice by index
     * @param {number} index - Voice index from getVoices()
     */
    setVoice(index) {
        if (index >= 0 && index < this.voices.length) {
            this.currentVoiceIndex = index;
            console.log(`TTSClient: Voice set to ${this.voices[index].name}`);
        }
    },

    /**
     * Speak text using Web Speech API
     * @param {string} text - Text to speak
     * @param {object} options - Optional settings (rate, pitch, volume, voiceId)
     * @returns {Promise} Resolves when speech is complete
     */
    speak(text, options = {}) {
        return new Promise((resolve, reject) => {
            if (typeof speechSynthesis === 'undefined') {
                const error = 'Web Speech API not supported';
                console.error(error);
                if (this.onSpeakError) this.onSpeakError(error);
                reject(new Error(error));
                return;
            }

            if (!text || text.trim() === '') {
                resolve();
                return;
            }

            // Cancel any ongoing speech
            speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            
            // Set voice
            const voiceId = options.voiceId !== undefined ? options.voiceId : this.currentVoiceIndex;
            if (this.voices[voiceId]) {
                utterance.voice = this.voices[voiceId];
            }

            // Set speech parameters
            if (options.rate !== undefined) utterance.rate = options.rate;
            if (options.pitch !== undefined) utterance.pitch = options.pitch;
            if (options.volume !== undefined) utterance.volume = options.volume;
            if (options.lang !== undefined) utterance.lang = options.lang;

            // Event handlers
            utterance.onstart = () => {
                console.log('TTSClient: Speech started');
                if (this.onSpeakStart) this.onSpeakStart();
            };

            utterance.onend = () => {
                console.log('TTSClient: Speech ended');
                if (this.onSpeakEnd) this.onSpeakEnd();
                resolve();
            };

            utterance.onerror = (event) => {
                console.error('TTSClient: Speech error:', event.error);
                if (this.onSpeakError) this.onSpeakError(event.error);
                reject(new Error(event.error));
            };

            // Speak
            speechSynthesis.speak(utterance);
        });
    },

    /**
     * Stop any ongoing speech
     */
    stop() {
        if (typeof speechSynthesis !== 'undefined') {
            speechSynthesis.cancel();
            console.log('TTSClient: Speech stopped');
        }
    },

    /**
     * Pause ongoing speech
     */
    pause() {
        if (typeof speechSynthesis !== 'undefined') {
            speechSynthesis.pause();
        }
    },

    /**
     * Resume paused speech
     */
    resume() {
        if (typeof speechSynthesis !== 'undefined') {
            speechSynthesis.resume();
        }
    },

    /**
     * Check if currently speaking
     * @returns {boolean}
     */
    isSpeaking() {
        if (typeof speechSynthesis !== 'undefined') {
            return speechSynthesis.speaking;
        }
        return false;
    }
};

// Export for both CommonJS and browser
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TTSClient;
}
if (typeof window !== 'undefined') {
    window.TTSClient = TTSClient;
}
