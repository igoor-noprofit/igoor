"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudioNodeVAD = exports.MicVAD = exports.getDefaultRealTimeVADOptions = exports.ort = exports.DEFAULT_MODEL = void 0;
const ortInstance = __importStar(require("onnxruntime-web"));
const default_model_fetcher_1 = require("./default-model-fetcher");
const frame_processor_1 = require("./frame-processor");
const logging_1 = require("./logging");
const messages_1 = require("./messages");
const models_1 = require("./models");
const resampler_1 = require("./resampler");
exports.DEFAULT_MODEL = "legacy";
exports.ort = ortInstance;
const workletFile = "vad.worklet.bundle.min.js";
const sileroV5File = "silero_vad_v5.onnx";
const sileroLegacyFile = "silero_vad_legacy.onnx";
const getDefaultRealTimeVADOptions = (model) => {
    return {
        ...frame_processor_1.defaultFrameProcessorOptions,
        onFrameProcessed: (_probabilities, _frame) => { },
        onVADMisfire: () => {
            logging_1.log.debug("VAD misfire");
        },
        onSpeechStart: () => {
            logging_1.log.debug("Detected speech start");
        },
        onSpeechEnd: () => {
            logging_1.log.debug("Detected speech end");
        },
        onSpeechRealStart: () => {
            logging_1.log.debug("Detected real speech start");
        },
        baseAssetPath: "./",
        onnxWASMBasePath: "./",
        model: model,
        workletOptions: {},
        getStream: async () => {
            return await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    autoGainControl: true,
                    noiseSuppression: true,
                },
            });
        },
        pauseStream: async (_stream) => {
            _stream.getTracks().forEach((track) => {
                track.stop();
            });
        },
        resumeStream: async (_stream) => {
            return await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    autoGainControl: true,
                    noiseSuppression: true,
                },
            });
        },
        ortConfig: (ort) => {
            ort.env.logLevel = "error";
        },
        startOnLoad: true,
    };
};
exports.getDefaultRealTimeVADOptions = getDefaultRealTimeVADOptions;
class MicVAD {
    static async new(options = {}) {
        const fullOptions = {
            ...(0, exports.getDefaultRealTimeVADOptions)(options.model ?? exports.DEFAULT_MODEL),
            ...options,
        };
        (0, frame_processor_1.validateOptions)(fullOptions);
        const audioContext = new AudioContext();
        const audioNodeVAD = await AudioNodeVAD.new(audioContext, fullOptions);
        const micVad = new MicVAD(fullOptions, audioContext, audioNodeVAD);
        if (fullOptions.startOnLoad) {
            try {
                await micVad.start();
            }
            catch (e) {
                console.error("Error starting micVad", e);
            }
        }
        return micVad;
    }
    constructor(options, audioContext, audioNodeVAD, listening = false) {
        this.options = options;
        this.audioContext = audioContext;
        this.audioNodeVAD = audioNodeVAD;
        this.listening = listening;
        this.initialized = false;
        this.pause = () => {
            if (this.stream) {
                this.options.pauseStream(this.stream);
            }
            this.audioNodeVAD.pause();
            this.listening = false;
        };
        this.resume = async () => {
            if (!this.stream) {
                console.warn("Stream not initialized");
                return;
            }
            this.stream = await this.options.resumeStream(this.stream);
            if (this.sourceNode) {
                this.sourceNode.disconnect();
            }
            this.sourceNode = new MediaStreamAudioSourceNode(this.audioContext, {
                mediaStream: this.stream,
            });
            this.audioNodeVAD.receive(this.sourceNode);
        };
        this.start = async () => {
            if (!this.initialized) {
                this.initialized = true;
                this.stream = await this.options.getStream();
                this.sourceNode = new MediaStreamAudioSourceNode(this.audioContext, {
                    mediaStream: this.stream,
                });
                this.audioNodeVAD.receive(this.sourceNode);
            }
            if (!this.stream?.active) {
                await this.resume();
                this.audioNodeVAD.start();
                this.listening = true;
            }
            else {
                this.audioNodeVAD.start();
                this.listening = true;
            }
        };
        this.destroy = () => {
            if (this.listening) {
                this.pause();
            }
            if (this.stream) {
                this.options.pauseStream(this.stream);
            }
            else {
                console.warn("Stream not initialized");
            }
            if (this.sourceNode) {
                this.sourceNode.disconnect();
            }
            else {
                console.warn("Source node not initialized");
            }
            this.audioNodeVAD.destroy();
            this.audioContext.close();
        };
        this.setOptions = (options) => {
            this.audioNodeVAD.setFrameProcessorOptions(options);
        };
    }
}
exports.MicVAD = MicVAD;
class AudioNodeVAD {
    static async new(ctx, options = {}) {
        const fullOptions = {
            ...(0, exports.getDefaultRealTimeVADOptions)(options.model ?? exports.DEFAULT_MODEL),
            ...options,
        };
        (0, frame_processor_1.validateOptions)(fullOptions);
        exports.ort.env.wasm.wasmPaths = fullOptions.onnxWASMBasePath;
        if (fullOptions.ortConfig !== undefined) {
            fullOptions.ortConfig(exports.ort);
        }
        const modelFile = fullOptions.model === "v5" ? sileroV5File : sileroLegacyFile;
        const modelURL = fullOptions.baseAssetPath + modelFile;
        const modelFactory = fullOptions.model === "v5" ? models_1.SileroV5.new : models_1.SileroLegacy.new;
        let model;
        try {
            model = await modelFactory(exports.ort, () => (0, default_model_fetcher_1.defaultModelFetcher)(modelURL));
        }
        catch (e) {
            console.error(`Encountered an error while loading model file ${modelURL}`);
            throw e;
        }
        const frameSamples = fullOptions.model === "v5" ? 512 : 1536;
        const msPerFrame = frameSamples / 16;
        const frameProcessor = new frame_processor_1.FrameProcessor(model.process, model.reset_state, {
            positiveSpeechThreshold: fullOptions.positiveSpeechThreshold,
            negativeSpeechThreshold: fullOptions.negativeSpeechThreshold,
            redemptionMs: fullOptions.redemptionMs,
            preSpeechPadMs: fullOptions.preSpeechPadMs,
            minSpeechMs: fullOptions.minSpeechMs,
            submitUserSpeechOnPause: fullOptions.submitUserSpeechOnPause,
        }, msPerFrame);
        const audioNodeVAD = new AudioNodeVAD(ctx, fullOptions, frameProcessor, frameSamples, msPerFrame);
        await audioNodeVAD.setupAudioNode();
        return audioNodeVAD;
    }
    constructor(ctx, options, frameProcessor, frameSamples, msPerFrame) {
        this.ctx = ctx;
        this.options = options;
        this.frameSamples = frameSamples;
        this.msPerFrame = msPerFrame;
        this.pause = () => {
            this.frameProcessor.pause(this.handleFrameProcessorEvent);
        };
        this.start = () => {
            this.frameProcessor.resume();
        };
        this.receive = (node) => {
            node.connect(this.audioNode);
        };
        this.processFrame = async (frame) => {
            await this.frameProcessor.process(frame, this.handleFrameProcessorEvent);
        };
        this.handleFrameProcessorEvent = (ev) => {
            switch (ev.msg) {
                case messages_1.Message.FrameProcessed:
                    this.options.onFrameProcessed(ev.probs, ev.frame);
                    break;
                case messages_1.Message.SpeechStart:
                    this.options.onSpeechStart();
                    break;
                case messages_1.Message.SpeechRealStart:
                    this.options.onSpeechRealStart();
                    break;
                case messages_1.Message.VADMisfire:
                    this.options.onVADMisfire();
                    break;
                case messages_1.Message.SpeechEnd:
                    this.options.onSpeechEnd(ev.audio);
                    break;
            }
        };
        this.destroy = () => {
            if (this.audioNode instanceof AudioWorkletNode) {
                this.audioNode.port.postMessage({
                    message: messages_1.Message.SpeechStop,
                });
            }
            this.audioNode.disconnect();
            this.gainNode?.disconnect();
        };
        this.setFrameProcessorOptions = (options) => {
            this.frameProcessor.options = {
                ...this.frameProcessor.options,
                ...options,
            };
        };
        this.frameProcessor = frameProcessor;
    }
    async setupAudioNode() {
        const hasAudioWorklet = "audioWorklet" in this.ctx && typeof AudioWorkletNode === "function";
        if (hasAudioWorklet) {
            try {
                const workletURL = this.options.baseAssetPath + workletFile;
                await this.ctx.audioWorklet.addModule(workletURL);
                const workletOptions = this.options.workletOptions ?? {};
                workletOptions.processorOptions = {
                    ...(workletOptions.processorOptions ?? {}),
                    frameSamples: this.frameSamples,
                };
                this.audioNode = new AudioWorkletNode(this.ctx, "vad-helper-worklet", workletOptions);
                this.audioNode.port.onmessage = async (ev) => {
                    switch (ev.data?.message) {
                        case messages_1.Message.AudioFrame:
                            let buffer = ev.data.data;
                            if (!(buffer instanceof ArrayBuffer)) {
                                buffer = new ArrayBuffer(ev.data.data.byteLength);
                                new Uint8Array(buffer).set(new Uint8Array(ev.data.data));
                            }
                            const frame = new Float32Array(buffer);
                            await this.processFrame(frame);
                            break;
                    }
                };
                return;
            }
            catch (e) {
                console.log("AudioWorklet setup failed, falling back to ScriptProcessor", e);
            }
        }
        // Initialize resampler for ScriptProcessor
        this.resampler = new resampler_1.Resampler({
            nativeSampleRate: this.ctx.sampleRate,
            targetSampleRate: 16000,
            targetFrameSize: this.frameSamples ?? 480,
        });
        // Fallback to ScriptProcessor
        const bufferSize = 4096; // Increased for more stable processing
        this.audioNode = this.ctx.createScriptProcessor(bufferSize, 1, 1);
        // Create a gain node with zero gain to handle the audio chain
        this.gainNode = this.ctx.createGain();
        this.gainNode.gain.value = 0;
        let processingAudio = false;
        this.audioNode.onaudioprocess = async (e) => {
            if (processingAudio)
                return;
            processingAudio = true;
            try {
                const input = e.inputBuffer.getChannelData(0);
                const output = e.outputBuffer.getChannelData(0);
                output.fill(0);
                // Process through resampler
                if (this.resampler) {
                    const frames = this.resampler.process(input);
                    for (const frame of frames) {
                        await this.processFrame(frame);
                    }
                }
            }
            catch (error) {
                console.error("Error processing audio:", error);
            }
            finally {
                processingAudio = false;
            }
        };
        // Connect the audio chain
        this.audioNode.connect(this.gainNode);
        this.gainNode.connect(this.ctx.destination);
    }
}
exports.AudioNodeVAD = AudioNodeVAD;
//# sourceMappingURL=real-time-vad.js.map