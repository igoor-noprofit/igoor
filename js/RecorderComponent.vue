<template>
    <div class="recorder">
        <div class="recorder__meter" v-if="showMeter">
            <canvas ref="meterCanvas" width="200" height="20"></canvas>
        </div>
        <div class="recorder__controls">
            <button type="button" @click="$_startRecording" :disabled="isRecording || loading">
                {{ isRecording ? uiLabels.recording : uiLabels.start }}
            </button>
            <button type="button" @click="$_stopRecording" :disabled="!isRecording">
                {{ uiLabels.stop }}
            </button>
            <button type="button" @click="$_playRecording" :disabled="!hasRecording || isRecording">
                {{ uiLabels.play }}
            </button>
            <button v-if="enableUpload" type="button" @click="$_uploadRecording" :disabled="!hasRecording || loading">
                {{ loading ? uiLabels.uploading : uiLabels.upload }}
            </button>
        </div>
        <p class="recorder__status">{{ statusMessage }}</p>
    </div>
</template>

<script>
let wavRecorderReady = false;
let RecorderCtor = null;

async function ensureWavRecorder() {
    if (wavRecorderReady && RecorderCtor) {
        return RecorderCtor;
    }
    // Use native MediaRecorder - server will handle WAV conversion
    if (window.MediaRecorder) {
        wavRecorderReady = true;
        RecorderCtor = window.MediaRecorder;
        return RecorderCtor;
    }
    throw new Error('MediaRecorder not available');
}

function trimEndpoint(url) {
    if (!url) {
        return '/api/plugins/recorder/audio';
    }
    return url.replace(/\/+$/, '');
}

function withSuffix(base, suffix = '') {
    return `${trimEndpoint(base)}${suffix}`;
}



