<template>
    <div class="asrvosk-plugin">
        <div class="mic" :class="[status, { 'clickable': !continuous }]" @click="$_handleMicClick">
            <img src="/img/mic.png">
        </div>
        <button v-show="continuous" class="mode-toggle btn btn-small" :class="{ 'active': continuous }"
            @click="$_toggleMode" title="Toggle continuous mode">{{ t('Continuous mode') }}
        </button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "asrjs",
    mixins: [BasePluginComponent],
    data() {
        return {
            status: 'loading',
            audio: {},
            continuous: false,
            keyboardShortcut: null,
            vad: null, // Store VAD instance
            vadInitialized: false,
            audioChunks: [] // Store audio chunks for transcription
        };
    },
    created() {
        this.audio = {
            on: new Audio('/plugins/asrvosk/samples/on.wav'),
            off: new Audio('/plugins/asrvosk/samples/off.wav')
        };
        Object.values(this.audio).forEach(audio => audio.load());
    },
    async mounted() {
        window.addEventListener('keydown', this.$_handleKeyPress);
        
        // Load VAD library dynamically, then initialize
        await this.$_loadVADLibrary();
    },
    beforeDestroy() {
        window.removeEventListener('keydown', this.$_handleKeyPress);
        
        // Cleanup VAD
        if (this.vad) {
            this.vad.destroy();
        }
    },
    methods: {
        $_loadVADLibrary() {
            return new Promise((resolve, reject) => {
                // Check if already loaded
                if (window.vad) {
                    console.log('VAD library already loaded, skipping');
                    resolve();
                    return;
                }

                // Check if script tag already exists (prevents duplicate loading)
                const existingScript = document.querySelector('script[src="/plugins/asrjs/static/vad/bundle.min.js"]');
                if (existingScript) {
                    console.log('VAD library script already added, waiting for load...');
                    // Wait for it to load
                    const checkInterval = setInterval(async() => {
                        if (window.vad) {
                            clearInterval(checkInterval);
                            console.log('VAD library ready');
                            await this.$_initializeVAD();
                            resolve();
                        }
                        else{
                            console.log('Waiting for VAD library to load...');
                        }
                    }, 100);
                    return;
                }

                // Create script element
                const script = document.createElement('script');
                script.src = '/plugins/asrjs/static/vad/bundle.min.js';
                script.async = true;
                
                script.onload = () => {
                    console.log('VAD library loaded successfully');
                    resolve();
                };
                
                script.onerror = () => {
                    console.error('Failed to load VAD library');
                    this.status = 'error';
                    reject(new Error('Failed to load VAD library'));
                };
                
                // Append to document
                document.head.appendChild(script);
            });
        },

        async $_initializeVAD() {
            try {
                // VAD library should now be loaded
                if (!window.vad) {
                    throw new Error('VAD library not available');
                }

                this.vad = await window.vad.MicVAD.new({
                    // If bundling locally, specify paths:
                    baseAssetPath: "/plugins/asrjs/static/vad-assets",
                    onnxWASMBasePath: "/plugins/asrjs/static/onnx-wasm",
                    
                    // VAD configuration
                    positiveSpeechThreshold: 0.5,
                    negativeSpeechThreshold: 0.35,
                    redemptionFrames: 8,
                    preSpeechPadFrames: 1,
                    minSpeechFrames: 3,
                    
                    // Callbacks
                    onSpeechStart: () => {
                        console.log("Speech started");
                        this.audioChunks = [];
                        if (this.continuous) {
                            this.status = 'recording';
                            this.audio.on.play();
                        }
                    },
                    
                    onSpeechEnd: (audio) => {
                        console.log("Speech ended", audio);
                        if (this.continuous || this.status === 'recording') {
                            this.$_processAudio(audio);
                            this.audio.off.play();
                        }
                    },
                    
                    onVADMisfire: () => {
                        console.log("VAD misfire - false positive");
                        this.status = 'empty';
                        this.audio.off.play();
                        setTimeout(() => {
                            this.status = 'listening';
                        }, 500);
                    }
                });

                this.vadInitialized = true;
                this.status = 'ready';
                console.log('VAD initialized successfully');
                
            } catch (error) {
                console.error('Failed to initialize VAD:', error);
                this.status = 'error';
            }
        },

        async $_processAudio(audioData) {
            // Convert Float32Array audio to WAV blob
            const wavBlob = this.$_audioToWav(audioData);
            
            // Send to backend for transcription
            this.sendMsgToBackend({
                action: 'transcribe_audio',
                audio: await this.$_blobToBase64(wavBlob)
            });
            
            this.status = 'transcribing';
        },

        $_audioToWav(float32Array) {
            // Convert Float32Array to WAV format
            const sampleRate = 16000;
            const numChannels = 1;
            const bitsPerSample = 16;
            
            // Convert float32 to int16
            const int16Array = new Int16Array(float32Array.length);
            for (let i = 0; i < float32Array.length; i++) {
                const s = Math.max(-1, Math.min(1, float32Array[i]));
                int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Create WAV file
            const buffer = new ArrayBuffer(44 + int16Array.length * 2);
            const view = new DataView(buffer);
            
            // Write WAV header
            this.$_writeString(view, 0, 'RIFF');
            view.setUint32(4, 36 + int16Array.length * 2, true);
            this.$_writeString(view, 8, 'WAVE');
            this.$_writeString(view, 12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, numChannels, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * numChannels * bitsPerSample / 8, true);
            view.setUint16(32, numChannels * bitsPerSample / 8, true);
            view.setUint16(34, bitsPerSample, true);
            this.$_writeString(view, 36, 'data');
            view.setUint32(40, int16Array.length * 2, true);
            
            // Write audio data
            const offset = 44;
            for (let i = 0; i < int16Array.length; i++) {
                view.setInt16(offset + i * 2, int16Array[i], true);
            }
            
            return new Blob([buffer], { type: 'audio/wav' });
        },

        $_writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        },

        async $_blobToBase64(blob) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        },

        $_handleKeyPress(event) {
            console.log("Key pressed:", event.key, "with modifiers:", {
                ctrl: event.ctrlKey,
                alt: event.altKey,
                shift: event.shiftKey,
                meta: event.metaKey
            });
            const pressed = [];
            if (event.ctrlKey) pressed.push("Ctrl");
            if (event.altKey) pressed.push("Alt");
            if (event.shiftKey) pressed.push("Shift");
            if (event.metaKey) pressed.push("Meta");
            if (!["Control", "Shift", "Alt", "Meta"].includes(event.key)) {
                pressed.push(event.key.length === 1 ? event.key.toUpperCase() : event.key);
            }
            const pressedCombo = pressed.join("+");
            if (this.keyboardShortcut && pressedCombo === this.keyboardShortcut) {
                event.preventDefault();
                this.$_handleMicClick();
            }
        },

        $_toggleMode() {
            this.continuous = !this.continuous;
            
            if (this.continuous) {
                // Start VAD listening
                if (this.vad && this.vadInitialized) {
                    this.vad.start();
                    this.status = 'listening';
                }
            } else {
                // Pause VAD
                if (this.vad) {
                    this.vad.pause();
                    this.status = 'ready';
                }
            }
            
            this.sendMsgToBackend({
                action: 'set_continuous_mode',
                continuous: this.continuous
            });
        },

        handleIncomingMessage(event) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;
            console.log(this.$options.name + ' handling message');
            
            try {
                const data = JSON.parse(event.data);
                if (data.type === "settings") {
                    this.settings = data.settings;
                    console.log('ASRJS SETTINGS:', this.settings);
                    this.continuous = this.settings.continuous || false;
                    if (this.settings.shortcut) {
                        console.log('ASRJS SHORTCUT:', this.settings.shortcut);
                        this.keyboardShortcut = this.settings.shortcut;
                    }
                }
                if (data.status) {
                    this.status = data.status;
                }
            } catch (e) {
                console.error("Error parsing message:", e);
            }
        },

        $_handleMicClick() {
            if (!this.continuous) {
                if (this.status === 'listening' || this.status === 'ready') {
                    // Manual push-to-talk: start VAD
                    if (this.vad) {
                        this.vad.start();
                        this.status = 'recording';
                        this.sendMsgToBackend({ action: 'start_recording' });
                    }
                } else if (this.status === 'recording') {
                    // Stop recording
                    if (this.vad) {
                        this.vad.pause();
                        this.status = 'listening';
                        this.sendMsgToBackend({ action: 'stop_recording' });
                    }
                }
            } else {
                console.warn("Cannot click when in continuous mode");
            }
        }
    },
    watch: {
        status(newStatus, oldStatus) {
            if (this.continuous) {
                if (oldStatus === 'loading' && newStatus === 'listening') {
                    console.log("listening");
                } else if (oldStatus === 'listening' && newStatus === 'recording') {
                    this.audio.on.play();
                } else if (oldStatus === 'recording' && newStatus === 'listening') {
                    this.audio.off.play();
                }
            }
            if (newStatus === 'empty') {
                console.warn("Playing OFF sound");
                this.audio.off.play();
                this.status = 'listening';
            }
        }
    }
};
</script>

<style>
.asrvosk-plugin {
    flex-direction: column;
}

.mic.clickable {
    cursor: pointer;
    height: 100%;
    vertical-align: middle;
    display: flex;
    justify-content: center;
    align-items: center;
}

.mic img {
    max-height: 50px;
    max-width: 50px;
}

.mode-toggle {
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 5px;
    background: #444;
    transition: all 0.3s ease;
}

.mode-toggle.active {
    background: #2196F3;
    box-shadow: 0 0 10px rgba(33, 150, 243, 0.5);
}

.mode-toggle span {
    font-size: 18px;
    color: white;
}
</style>