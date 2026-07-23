class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 4096;
        this.recordingBuffer = [];
        this.speakerIdBuffer = [];
        this.speakerIdEnabled = false;  // Voice-profiles gate: don't capture/downsample unless enabled
        this.wakewordBuffer = [];  // Buffer for wakeword detection
        this.nativeSampleRate = sampleRate;
        this.targetSampleRate = 16000;
        this.chunkDuration = 3.0;
        this.wakewordChunkDuration = 0.08;  // 80ms chunks for wakeword detection

        // Handle messages from main thread
        this.isRecording = false;
        this.wakewordEnabled = false;  // Wakeword detection state
        this.port.onmessage = (event) => {
            if (event.data.type === 'clear-buffers') {
                this.recordingBuffer = [];
                this.speakerIdBuffer = [];
                this.wakewordBuffer = [];
            } else if (event.data.type === 'start-recording') {
                this.isRecording = true;
            } else if (event.data.type === 'stop-recording') {
                this.isRecording = false;
                // Flush the partial tail accumulated since the last 4096-boundary audio-data
                // post, then signal completion so the main thread can build the WAV without
                // losing the end (it only receives audio-data on exact bufferSize boundaries).
                const remainder = this.recordingBuffer.length % this.bufferSize;
                if (remainder > 0) {
                    this.port.postMessage({
                        type: 'audio-data',
                        data: this.recordingBuffer.slice(-remainder)
                    });
                }
                this.port.postMessage({ type: 'recording-stopped' });
            } else if (event.data.type === 'enable-wakeword') {
                this.wakewordEnabled = true;
                this.wakewordBuffer = [];  // Clear buffer when enabling
            } else if (event.data.type === 'disable-wakeword') {
                this.wakewordEnabled = false;
                this.wakewordBuffer = [];
            } else if (event.data.type === 'enable-speakerid') {
                this.speakerIdEnabled = true;
            } else if (event.data.type === 'disable-speakerid') {
                this.speakerIdEnabled = false;
                this.speakerIdBuffer = [];
            }
        };
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (!input || !input[0]) return true;

        const inputChannel = input[0];

        // Always capture audio for wakeword detection when enabled (even when not recording)
        if (this.wakewordEnabled) {
            // Downsample for wakeword detection
            const wakewordData = this.downsampleAudio(inputChannel, this.nativeSampleRate, this.targetSampleRate);
            this.wakewordBuffer.push(...wakewordData);

            // Check if we have enough data for a wakeword chunk (80ms at 16kHz = 1280 samples)
            const wakewordChunkSize = Math.floor(this.targetSampleRate * this.wakewordChunkDuration);
            if (this.wakewordBuffer.length >= wakewordChunkSize) {
                const chunk = this.wakewordBuffer.slice(0, wakewordChunkSize);
                this.wakewordBuffer = this.wakewordBuffer.slice(wakewordChunkSize);

                // Convert to Int16 for sending to backend
                const int16Chunk = new Int16Array(chunk.length);
                for (let i = 0; i < chunk.length; i++) {
                    int16Chunk[i] = Math.max(-32768, Math.min(32767, Math.floor(chunk[i] * 32767)));
                }

                // Send chunk to main thread for wakeword detection
                this.port.postMessage({
                    type: 'wakeword-chunk',
                    data: int16Chunk
                });
            }
        }

        // Downsample for speaker ID — runs whenever the voice-profiles gate is on,
        // NOT gated on recording. This MUST precede the isRecording early-return below:
        // in continuous mode the VAD drives capture and start/stop-recording is never
        // posted, so guarding this on isRecording means zero speakerid chunks ever
        // reach the backend in continuous mode. Mirrors the wakeword block above.
        // The main thread also guards the POST; this just skips the downsample when off.
        if (this.speakerIdEnabled) {
            const downsampledData = this.downsampleAudio(inputChannel, this.nativeSampleRate, this.targetSampleRate);
            this.speakerIdBuffer.push(...downsampledData);

            // Check if we have enough data for a chunk (3 seconds at 16kHz)
            const chunkSize = Math.floor(this.targetSampleRate * this.chunkDuration);
            if (this.speakerIdBuffer.length >= chunkSize) {
                const chunk = this.speakerIdBuffer.slice(0, chunkSize);
                this.speakerIdBuffer = this.speakerIdBuffer.slice(chunkSize); // Remove used portion

                // Send chunk to main thread
                this.port.postMessage({
                    type: 'speakerid-chunk',
                    data: chunk
                });
            }
        }

        // Everything below is recording-only (push-to-talk native-rate capture).
        if (!this.isRecording) return true;

        // Add current frame to recording buffer (for native rate recording)
        for (let i = 0; i < inputChannel.length; i++) {
            this.recordingBuffer.push(inputChannel[i]);
        }

        // Also send raw audio data periodically for visualization/monitoring
        if (this.recordingBuffer.length % this.bufferSize === 0) {
            this.port.postMessage({
                type: 'audio-data',
                data: this.recordingBuffer.slice(-this.bufferSize)
            });
        }

        return true;
    }
    
    downsampleAudio(audioData, inputSampleRate, outputSampleRate) {
        // Simple downsampling by selecting every Nth sample
        const ratio = inputSampleRate / outputSampleRate;
        const outputLength = Math.floor(audioData.length / ratio);
        const outputData = new Float32Array(outputLength);
        
        for (let i = 0; i < outputLength; i++) {
            const inputIndex = Math.floor(i * ratio);
            outputData[i] = audioData[inputIndex];
        }
        
        return outputData;
    }
    
    clearBuffers() {
        this.recordingBuffer = [];
        this.speakerIdBuffer = [];
    }
}

registerProcessor('audio-processor', AudioProcessor);
