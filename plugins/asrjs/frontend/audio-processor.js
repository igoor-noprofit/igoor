class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 4096;
        this.recordingBuffer = [];
        this.speakerIdBuffer = [];
        this.nativeSampleRate = sampleRate;
        this.targetSampleRate = 16000;
        this.chunkDuration = 3.0;
        
        // Handle messages from main thread
        this.isRecording = false;
        this.port.onmessage = (event) => {
            if (event.data.type === 'clear-buffers') {
                this.recordingBuffer = [];
                this.speakerIdBuffer = [];
            } else if (event.data.type === 'start-recording') {
                this.isRecording = true;
            } else if (event.data.type === 'stop-recording') {
                this.isRecording = false;
            }
        };
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (!input || !input[0] || !this.isRecording) return true;
        
        const inputChannel = input[0];
        
        // Add current frame to recording buffer (for native rate recording)
        for (let i = 0; i < inputChannel.length; i++) {
            this.recordingBuffer.push(inputChannel[i]);
        }
        
        // Downsample for speakerid
        const downsampledData = this.downsampleAudio(inputChannel, this.nativeSampleRate, this.targetSampleRate);
        this.speakerIdBuffer.push(...downsampledData);
        
        // Check if we have enough data for a chunk
        const chunkSize = Math.floor(this.targetSampleRate * this.chunkDuration); // 3 seconds at 16kHz
        if (this.speakerIdBuffer.length >= chunkSize) {
            const chunk = this.speakerIdBuffer.slice(0, chunkSize);
            this.speakerIdBuffer = this.speakerIdBuffer.slice(chunkSize); // Remove used portion
            
            // Send chunk to main thread
            this.port.postMessage({
                type: 'speakerid-chunk',
                data: chunk
            });
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
