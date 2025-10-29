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
            // vad: null, // Store VAD instance - COMMENTED OUT
            // vadInitialized: false,
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
        
        // Load VAD library dynamically, then initialize - COMMENTED OUT
        // await this.$_loadVADLibrary();
        
        // Set status to listening since we're not using VAD
        this.status = 'listening';
        
        // Initialize microphone access
        await this.$_initializeMicrophone();
    },
    beforeDestroy() {
        window.removeEventListener('keydown', this.$_handleKeyPress);
        
        // Cleanup VAD - COMMENTED OUT
        // if (this.vad) {
        //     this.vad.destroy();
        // }
        
        // Cleanup microphone and media recorder
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }
    },
    methods: {
        // $_loadVADLibrary() {
        //     return new Promise((resolve, reject) => {
        //         // Check if already loaded
        //         if (window.vad) {
        //             console.log('VAD library already loaded, skipping');
        //             resolve();
        //             return;
        //         }

        //         // Check if script tag already exists (prevents duplicate loading)
        //         const existingScript = document.querySelector('script[src="/plugins/asrjs/static/vad/bundle.min.js"]');
        //         if (existingScript) {
        //             console.log('VAD library script already added, waiting for load...');
        //             // Wait for it to load
        //             const checkInterval = setInterval(async() => {
        //                 if (window.vad) {
        //                     clearInterval(checkInterval);
        //                     console.log('VAD library ready');
        //                     await this.$_initializeVAD();
        //                     resolve();
        //                 }
        //                 else{
        //                     console.log('Waiting for VAD library to load...');
        //                 }
        //             }, 100);
        //             return;
        //         }

        //         // Create script element
        //         const script = document.createElement('script');
        //         script.src = '/plugins/asrjs/static/vad/bundle.min.js';
        //         script.async = true;
                
        //         script.onload = () => {
        //             console.log('VAD library loaded successfully');
        //             resolve();
        //         };
                
        //         script.onerror = () => {
        //             console.error('Failed to load VAD library');
        //             this.status = 'error';
        //             reject(new Error('Failed to load VAD library'));
        //         };
                
        //         // Append to document
        //         document.head.appendChild(script);
        //     });
        // },

        async $_initializeMicrophone() {
            try {
                // Request microphone permission
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        sampleRate: 16000,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true
                    } 
                });
                
                this.mediaStream = stream;
                this.mediaRecorder = new MediaRecorder(stream, {
                    mimeType: 'audio/webm'
                });
                
                // Don't start recorder here - only start when user clicks
                // this.mediaRecorder.start(100); // Request data every 100ms
                
                // Set up audio chunk collection and streaming
                this.audioChunks = [];
                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        console.log('Audio chunk received:', {
                            size: event.data.size,
                            type: event.data.type,
                            chunksCount: this.audioChunks.length
                        });
                        
                        // Send chunk to speakerid via HTTP endpoint (during recording)
                        this.$_sendChunkToSpeakerID(event.data);
                        
                        // Also store for final transcription (complete file after recording stops)
                        this.audioChunks.push(event.data);
                    }
                };
                
                console.log('Microphone initialized successfully');
                
                // Debug MediaRecorder
                console.log('MediaRecorder initial state:', this.mediaRecorder.state);
                
                // Add event listener to debug state changes
                this.mediaRecorder.addEventListener('start', () => {
                    console.log('MediaRecorder started');
                });
                
                this.mediaRecorder.addEventListener('stop', () => {
                    console.log('MediaRecorder stopped, chunks collected:', this.audioChunks.length);
                });
                
            } catch (error) {
                console.error('Error accessing microphone:', error);
                this.status = 'error';
            }
        },

        // async $_initializeVAD() {
        //     try {
        //         // VAD library should now be loaded
        //         if (!window.vad) {
        //             throw new Error('VAD library not available');
        //         }

        //         this.vad = await window.vad.MicVAD.new({
        //             // If bundling locally, specify paths:
        //             baseAssetPath: "/plugins/asrjs/static/vad-assets",
        //             onnxWASMBasePath: "/plugins/asrjs/static/onnx-wasm",
                    
        //             // VAD configuration
        //             positiveSpeechThreshold: 0.5,
        //             negativeSpeechThreshold: 0.35,
        //             redemptionFrames: 8,
        //             preSpeechPadFrames: 1,
        //             minSpeechFrames: 3,
                    
        //             // Callbacks
        //             onSpeechStart: () => {
        //                 console.log("Speech started");
        //                 this.audioChunks = [];
        //                 if (this.continuous) {
        //                     this.status = 'recording';
        //                     this.audio.on.play();
        //                 }
        //             },
                    
        //             onSpeechEnd: (audio) => {
        //                 console.log("Speech ended", audio);
        //                 if (this.continuous || this.status === 'recording') {
        //                     this.$_processAudio(audio);
        //                     this.audio.off.play();
        //                 }
        //             },
                    
        //             onVADMisfire: () => {
        //                 console.log("VAD misfire - false positive");
        //                 this.status = 'empty';
        //                 this.audio.off.play();
        //                 setTimeout(() => {
        //                     this.status = 'listening';
        //                 }, 500);
        //             }
        //         });

        //         this.vadInitialized = true;
        //         this.status = 'ready';
        //         console.log('VAD initialized successfully');
                
        //     } catch (error) {
        //         console.error('Failed to initialize VAD:', error);
        //         this.status = 'error';
        //     }
        // },

        // async $_processAudio(audioData) {
        //     // Convert Float32Array audio to WAV blob
        //     const wavBlob = this.$_audioToWav(audioData);
            
        //     // Send to backend for transcription
        //     this.sendMsgToBackend({
        //         action: 'transcribe_audio',
        //         audio: await this.$_blobToBase64(wavBlob)
        //     });
            
        //     this.status = 'transcribing';
        // },

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

        $_writeWavHeader(view, numberOfChannels, sampleRate, length) {
            // Write WAV file header
            view.setUint32(0, 0x46464949, true); // "RIFF"
            view.setUint32(4, 36 + length * numberOfChannels * 2, true); // File size + 36 (header)
            view.setUint32(8, 0x57415645, true); // "WAVE"
            view.setUint32(12, sampleRate, true); // Sample rate
            view.setUint32(16, 0x10000001, true); // PCM format
            view.setUint16(20, numberOfChannels, true); // Number of channels
            view.setUint32(22, sampleRate * 2, true); // Byte rate
            view.setUint16(34, numberOfChannels * 2, true); // Block align
            view.setUint32(36, 0x61746164, true); // "data"
            view.setUint32(40, length * numberOfChannels * 2, true); // Data size
        },

        $_writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        },

        async $_checkSpeakerIDStatus() {
            // Check if speakerid plugin is active before sending chunks
            try {
                const response = await fetch('http://127.0.0.1:9714/api/plugins/speakerid/status');
                
                if (response.ok) {
                    const statusData = await response.json();
                    console.log('SpeakerID status:', statusData);
                    return true;
                } else {
                    console.warn('SpeakerID plugin not available, skipping chunk sending');
                    return false;
                }
            } catch (error) {
                console.error('Error checking speakerid status:', error);
                return false;
            }
        },

        async $_sendChunkToSpeakerID(chunk) {
            // Check if speakerid is available before sending chunks
            const isSpeakerIDActive = await this.$_checkSpeakerIDStatus();
            
            if (!isSpeakerIDActive) {
                console.log('SpeakerID not active, skipping chunk');
                return;
            }
            
            // Send audio chunk to speakerid HTTP endpoint (during recording)
            try {
                const formData = new FormData();
                formData.append('audio_data', chunk, 'chunk.webm');
                
                const response = await fetch('http://127.0.0.1:9714/api/plugins/speakerid/process_audio', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    console.error('Error sending audio chunk to speakerid:', response.status);
                }
            } catch (error) {
                console.error('Error sending chunk to speakerid:', error);
            }
        },

        async $_startRecording() {
            // Start MediaRecorder to actually collect audio chunks
            if (this.mediaRecorder && this.mediaRecorder.state === 'inactive') {
                this.mediaRecorder.start(100); // Request data every 100ms
                console.log('MediaRecorder started');
            }
            
            // Also notify backend via FastAPI endpoint
            try {
                const response = await fetch('http://127.0.0.1:9714/api/plugins/asrjs/start_recording', {
                    method: 'POST'
                });
                
                if (response.ok) {
                    console.log('Recording started');
                } else {
                    console.error('Error starting recording:', response.status);
                }
            } catch (error) {
                console.error('Error starting recording:', error);
            }
        },

        async $_stopRecording() {
            // Stop MediaRecorder to stop collecting audio chunks
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                this.mediaRecorder.stop();
                console.log('MediaRecorder stopped, chunks collected:', this.audioChunks.length);
            }
            
            // Also notify backend via FastAPI endpoint
            try {
                const response = await fetch('http://127.0.0.1:9714/api/plugins/asrjs/stop_recording', {
                    method: 'POST'
                });
                
                if (response.ok) {
                    console.log('Recording stopped');
                } else {
                    console.error('Error stopping recording:', response.status);
                }
            } catch (error) {
                console.error('Error stopping recording:', error);
            }
        },



        async $_sendAudioToTranscribe(audioBlob) {
            // Send complete audio to ASR transcription endpoint
            try {
                console.log('Sending audio to transcribe:', {
                    blobSize: audioBlob.size,
                    blobType: audioBlob.type
                });
                
                const formData = new FormData();
                formData.append('audio_file', audioBlob, 'recording.webm');
                
                const response = await fetch('http://127.0.0.1:9714/api/plugins/asrjs/transcribe', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('Transcription result:', result);
                } else {
                    console.error('Error transcribing audio:', response.status, await response.text());
                }
            } catch (error) {
                console.error('Error sending audio to transcribe:', error);
            }
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
            
            // VAD functionality commented out
            // if (this.continuous) {
            //     // Start VAD listening
            //     if (this.vad && this.vadInitialized) {
            //         this.vad.start();
            //         this.status = 'listening';
            //     }
            // } else {
            //     // Pause VAD
            //     if (this.vad) {
            //         this.vad.pause();
            //         this.status = 'ready';
            //     }
            // }
            
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
                if (data.type === "transcription_result") {
                    // Handle transcription result from backend
                    console.log('Transcription result:', data.text);
                    if (data.text && data.text.trim()) {
                        this.status = 'listening';
                    }
                }
                if (data.status) {
                    this.status = data.status;
                }
            } catch (e) {
                console.error("Error parsing message:", e);
            }
        },

        async $_handleMicClick() {
            console.log('$_handleMicClick called', {
                status: this.status,
                continuous: this.continuous,
                chunksLength: this.audioChunks.length
            });
            
            if (!this.continuous) {
                if (this.status === 'listening' || this.status === 'ready') {
                    // Manual push-to-talk: start recording
                    this.status = 'recording';
                    await this.$_startRecording();
                } else if (this.status === 'recording') {
                    // Stop recording first
                    await this.$_stopRecording();
                    
                    // Send complete audio for transcription AFTER recording stops
                    if (this.audioChunks.length > 0) {
                        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                        await this.$_sendAudioToTranscribe(audioBlob);
                    }
                    else{
                        console.warn("No audio chunks to send for transcription");
                    }
                    
                    // Update status and clear audio chunks
                    this.status = 'listening';
                    this.audioChunks = [];
                }
            } else {
                console.warn("Cannot click when in continuous mode");
            }
        },
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