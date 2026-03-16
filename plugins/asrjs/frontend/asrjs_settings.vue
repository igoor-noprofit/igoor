<template>
    <div class="asrjs-plugin-settings form-grid bio-container">
        <div class="bio left">
            <!-- Model Provider -->
            <div class="form-label">{{t('Model provider')}}</div>
            <div class="form-input">
                <select name="model_provider" v-model="formData.model_provider" @change="onProviderChange">
                    <option value="groq">Groq</option>
                    <option value="mistral">Mistral (BETA)</option>
                </select>
            </div>
            <div class="form-note"></div>

            <!-- Model Name -->
            <div class="form-label">{{t('Model name')}}</div>
            <div class="form-input">
                <select name="model_name" v-model="formData.model_name">
                    <option value="whisper-large-v3" v-show="formData.model_provider === 'groq'">Whisper Large v3</option>
                    <option value="whisper-large-v3-turbo" v-show="formData.model_provider === 'groq'">Whisper Large v3 Turbo</option>
                    <option value="voxtral-mini-latest" v-show="formData.model_provider === 'mistral'">Voxtral Mini Latest</option>
                </select>
            </div>
            <div class="form-note"></div>

            <!-- MISTRAL API KEY -->
            <div class="form-label" v-show="formData.model_name === 'voxtral-mini-latest'">{{t('Voxtral API Key (BETA)')}}</div>
            <div class="form-input" v-show="formData.model_name === 'voxtral-mini-latest'">
                <input
                    type="password"
                    v-model="formData.voxtral_api_key"
                    :class="{'input-error': voxtralKeyError}"
                    :placeholder="t('Required for Voxtral')"
                    required
                />
            </div>
            <div class="form-note" :style="{color: voxtralKeyError ? '#ff6666' : undefined}" v-show="formData.model_name === 'voxtral-mini-latest'">
                {{ voxtralKeyError ? t('Mistral API Key is required') : t('Mistral API Key is required for Voxtral models') }}
            </div>

            <!-- Shortcut -->
            <div class="form-label">{{t('Microphone Activation Shortcut')}}</div>
            <div class="form-input" style="display: flex; align-items: center; gap: 8px;">
                <input
                    type="text"
                    readonly
                    :value="formData.shortcut"
                    @focus="startRecordingShortcut"
                    @keydown.prevent="recordShortcut"
                    @blur="stopRecordingShortcut"
                    v-bind:placeholder="t('Key shortcut')"
                    style="width: 180px;"
                    tabindex="0"
                />
                <button type="button" @click="clearShortcut" style="margin-left: 4px;" :disabled="!formData.shortcut">{{t('Clear')}}</button>
            </div>
            <div class="form-note">
                {{t('Click the box and press a key or combination (e.g., Ctrl+R) to set the shortcut.')}}
                <br>
                {{t('This keyboard combination STARTS / STOPS the speech detection process')}}
            </div>

            <!-- Microphone Volume Indicator -->
            <div class="form-label">{{t('Microphone Level')}}</div>
            <div class="form-input" style="display: flex; align-items: center; gap: 8px;">
                <div class="volume-meter">
                    <div class="volume-bar" :style="{ width: volumeLevel + '%' }"></div>
                </div>
                <span class="volume-value">{{ volumeLevel }}%</span>
            </div>
            <div class="form-note"></div>
            <!-- Continuous Mode -->
            <div class="form-label">{{t('Continuous Listening Mode')}}</div>
            <div class="form-input">
                <label class="toggle-switch">
                    <input type="checkbox" v-model="formData.continuous" />
                    <span class="toggle-slider"></span>
                </label>
                <span style="margin-left: 8px;">{{ formData.continuous ? t('Enabled') : t('Disabled') }}</span>
            </div>
            <div class="form-note">
                {{t('When enabled, the microphone listens continuously and automatically detects speech.')}}<br>
            </div>
        </div>

        <div class="bio right">
             <!-- Save Button -->
            <div class="form-label"></div>
            <div class="form-input">
                <SaveSettingsButton
                    :hasChanges="hasUnsavedChanges"
                    :loading="loading"
                    :t="t"
                    :lang="lang"
                    @save="checkBeforeUpdating"
                    @cancel="resetSettings"
                />
            </div>

            <!-- Speech Detection Threshold (only shown when continuous is enabled) -->
            <template v-if="formData.continuous">
                <div class="form-label">{{t('Speech Threshold')}}</div>
                <div class="form-input" style="display: flex; align-items: center; gap: 12px;">
                    <input
                        type="range"
                        min="0.2"
                        max="0.8"
                        step="0.05"
                        v-model.number="formData.positiveSpeechThreshold"
                        style="flex: 1 1 60%;"
                    />
                    <input
                        type="number"
                        v-model.number="formData.positiveSpeechThreshold"
                        step="0.05"
                        min="0.2"
                        max="0.8"
                        style="width: 60px;"
                    />
                </div>
                <div class="form-note">
                    {{t('Lower = more sensitive (may pick up noise), Higher = less sensitive (may miss soft speech)')}}
                </div>

                <!-- Pause Tolerance (redemptionFrames) -->
                <div class="form-label">{{t('Pause Tolerance')}}</div>
                <div class="form-input">
                    <select name="redemptionFrames" v-model.number="formData.redemptionFrames">
                        <option value="4">4 frames (~80ms) - Fast</option>
                        <option value="8">8 frames (~160ms) - Default</option>
                        <option value="12">12 frames (~240ms) - Medium</option>
                        <option value="16">16 frames (~320ms) - Slow</option>
                        <option value="24">24 frames (~480ms) - Very slow </option>
                    </select>
                </div>
                <!--div class="form-note">
                    {{t('How long to wait after speech stops before transcribing.')}}<br>
                    {{t('Higher values help with speakers who pause frequently.')}}
                </div-->

                <!-- Always Generate (bypass semantic VAD) -->
                <div class="form-label">{{t('Always generate predictions')}}</div>
                <div class="form-input">
                    <label class="toggle-switch">
                        <input type="checkbox" v-model="formData.always_generate" />
                        <span class="toggle-slider"></span>
                    </label>
                    <span style="margin-left: 8px;">{{ formData.always_generate ? t('Enabled') : t('Disabled') }}</span>
                </div>
            <!--div class="form-note">
                {{t('When enabled, bypasses the semantic VAD check and generates immediately after speech ends.')}}<br>
            </div-->
        </template>

        <!-- Wakeword Detection Section -->
        <template v-if="formData.continuous">
            <div class="form-label">{{t('Wakeword Detection')}}</div>
            <div class="form-input">
                <label class="toggle-switch">
                    <input type="checkbox" v-model="formData.wakeword_enabled" />
                    <span class="toggle-slider"></span>
                </label>
                <span style="margin-left: 8px;">{{ formData.wakeword_enabled ? t('Enabled') : t('Disabled') }}</span>
            </div>
            <!--div class="form-note">
                {{t('Say "Hey Igor" to activate voice recognition hands-free.')}}
            </div-->

            <!-- Wakeword Sensitivity (only shown when wakeword enabled) -->
            <template v-if="formData.wakeword_enabled">
                <div class="form-label">{{t('Wakeword Sensitivity')}}</div>
                <div class="form-input" style="display: flex; align-items: center; gap: 12px;">
                    <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.1"
                        v-model.number="formData.wakeword_sensitivity"
                        style="flex: 1 1 60%;"
                    />
                    <input
                        type="number"
                        v-model.number="formData.wakeword_sensitivity"
                        step="0.1"
                        min="0.1"
                        max="0.9"
                        style="width: 60px;"
                    />
                </div>
                <!--div class="form-note">
                    {{t('Lower = fewer false positives, Higher = more sensitive')}}<br>
                    {{t('Adjust based on your environment and microphone quality.')}}
                </div-->

                <!-- Wakeword Model Selection -->
                <div class="form-input" style="display: flex; align-items: center; gap: 8px;">
                    <select v-model="formData.wakeword_model" style="flex: 1;">
                        <option value="">{{t('Default model')}}</option>
                        <option v-for="model in customModels" :key="model" :value="model">{{ model }}</option>
                    </select>
                    <input
                        type="file"
                        ref="wakewordFileInput"
                        accept=".onnx"
                        style="display: none"
                        @change="handleWakewordFileSelect"
                    />
                    <button type="button" class="btn btn-primary" @click="$refs.wakewordFileInput.click()">
                        <i class="ph-light ph-folder"></i>
                        <span>{{ t('Browse') }}</span>
                    </button>
                </div>
            </template>
        </template>
           
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';

