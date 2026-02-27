<template>
    <div class="asrvosk-plugin">
        <div v-if="hasError" class="error-banner">
            {{ errorMessage }}
        </div>
        <div  v-if="!hasError" class="mic" :class="[status, { 'clickable': !continuous }]" @click="$_handleMicClick">
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
            audioChunks: [], // Store audio chunks for transcription
            speakerIdAvailable: false, // Cache speakerid availability
            audioContext: null,
            processor: null,
            source: null,
            recordingBuffer: [], // Buffer for native frequency audio
            isRecording: false,
            chunkInterval: null,
            nativeSampleRate: null, // Store the actual native sample rate (typically 48kHz)
            speakerIdBuffer: [], // Buffer for downsampled audio for speakerid
            lastChunkSentTime: 0, // Track when we last sent a chunk to speakerid
            chunkDuration: 3.0 // Fixed chunk duration in seconds for speakerid
        };
    },
    computed: {
        hasError() {
            return Boolean(this.error);
        },
        errorMessage() {
            if (!this.error) {
                return '';
            }
            return this.error.message || this.t('Microphone access problem. Verify that Windows has access to your microphone, then restart IGOOR.');
        }
    },
    created() {
        this.audio = {
            on: new Audio('/plugins/asrvosk/samples/on.wav'),
            off: new Audio('/plugins/asrvosk/samples/off.wav')
        };
        Object.values(this.audio).forEach(audio => audio.load());
    },
    async mounted() {
        // Load settings directly via REST API
        try {
            const settings = await this.callPluginRestEndpoint('asrjs', 'settings');
            console.log('ASRJS settings received:', settings);
            this.settings = settings;
            this.continuous = settings.continuous || false;
            if (settings.shortcut) {
                console.log('ASRJS SHORTCUT:', settings.shortcut);
                this.keyboardShortcut = settings.shortcut;
            }
        } catch (error) {
            console.error('Error loading settings via REST:', error);
        }

        window.addEventListener('keydown', this.$_handleKeyPress);
        // Load VAD library dynamically, then initialize - COMMENTED OUT
        // await this.$_loadVADLibrary();

        // Set status to listening since we're not using VAD
        this.status = 'listening';

        // Check speakerid availability during initialization
        await this.$_checkSpeakerIdAvailability();

        // Initialize microphone access
        await this.$_initializeMicrophone();
    },
    beforeDestroy() {
        window.removeEventListener('keydown', this.$_handleKeyPress);
        
        // Cleanup VAD - COMMENTED OUT
        // if (this.vad) {
        //     this.vad.destroy();
        // }
        
        // Cleanup Web Audio API components
        if (this.processor) {
            this.processor.disconnect();
        }
        if (this.source) {
            this.source.disconnect();
        }
        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }
        if (this.chunkInterval) {
            clearInterval(this.chunkInterval);
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

        async $_initializeMicrophoneMinimal() {
            try {
                console.log('Attempting microphone initialization with minimal constraints...');
                
                // Try with very minimal constraints - let browser choose everything
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: true  // Just ask for audio, no specific constraints
                });
                
                // Verify actual sample rate from stream
                const audioTrack = stream.getAudioTracks()[0];
                const settings = audioTrack.getSettings();
                console.log('Microphone initialized with minimal constraints at:', settings.sampleRate);
                
                this.mediaStream = stream;
                this.nativeSampleRate = settings.sampleRate || 48000;
                
                // Initialize Web Audio API
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ 
                    sampleRate: this.nativeSampleRate 
                });
                
                this.source = this.audioContext.createMediaStreamSource(stream);
                
                // Load and start AudioWorklet processor
                await this.audioContext.audioWorklet.addModule('/plugins/asrjs/frontend/audio-processor.js');
                this.processor = new AudioWorkletNode(this.audioContext, 'audio-processor');
                
                // Handle messages from AudioWorklet
                this.processor.port.onmessage = (event) => {
                    if (event.data.type === 'speakerid-chunk') {
                        // Send chunk to speakerid
                        this.$_sendFixedChunkToSpeakerID(event.data.data);
                    } else if (event.data.type === 'audio-data') {
                        // Store audio data for final WAV file
                        this.recordingBuffer = this.recordingBuffer.concat(event.data.data);
                    }
                };
                
                // Connect the audio nodes
                this.source.connect(this.processor);
                this.processor.connect(this.audioContext.destination);
                
                // Set up audio level monitoring
                const analyser = this.audioContext.createAnalyser();
                analyser.fftSize = 256;
                this.source.connect(analyser);
                
                const dataArray = new Uint8Array(analyser.frequencyBinCount);
                
                // Monitor audio levels
                let levelCount = 0;
                const monitorAudio = () => {
                    analyser.getByteFrequencyData(dataArray);
                    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
                    levelCount++;
                    if (average > 5 && levelCount % 30 === 0) {
                        console.log(`Audio level: ${average.toFixed(2)} (0-255 scale) at ${this.nativeSampleRate} Hz`);
                    }
                    requestAnimationFrame(monitorAudio);
                };
                monitorAudio();
                
                console.log('Web Audio API initialized successfully with minimal constraints');
                this.status = 'listening';  // Set status to listening after successful init
                
            } catch (error) {
                console.error('Failed to initialize microphone even with minimal constraints:', error);
                this.status = 'error';
            }
        },

        async $_initializeMicrophone() {
            try {
                // Request microphone permission at native frequency - no sample rate constraint
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        channelCount: 1,
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false,
                        volume: 1.0,  // Force maximum volume
                        latency: 0    // Minimal latency
                    } 
                });
                
                // Verify actual sample rate from stream
                const audioTrack = stream.getAudioTracks()[0];
                const settings = audioTrack.getSettings();
                console.log('Microphone native sample rate:', settings.sampleRate);
                console.log('Browser negotiated constraints:', settings);
                
                this.mediaStream = stream;
                
                // Store native sample rate (typically 48kHz)
                this.nativeSampleRate = settings.sampleRate || 48000;
                console.log(`Recording at native frequency: ${this.nativeSampleRate}Hz`);
                
                // Initialize Web Audio API at native frequency
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ 
                    sampleRate: this.nativeSampleRate 
                });
                
                this.source = this.audioContext.createMediaStreamSource(stream);
                
                // Load and start AudioWorklet processor
                await this.audioContext.audioWorklet.addModule('/plugins/asrjs/frontend/audio-processor.js');
                this.processor = new AudioWorkletNode(this.audioContext, 'audio-processor');
                
                // Handle messages from AudioWorklet
                this.processor.port.onmessage = (event) => {
                    if (event.data.type === 'speakerid-chunk') {
                        // Send chunk to speakerid
                        this.$_sendFixedChunkToSpeakerID(event.data.data);
                    } else if (event.data.type === 'audio-data') {
                        // Store audio data for final WAV file
                        this.recordingBuffer = this.recordingBuffer.concat(event.data.data);
                    }
                };
                
                // Connect the audio nodes
                this.source.connect(this.processor);
                this.processor.connect(this.audioContext.destination);
                
                // Set up audio level monitoring
                const analyser = this.audioContext.createAnalyser();
                analyser.fftSize = 256;
                this.source.connect(analyser);
                
                const dataArray = new Uint8Array(analyser.frequencyBinCount);
                
                // Monitor audio levels
                let levelCount = 0;
                const monitorAudio = () => {
                    analyser.getByteFrequencyData(dataArray);
                    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
                    levelCount++;
                    if (average > 5 && levelCount % 30 === 0) { // Log every ~30 frames when audio detected
                        console.log(`Audio level: ${average.toFixed(2)} (0-255 scale) at ${this.nativeSampleRate} Hz`);
                    }
                    requestAnimationFrame(monitorAudio);
                };
                monitorAudio();
                
                console.log('Web Audio API initialized successfully at native frequency');
                console.log('Audio stream settings:', {
                    sampleRate: this.nativeSampleRate,
                    channelCount: settings.channelCount,
                    volume: settings.volume
                });
                
            } catch (error) {
                this.error = error;
                console.error('Error accessing microphone:', error);
                console.error('Error details:', {
                    name: error.name,
                    message: error.message,
                    constraint: error.constraint,
                    type: error.type
                });
                
                // Provide specific error messages based on error type
                if (error.name === 'NotAllowedError') {
                    console.error('Microphone access denied. Please allow microphone permissions.');
                } else if (error.name === 'NotFoundError') {
                    console.error('No microphone found. Please check your audio devices.');
                } else if (error.name === 'NotSupportedError') {
                    console.error('Microphone not supported or constraints not met.');
                } else if (error.name === 'OverconstrainedError') {
                    console.error('Requested audio constraints not supported by this device.');
                    // Try again with minimal constraints
                    console.log('Retrying with minimal constraints...');
                    await this.$_initializeMicrophoneMinimal();
                    return;
                }
                
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

        $_createWAVChunk(float32Array, sampleRate) {
            // Create a mini WAV file from a chunk of audio data
            const numChannels = 1;
            const bitsPerSample = 16;
            
            // Convert float32 to int16
            const int16Array = new Int16Array(float32Array.length);
            for (let i = 0; i < float32Array.length; i++) {
                const s = Math.max(-1, Math.min(1, float32Array[i]));
                int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Create WAV file buffer with proper header
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

        $_audioToWav(float32Array) {
            // Convert Float32Array to WAV format (use native sample rate)
            const sampleRate = this.nativeSampleRate || 48000;
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



        $_float32ToInt16(float32Array) {
            // Convert Float32Array to Int16Array (16-bit signed PCM)
            const int16Array = new Int16Array(float32Array.length);
            for (let i = 0; i < float32Array.length; i++) {
                const s = Math.max(-1, Math.min(1, float32Array[i]));
                int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            return int16Array;
        },

        async $_sendFixedChunkToSpeakerID(float32Chunk) {
            // Send fixed chunk to speakerid for identification
            if (!this.speakerIdAvailable) {
                console.log('SpeakerID not available, skipping chunk');
                return;
            }
            
            try {
                // Convert float32 to int16
                const int16Data = this.$_float32ToInt16(float32Chunk);
                
                // Convert to WAV format
                const wavBlob = this.$_createWAVChunk(float32Chunk, 16000);
                
                // Send to speakerid endpoint
                const formData = new FormData();
                formData.append('audio_file', wavBlob, 'chunk.wav');
                formData.append('sample_rate', '16000');
                
                const response = await fetch('http://127.0.0.1:9714/api/plugins/speakerid/process_audio_chunk', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('Fixed chunk sent to speakerid:', result);
                } else {
                    console.error('Error sending fixed chunk to speakerid:', response.status);
                }
            } catch (error) {
                console.error('Error sending fixed chunk to speakerid:', error);
            }
        },

        async $_checkSpeakerIdAvailability() {
            // Check speakerid availability up to 3 times during initialization
            let attempts = 0;
            const maxAttempts = 3;
            
            while (attempts < maxAttempts) {
                try {
                    const response = await this.callPluginRestEndpoint('speakerid', 'status');
                    
                    this.speakerIdAvailable = true;
                    console.log('SpeakerID plugin is available');
                    return;
                } catch (error) {
                    console.log(`SpeakerID check attempt ${attempts + 1} failed:`, error.message);
                }
                
                attempts++;
                if (attempts < maxAttempts) {
                    // Wait 1 second before next attempt
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            // If we get here, speakerid is not available after 3 attempts
            this.speakerIdAvailable = false;
            console.log('SpeakerID plugin is not available after 3 attempts');
        },

        async $_checkSpeakerIDStatus() {
            // Check if speakerid plugin is active before sending chunks
            try {
                const statusData = await this.callPluginRestEndpoint('speakerid', 'status');
                
                console.log('SpeakerID status:', statusData);
                return true;
            } catch (error) {
                console.warn('SpeakerID plugin not available, skipping chunk sending');
                console.warn('Error checking speakerid status:', error);
                return false;
            }
        },

        async $_sendAudioChunkToSpeakerID(audioBlob) {
            // Use cached speakerid availability (no API calls)
            if (!this.speakerIdAvailable) {
                console.log('SpeakerID not available (cached), skipping identification');
                return;
            }
            
            // Send audio chunk to speakerid for identification
            try {
                const formData = new FormData();
                formData.append('audio_file', audioBlob, 'chunk.wav');
                formData.append('sample_rate', this.nativeSampleRate.toString());  // Use native sample rate
                
                const response = await fetch('http://127.0.0.1:9714/api/plugins/speakerid/process_audio_chunk', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    console.error('Error sending audio chunk to speakerid:', response.status);
                } else {
                    const result = await response.json();
                    console.log('Speaker chunk identification result:', result);
                }
            } catch (error) {
                console.error('Error sending audio chunk to speakerid:', error);
            }
        },

        async $_sendAudioToSpeakerID(audioBlob) {
            return true;
            // Use cached speakerid availability (no API calls)
            if (!this.speakerIdAvailable) {
                console.log('SpeakerID not available (cached), skipping identification');
                return;
            }
            
            // Send complete audio file to speakerid for identification
            try {
                const formData = new FormData();
                formData.append('audio_file', audioBlob, 'recording.wav');
                formData.append('sample_rate', this.nativeSampleRate.toString());  // Use native sample rate
                
                const response = await fetch('http://127.0.0.1:9714/api/plugins/speakerid/identify_speaker', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    console.error('Error sending audio to speakerid:', response.status);
                } else {
                    const result = await response.json();
                    console.log('Speaker identification result:', result);
                }
            } catch (error) {
                console.error('Error sending audio to speakerid:', error);
            }
        },

        async $_startRecording() {
            // Start Web Audio API recording
            this.isRecording = true;
            this.recordingBuffer = [];
            this.audioChunks = [];
            this.speakerIdBuffer = []; // Clear speakerid buffer for new recording
            
            // Clear buffers in AudioWorklet and start recording
            if (this.processor) {
                this.processor.port.postMessage({ type: 'clear-buffers' });
                this.processor.port.postMessage({ type: 'start-recording' });
            }
            
            console.log(`Recording started at ${this.nativeSampleRate}Hz, sending ${this.chunkDuration}s chunks to speakerid`);
            
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
            // Stop Web Audio API recording
            this.isRecording = false;
            
            // Tell AudioWorklet to stop recording
            if (this.processor) {
                this.processor.port.postMessage({ type: 'stop-recording' });
            }
            
            console.log(`Recording stopped, collected ${this.recordingBuffer.length} native samples and ${this.speakerIdBuffer.length} downsampled samples`);
            
            // Send any remaining speakerid buffer if it has sufficient data
            const minChunkSize = Math.floor(16000 * 1.0); // Minimum 1 second
            if (this.speakerIdBuffer.length >= minChunkSize) {
                console.log(`Sending final partial chunk of ${this.speakerIdBuffer.length} samples to speakerid`);
                await this.$_sendFixedChunkToSpeakerID(this.speakerIdBuffer);
            }
            
            // Create final WAV file from complete recording buffer
            const finalWavBlob = this.$_audioToWav(this.recordingBuffer);
            
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
            
            return finalWavBlob;
        },



        async $_sendAudioToTranscribe(audioBlob) {
            // Send complete audio to ASR transcription endpoint
            try {
                console.log('Sending audio to transcribe:', {
                    blobSize: audioBlob.size,
                    blobType: audioBlob.type
                });
                
                const formData = new FormData();
                formData.append('audio_file', audioBlob, 'recording.wav');
                
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
            // console.log("Pressed combination:", pressedCombo + ", looking for:", this.keyboardShortcut);
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
            if (handled) {
                // Base component handled the message, check if it was settings
                const data = JSON.parse(event.data);
                if (data.settings) {
                    console.log('ASRJS SETTINGS:', data.settings);
                    this.settings = data.settings;
                    this.continuous = this.settings.continuous || false;
                    if (this.settings.shortcut) {
                        console.log('ASRJS SHORTCUT:', this.settings.shortcut);
                        this.keyboardShortcut = this.settings.shortcut;
                    }
                }
                return true;
            }
            console.log(this.$options.name + ' handling message');

            try {
                const data = JSON.parse(event.data);
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
                    const finalWavBlob = await this.$_stopRecording();
                    
                    // Send complete audio to BOTH APIs after recording stops
                    if (finalWavBlob && finalWavBlob.size > 0) {
                        // Send to ASR for transcription
                        await this.$_sendAudioToTranscribe(finalWavBlob);
                        
                        // Send to SpeakerID for identification
                        await this.$_sendAudioToSpeakerID(finalWavBlob);
                    }
                    else{
                        console.warn("No audio data to send for processing");
                    }
                    
                    // Update status and clear audio buffers
                    this.status = 'listening';
                    this.recordingBuffer = [];
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
    width: 120px;
    flex: 0 0 auto;
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