module.exports = {
    name: 'RecorderComponent',
    props: {
        pluginName: { type: String, default: '' },
        uploadUrl: { type: String, default: '/api/plugins/recorder/audio' },
        enableUpload: { type: Boolean, default: true },
        showMeter: { type: Boolean, default: true },
        autoUpload: { type: Boolean, default: false },
        labels: { type: Object, default: () => ({}) }
    },
    data() {
        return {
            isRecording: false,
            hasRecording: false,
            loading: false,
            statusMessage: 'Ready to record',
            recordedBlob: null,
            mediaRecorder: null,
            audioContext: null,
            analyser: null,
            meterRAF: null,
            stream: null
        };
    },
    computed: {
        uiLabels() {
            return {
                start: 'Start recording',
                recording: 'Recording…',
                stop: 'Stop',
                play: 'Play',
                upload: 'Upload',
                uploading: 'Uploading…',
                ...this.labels
            };
        },
        baseEndpoint() {
            return trimEndpoint(this.uploadUrl);
        }
    },
    methods: {
        async $_startRecording() {
            if (this.isRecording || this.loading) {
                return;
            }
            try {
                const Recorder = await ensureWavRecorder();
                await this.$_initAudio(Recorder);
                this.mediaRecorder.start();
                this.isRecording = true;
                this.statusMessage = 'Recording in progress…';
                this.$emit('record-started');
            } catch (error) {
                console.error('Recorder start error', error);
                this.statusMessage = 'Unable to start recording';
                this.$emit('error', error);
                this.$_cleanupStream();
            }
        },
        $_stopRecording() {
            if (!this.isRecording || !this.mediaRecorder) {
                return;
            }
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.statusMessage = 'Recording stopped';
            this.$emit('record-stopped');
        },
        async $_playRecording() {
            if (!this.latestRecorderId && !this.recordedBlob) {
                this.statusMessage = 'No recording available';
                return;
            }
            
            try {
                let audioUrl;
                
                // If we have a recorder ID, fetch the converted WAV file from server
                if (this.latestRecorderId) {
                    // Construct the full URL properly
                    const baseUrl = window.location.origin;
                    audioUrl = `${baseUrl}/api/plugins/recorder/audio/${this.latestRecorderId}/file`;
                    console.log('Playing audio from URL:', audioUrl);
                } else {
                    // Fallback to local blob (may not work for all formats)
                    audioUrl = URL.createObjectURL(this.recordedBlob);
                    console.log('Playing local blob');
                }
                
                // Test the URL first
                if (this.latestRecorderId) {
                    try {
                        const testResponse = await fetch(audioUrl, { method: 'HEAD' });
                        console.log('Audio file HEAD response:', testResponse.status, testResponse.statusText);
                        if (!testResponse.ok) {
                            throw new Error(`Audio file not accessible (${testResponse.status})`);
                        }
                    } catch (testError) {
                        console.error('Audio file test failed:', testError);
                        throw testError;
                    }
                }
                
                const audio = new Audio(audioUrl);
                audio.play();
                this.statusMessage = 'Playing back…';
                
                // Clean up the object URL when playback ends (only for local blobs)
                audio.addEventListener('ended', () => {
                    if (!this.latestRecorderId) {
                        URL.revokeObjectURL(audioUrl);
                    }
                    this.statusMessage = 'Playback finished';
                });
                
                audio.addEventListener('error', (e) => {
                    if (!this.latestRecorderId) {
                        URL.revokeObjectURL(audioUrl);
                    }
                    console.error('Playback error:', e);
                    console.error('Audio element error details:', audio.error);
                    this.statusMessage = 'Playback failed';
                    this.$emit('error', new Error('Audio playback failed'));
                });
                
            } catch (error) {
                console.error('Playback error', error);
                this.statusMessage = `Playback failed: ${error.message}`;
                this.$emit('error', error);
            }
        },
        async $_uploadRecording(pluginOverride) {
            if (!this.recordedBlob || !this.enableUpload) {
                return;
            }
            const plugin = pluginOverride || this.pluginName;
            if (!plugin) {
                const err = new Error('Plugin name required');
                this.statusMessage = 'No plugin specified for upload';
                this.$emit('error', err);
                return;
            }
            this.loading = true;
            this.statusMessage = 'Uploading and converting to WAV…';
            try {
                const payload = await this.$_submitRecording(plugin, this.recordedBlob);
                this.latestRecorderId = payload?.id;
                this.$emit('uploaded', payload);
                this.statusMessage = 'Upload complete - ready for playback';
                return payload;
            } catch (error) {
                console.error('Upload error', error);
                this.statusMessage = 'Upload failed';
                this.$emit('error', error);
                throw error;
            } finally {
                this.loading = false;
            }
        },
        async $_submitRecording(plugin, blob) {
            const formData = new FormData();
            formData.append('plugin', plugin);
            
            // Use original extension - server will convert to WAV
            let extension = 'webm';
            if (blob.type) {
                const typeMap = {
                    'audio/webm': 'webm',
                    'audio/ogg': 'ogg',
                    'audio/mp4': 'm4a',
                    'audio/wav': 'wav'
                };
                extension = typeMap[blob.type] || 'webm';
            }
            
            formData.append('file', blob, `${plugin}_${Date.now()}.${extension}`);
            const response = await fetch(this.baseEndpoint, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => null);
                const message = detail?.detail || `Upload failed (${response.status})`;
                throw new Error(message);
            }
            return response.json().catch(() => null);
        },
        async $_fetchRecordings(pluginOverride, options = {}) {
            const plugin = pluginOverride || this.pluginName;
            const url = new URL(this.baseEndpoint, window.location.origin);
            if (plugin) {
                url.searchParams.set('plugin', plugin);
            }
            const response = await fetch(url.toString(), {
                method: 'GET',
                credentials: 'same-origin',
                signal: options.signal
            });
            if (!response.ok) {
                throw new Error(`Failed to load recordings (${response.status})`);
            }
            const payload = await response.json();
            if (options.emit !== false) {
                this.$emit('records', payload);
            }
            return payload;
        },
        async $_getRecordingMeta(recordId) {
            const response = await fetch(withSuffix(this.baseEndpoint, `/${recordId}`), {
                credentials: 'same-origin'
            });
            if (!response.ok) {
                throw new Error(`Recording ${recordId} not found (${response.status})`);
            }
            return response.json();
        },
        async $_downloadRecording(recordId) {
            const response = await fetch(withSuffix(this.baseEndpoint, `/${recordId}/file`), {
                credentials: 'same-origin'
            });
            if (!response.ok) {
                throw new Error(`Recording ${recordId} unavailable (${response.status})`);
            }
            return response.blob();
        },
        async $_initAudio(Recorder) {
            this.$_cleanupStream();
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Try to determine the best MIME type for the current browser
            let mimeType = 'audio/wav';
            const supportedTypes = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/ogg;codecs=opus',
                'audio/mp4',
                'audio/wav'
            ];
            
            for (const type of supportedTypes) {
                if (MediaRecorder.isTypeSupported(type)) {
                    mimeType = type;
                    break;
                }
            }
            
            try {
                this.mediaRecorder = new Recorder(this.stream, { mimeType });
            } catch (error) {
                console.warn('Failed to create MediaRecorder with MIME type:', mimeType, error);
                // Try without specifying MIME type
                this.mediaRecorder = new Recorder(this.stream);
            }
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data?.size > 0) {
                    this.recordedBlob = event.data;
                    this.hasRecording = true;
                    this.statusMessage = 'Recording ready - upload to enable playback';
                    this.$emit('recorded', event.data);
                    if (this.autoUpload) {
                        this.$_uploadRecording();
                    }
                }
            };
            this.mediaRecorder.onstop = () => {
                this.$_cleanupStream();
            };
            this.mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event);
                this.statusMessage = 'Recording error occurred';
                this.$emit('error', event.error || new Error('Recording error'));
            };
            this.$_setupMeter();
        },
        $_setupMeter() {
            if (!this.showMeter) {
                return;
            }
            if (!this.audioContext) {
                this.audioContext = new AudioContext();
            }
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            const source = this.audioContext.createMediaStreamSource(this.stream);
            source.connect(this.analyser);
            this.$_drawMeter();
        },
        $_drawMeter() {
            if (!this.analyser) {
                return;
            }
            const canvas = this.$refs.meterCanvas;
            if (!canvas) {
                return;
            }
            const ctx = canvas.getContext('2d');
            const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            const draw = () => {
                this.analyser.getByteFrequencyData(dataArray);
                let rms = 0;
                for (let i = 0; i < dataArray.length; i++) {
                    rms += dataArray[i] ** 2;
                }
                const volume = Math.sqrt(rms / dataArray.length) / 255;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                const color = volume > 0.8 ? '#f87171' : volume > 0.5 ? '#facc15' : '#34d399';
                ctx.fillStyle = color;
                ctx.fillRect(0, 0, volume * canvas.width, canvas.height);
                this.meterRAF = requestAnimationFrame(draw);
            };
            draw();
        },
        $_cleanupStream() {
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
            this.stream = null;
            if (this.meterRAF) {
                cancelAnimationFrame(this.meterRAF);
                this.meterRAF = null;
            }
            if (this.analyser) {
                this.analyser.disconnect();
                this.analyser = null;
            }
            if (!this.isRecording && !this.loading) {
                this.statusMessage = 'Ready to record';
            }
        }
    },
    beforeUnmount() {
        this.$_cleanupStream();
        if (this.mediaRecorder) {
            this.mediaRecorder.ondataavailable = null;
            this.mediaRecorder.onstop = null;
            this.mediaRecorder = null;
        }
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        this.recordedBlob = null;
    }
};
</script>


<style scoped>
.recorder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

.recorder__controls {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
}

.recorder__meter canvas {
    border: 1px solid #ccc;
    border-radius: 4px;
}

.recorder__status {
    font-size: 0.9rem;
    color: #6b7280;
    margin: 0;
}
</style>