function formatShortcut(e) {
    let keys = [];
    if (e.ctrlKey) keys.push('Ctrl');
    if (e.altKey) keys.push('Alt');
    if (e.shiftKey) keys.push('Shift');
    if (e.metaKey) keys.push('Meta');
    if (e.key && !['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
        keys.push(e.key.length === 1 ? e.key.toUpperCase() : e.key);
    }
    return keys.join('+');
}

export default {
    name: "asrjsSettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    components: {
        SaveSettingsButton
    },
    data() {
        return {
            formData: {
                model_provider: 'groq',
                model_name: 'whisper-large-v3',
                voxtral_api_key: '',
                continuous: false,
                always_generate: false,
                positiveSpeechThreshold: 0.5,
                redemptionFrames: 8,
                shortcut: ''
            },
            defaultSettings: {
                positiveSpeechThreshold: 0.5,
                redemptionFrames: 8,
                continuous: false,
                always_generate: false
            },
            isRecordingShortcut: false,
            voxtralKeyError: false,
            loading: false,
            // Volume meter
            volumeLevel: 0,
            audioContext: null,
            analyser: null,
            microphone: null,
            volumeCheckInterval: null,
            // Custom wakeword model
            customModels: []  // List of custom model filenames
        };
    },
    computed: {
        hasUnsavedChanges() {
            if (!this.originalSettings || !this.formData) return false;
            return JSON.stringify(this.formData) !== JSON.stringify(this.originalSettings);
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal) {
                    this.$nextTick(() => {
                        this.setOriginalSettings(newVal);
                        this.formData = {
                            ...this.defaultSettings,
                            ...newVal
                        };
                    });
                }
            },
            immediate: true,
            deep: true
        },
        'formData.continuous'(newVal) {
            if (!newVal) {
                // Wakeword requires continuous mode - auto-disable it
                this.formData.wakeword_enabled = false;
            }
        }
    },
    mounted() {
        this.startVolumeMonitor();
        this.fetchCustomModels();
    },
    beforeDestroy() {
        this.stopVolumeMonitor();
    },
    methods: {
        startRecordingShortcut(e) {
            this.isRecordingShortcut = true;
        },
        stopRecordingShortcut() {
            this.isRecordingShortcut = false;
        },
        recordShortcut(e) {
            if (!this.isRecordingShortcut) return;
            if (!['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
                const shortcut = formatShortcut(e);
                if (shortcut) {
                    this.formData.shortcut = shortcut;
                    this.isRecordingShortcut = false;
                    e.target.blur();
                }
            }
        },
        clearShortcut() {
            this.formData.shortcut = '';
        },
        onProviderChange() {
            if (this.formData.model_provider === 'groq') {
                if (!['whisper-large-v3', 'whisper-large-v3-turbo'].includes(this.formData.model_name)) {
                    this.formData.model_name = 'whisper-large-v3';
                }
            } else if (this.formData.model_provider === 'mistral') {
                if (this.formData.model_name !== 'voxtral-mini-latest') {
                    this.formData.model_name = 'voxtral-mini-latest';
                }
            }
        },
        checkBeforeUpdating() {
            console.log("Updating settings with:", this.formData);
            if (
                this.formData.model_name === 'voxtral-mini-latest' &&
                (!this.formData.voxtral_api_key || !this.formData.voxtral_api_key.trim())
            ) {
                this.voxtralKeyError = true;
                console.warn('Voxtral API Key is required for Voxtral models.');
                return;
            }
            this.voxtralKeyError = false;
            this.loading = true;
            this.saveSettings().finally(() => {
                this.loading = false;
            });
        },
        async startVolumeMonitor() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                this.microphone = this.audioContext.createMediaStreamSource(stream);
                this.analyser = this.audioContext.createAnalyser();
                this.analyser.fftSize = 2048;
                this.microphone.connect(this.analyser);

                const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
                this.volumeCheckInterval = setInterval(() => {
                    // Use time domain data for proper amplitude measurement
                    this.analyser.getByteTimeDomainData(dataArray);
                    // Calculate RMS (root mean square) for volume
                    let sum = 0;
                    for (let i = 0; i < dataArray.length; i++) {
                        const normalized = (dataArray[i] - 128) / 128;
                        sum += normalized * normalized;
                    }
                    const rms = Math.sqrt(sum / dataArray.length);
                    // Scale to 0-100% with some boost for visibility
                    this.volumeLevel = Math.min(100, Math.round(rms * 400));
                }, 100);
            } catch (e) {
                console.error('Could not access microphone:', e);
            }
        },
        stopVolumeMonitor() {
            if (this.volumeCheckInterval) {
                clearInterval(this.volumeCheckInterval);
                this.volumeCheckInterval = null;
            }
            if (this.microphone) {
                this.microphone.disconnect();
                this.microphone = null;
            }
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }
        },
        async fetchCustomModels() {
            try {
                const response = await fetch('http://127.0.0.1:9714/api/plugins/asrjs/list_custom_wakeword_models');
                const result = await response.json();
                if (result.models) {
                    this.customModels = result.models;
                }
            } catch (error) {
                console.error('Error fetching custom models:', error);
            }
        },
        async handleWakewordFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('http://127.0.0.1:9714/api/plugins/asrjs/upload_wakeword_model', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (result.status === 'success') {
                    // Refresh the list and select the new model
                    await this.fetchCustomModels();
                    this.formData.wakeword_model = result.filename;
                    console.log('Custom model uploaded:', result.path);
                } else {
                    console.error('Upload failed:', result.message);
                }
            } catch (error) {
                console.error('Error uploading model:', error);
            }
        }
    }
};
</script>

<style scoped>
.asrjs-plugin-settings.form-grid {
    gap: 12px 18px;
    align-items: start;
    background: none;
    padding: 10px;
}

.bio-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px 18px;
    align-items: start;
}
.bio{
    width: 100%;
}
.bio.left {
    display: flex;
    flex-direction: column;
}

.bio.right {
    display: flex;
    flex-direction: column;
}

.form-label {
    font-weight: 500;
    padding-top: 6px;
    color: #e0e0e0;
    min-width: 200px;
}

.form-input {
    display: flex;
    align-items: center;
    gap: 8px;
}

.form-note {
    font-size: 0.97em;
    color: #aaa;
    line-height: 1.4;
    padding-top: 2px;
    text-align: left;
}

select, input[type="text"], input[type="password"], input[type="number"] {
    background: #222;
    color: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 1em;
}

button {
    background: #3ca23c;
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
}

button:hover {
    background: #338a33;
}

button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.input-error {
    border-color: #ff6666;
    background: #2a1818;
}

.toggle-switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #444;
    transition: 0.3s;
    border-radius: 24px;
}

.toggle-slider:before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background-color: #ccc;
    transition: 0.3s;
    border-radius: 50%;
}

.toggle-switch input:checked + .toggle-slider {
    background-color: #3ca23c;
}

.toggle-switch input:checked + .toggle-slider:before {
    transform: translateX(20px);
}

.volume-meter {
    width: 150px;
    height: 20px;
    background: #333;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #555;
}

.volume-bar {
    height: 100%;
    background: linear-gradient(90deg, #3ca23c, #7cb342, #fdd835, #ff5722);
    transition: width 0.05s ease-out;
}

.volume-value {
    font-size: 0.9em;
    color: #aaa;
    min-width: 40px;
}
</style>
