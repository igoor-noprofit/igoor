<template>
    <div class="elevenlabs-plugin-settings form-grid bio-container">
        <div class="bio left">
            <!-- API Key -->
            <div class="form-label">{{ t('API Key used to authenticate with the ElevenLabs provider') }}</div>
            <div class="form-input">
                <input type="password" v-model="formData.api_key" :class="{ 'input-error': apiKeyError }"
                    placeholder="ex. 93acd-...-...-...-fe1" />
            </div>
            <div class="form-note" :style="{ color: apiKeyError ? '#ff6666' : undefined }">
                {{ apiKeyError ? (apiKeyErrorMessage || t('API Key is required')) : '' }}
            </div>

            <!-- Voice Selection -->
            <div class="form-label">{{ t('Choose a voice for synthesis') }}</div>
            <div class="form-input">
                <select v-model="formData.voice_id" :class="{ 'input-error': voiceIdError }" @change="onVoiceIdChange"
                    :disabled="!filteredVoices.length" class="voice-selector">
                    <option disabled value="">{{ t('Select a voice') }}</option>
                    <option v-for="voice in filteredVoices" :key="voice.id" :value="voice.id">
                        {{ voice.display_name }}
                    </option>
                </select>
            </div>
            <div class="form-note" :style="{ color: voiceIdError ? '#ff6666' : undefined }">
                {{ voiceIdError ? t('Voice ID is required') : '' }}
            </div>

            <!-- Model Selection -->
            <div class="form-label">{{ t('Model selection') }}</div>
            <div class="form-input">
                <select v-model="formData.model_id">
                    <option value="eleven_multilingual_v2">Eleven Multilingual v2</option>
                    <option value="eleven_turbo_v2_5">Eleven Turbo v2.5</option>
                    <option value="eleven_flash_v2_5">Eleven Flash v2.5</option>
                    <option value="eleven_v3">Eleven v3</option>
                </select>
            </div>

            <!-- Output Format Selection -->
            <div class="form-label">{{ t('Output Format') }}</div>
            <div class="form-input">
                <select v-model="formData.output_format">
                    <option value="mp3_44100_128">MP3 44.1kHz 128kbps</option>
                    <option value="mp3_44100_96">MP3 44.1kHz 96kbps</option>
                    <option value="mp3_44100_64">MP3 44.1kHz 64kbps</option>
                    <option value="mp3_22050_128">MP3 22.05kHz 128kbps</option>
                    <option value="mp3_22050_96">MP3 22.05kHz 96kbps</option>
                    <option value="mp3_22050_64">MP3 22.05kHz 64kbps</option>
                    <option value="pcm_16000">PCM 16kHz</option>
                    <option value="pcm_22050">PCM 22.05kHz</option>
                    <option value="pcm_44100">PCM 44.1kHz</option>
                </select>
            </div>
        </div>

        <div class="bio right">
            <!-- Save Button -->
            <div class="form-label"></div>
            <div class="form-input">
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%" >
                    <button class="" type="button" @click="testVoice">{{ t('Test voice') }}</button>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <SaveSettingsButton
                            :hasChanges="hasChanges"
                            :loading="isSaving"
                            :t="t"
                            :lang="lang"
                            @save="checkBeforeUpdating"
                            @cancel="resetSettings"
                        />
                        <div v-if="saveStatus" style="margin-left:12px;">
                            <span v-if="saveStatus.type === 'success'" style="color:#3ca23c">{{ saveStatus.message }}</span>
                            <span v-else style="color:#ff6666">{{ saveStatus.message }}</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="form-note"></div>

            <!-- Advanced controls card -->
            <div class="form-label"></div>
            <div class="form-input" style="grid-column: 2 / span 2; padding: 10px 0;">
                <div class="ssml-card">
                    <!-- Card header with reset button -->
                    <div class="ssml-card-header"
                        style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div>{{ t('Advanced Voice Controls') }}</div>
                        <div style="text-align:right">
                            <button class="reset-button" type="button" @click="resetControllers">{{ t('Reset')
                            }}</button>
                        </div>
                    </div>

                    <!-- Stability Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Stability') }}</div>
                        <div class="ssml-center">
                            <input type="range" id="stabilitySlider" :min="0" :max="1" step="0.01"
                                v-model.number="stabilityValue" @input="onStabilityChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="stabilityValue"
                                @change="onStabilityChange" step="0.01" min="0" max="1" />
                        </div>
                    </div>

                    <!-- Similarity Boost Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Similarity Boost') }}</div>
                        <div class="ssml-center">
                            <input type="range" id="similarityBoostSlider" :min="0" :max="1" step="0.01"
                                v-model.number="similarityBoostValue" @input="onSimilarityBoostChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="similarityBoostValue"
                                @change="onSimilarityBoostChange" step="0.01" min="0" max="1" />
                        </div>
                    </div>

                    <!-- Style Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Style') }}</div>
                        <div class="ssml-center">
                            <input type="range" id="styleSlider" :min="0" :max="1" step="0.01"
                                v-model.number="styleValue" @input="onStyleChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="styleValue"
                                @change="onStyleChange" step="0.01" min="0" max="1" />
                        </div>
                    </div>

                    <!-- Speed Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Speed') }}</div>
                        <div class="ssml-center">
                            <input type="range" id="speedSlider" :min="0.7" :max="1.2" step="0.05"
                                v-model.number="speedValue" @input="onSpeedChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="speedValue"
                                @change="onSpeedChange" step="0.05" min="0.7" max="1.2" />
                        </div>
                    </div>

                    <!-- Latency Optimization Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Latency Optimization') }}</div>
                        <div class="ssml-center">
                            <select id="latencyOptimizationSlider" v-model="latencyOptimizationValue" @change="onLatencyOptimizationChange">
                                <option :value="0">{{ t('Best Quality') }}</option>
                                <option :value="1">{{ t('Quality') }}</option>
                                <option :value="2">{{ t('Balanced') }}</option>
                                <option :value="3">{{ t('Speed') }}</option>
                                <option :value="4">{{ t('Max Speed') }}</option>
                            </select>
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="latencyOptimizationValue"
                                @change="onLatencyOptimizationChange" min="0" max="4" />
                        </div>
                    </div>

                    <!-- Speaker Boost & Logging Toggles -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Speaker Boost') }}</div>
                        <div class="ssml-center checkbox-columns">
                            <div class="checkbox-column">
                                <input type="checkbox" id="use_speaker_boost" v-model="speakerBoostValue" @change="onSpeakerBoostChange" />
                                <label for="use_speaker_boost">{{ t('Speaker Boost') }}</label>
                            </div>
                            <div class="checkbox-column">
                                <input type="checkbox" id="enable_logging" v-model="formData.enable_logging" />
                                <label for="enable_logging">{{ t('Enable Logging') }}</label>
                            </div>
                        </div>
                        <div class="ssml-right">
                        </div>
                    </div>

                    

                </div>
            </div>
            <div class="form-note"></div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';

export default {
    name: 'elevenlabsttsSettings',
    mixins: [BasePluginComponent],
    components: {
        SaveSettingsButton
    },
    props: {
        initialSettings: Object
    },
    data() {
        return {
            formData: {
                api_key: '',
                voice_id: '',
                model_id: 'eleven_multilingual_v2',
                stability: 0.5,
                similarity_boost: 0.75,
                style: 0.0,
                use_speaker_boost: true,
                speed: 1.0,
                latency_optimization: 0,
                output_format: 'mp3_44100_128',
                enable_logging: true
            },
            originalSettings: null,
            apiKeyError: false,
            apiKeyErrorMessage: '',
            voiceIdError: false,
            isSaving: false,
            saveStatus: null,
            voiceList: [],
            apiKeyInitialized: false,
            // Local v-model backing values
            stabilityValue: 0.5,
            similarityBoostValue: 0.75,
            styleValue: 0.0,
            speakerBoostValue: true,
            speedValue: 1.0,
            latencyOptimizationValue: 0,
            outputFormatValue: 'mp3_44100_128',
            enableLoggingValue: true
        };
    },
    computed: {
        hasChanges() {
            if (!this.originalSettings) return false;
            const keys = ['api_key', 'voice_id', 'model_id', 'stability', 'similarity_boost', 'style', 'use_speaker_boost', 'speed', 'latency_optimization', 'output_format', 'enable_logging'];
            return keys.some(k => JSON.stringify(this.formData[k]) !== JSON.stringify(this.originalSettings[k]));
        },
        filteredVoices() {
            const voices = Array.isArray(this.voiceList) ? this.voiceList : [];
            // Show all voices without filtering
            return voices
                .slice()
                .sort((a, b) => a.display_name.localeCompare(b.display_name, undefined, { sensitivity: 'base' }));
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (!newVal) return;
                this.formData = { ...this.formData, ...newVal };
                this.voiceList = Array.isArray(newVal.voice_list) ? newVal.voice_list.slice() : [];
                // initialize local values
                this.stabilityValue = Number(newVal.stability ?? this.formData.stability ?? 0.5);
                this.similarityBoostValue = Number(newVal.similarity_boost ?? this.formData.similarity_boost ?? 0.75);
                this.styleValue = Number(newVal.style ?? this.formData.style ?? 0.0);
                this.speakerBoostValue = newVal.use_speaker_boost !== undefined ? newVal.use_speaker_boost : this.formData.use_speaker_boost;
                this.speedValue = Number(newVal.speed ?? this.formData.speed ?? 1.0);
                this.latencyOptimizationValue = Number(newVal.latency_optimization ?? this.formData.latency_optimization ?? 0);
                // store original settings snapshot for change detection
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
                this.apiKeyInitialized = true;
            },
            immediate: true,
            deep: true
        },

        'formData.api_key': {
            async handler(newVal, oldVal) {
                if (!this.apiKeyInitialized) return;
                const trimmedNew = (newVal || '').trim();
                const trimmedOld = (oldVal || '').trim();
                if (trimmedNew === trimmedOld) return;

                // Clear errors when API key changes
                this.apiKeyError = false;
                this.apiKeyErrorMessage = '';

                if (!trimmedNew) {
                    this.voiceList = [];
                    this.formData.voice_id = '';
                    return;
                }

                await this.loadVoiceListFromRest();
            }
        }
    },
    methods: {
        onStabilityChange() {
            if (this.stabilityValue < 0) this.stabilityValue = 0;
            if (this.stabilityValue > 1) this.stabilityValue = 1;
            this.formData.stability = parseFloat(this.stabilityValue.toFixed(2));
        },
        onSimilarityBoostChange() {
            if (this.similarityBoostValue < 0) this.similarityBoostValue = 0;
            if (this.similarityBoostValue > 1) this.similarityBoostValue = 1;
            this.formData.similarity_boost = parseFloat(this.similarityBoostValue.toFixed(2));
        },
        onStyleChange() {
            if (this.styleValue < 0) this.styleValue = 0;
            if (this.styleValue > 1) this.styleValue = 1;
            this.formData.style = parseFloat(this.styleValue.toFixed(2));
        },
        onSpeakerBoostChange() {
            this.formData.use_speaker_boost = this.speakerBoostValue;
        },

        onSpeedChange() {
            if (this.speedValue < 0.7) this.speedValue = 0.7;
            if (this.speedValue > 1.2) this.speedValue = 1.2;
            // Clamp speed to valid range before saving
            this.formData.speed = Math.max(0.7, Math.min(1.2, parseFloat(this.speedValue.toFixed(1))));
        },
        onLatencyOptimizationChange() {
            if (this.latencyOptimizationValue < 0) this.latencyOptimizationValue = 0;
            if (this.latencyOptimizationValue > 4) this.latencyOptimizationValue = 4;
            this.formData.latency_optimization = parseInt(this.latencyOptimizationValue);
        },

        
        resetControllers() {
            // Reset to default values
            this.stabilityValue = 0.5;
            this.similarityBoostValue = 0.75;
            this.styleValue = 0.0;
            this.speakerBoostValue = true;
            this.speedValue = 1.0;
            this.latencyOptimizationValue = 0;
            
            this.formData.stability = 0.5;
            this.formData.similarity_boost = 0.75;
            this.formData.style = 0.0;
            this.formData.use_speaker_boost = true;
            this.formData.speed = 1.0;
            this.formData.latency_optimization = 0;
            
            // Reset new parameters
            this.formData.output_format = 'mp3_44100_128';
            this.formData.enable_logging = true;


        },
        resetSettings() {
            // Restore to last saved settings (originalSettings)
            if (this.originalSettings) {
                this.formData = JSON.parse(JSON.stringify(this.originalSettings));
                // Reset local v-model values to match formData
                this.stabilityValue = this.formData.stability;
                this.similarityBoostValue = this.formData.similarity_boost;
                this.styleValue = this.formData.style;
                this.speakerBoostValue = this.formData.use_speaker_boost;
                this.speedValue = this.formData.speed;
                this.latencyOptimizationValue = this.formData.latency_optimization;
                this.outputFormatValue = this.formData.output_format;
                this.enableLoggingValue = this.formData.enable_logging;
                // Clear errors
                this.apiKeyError = false;
                this.apiKeyErrorMessage = '';
                this.voiceIdError = false;
            }
        },
        async loadVoiceListFromRest() {
            // Clear any previous error
            this.apiKeyError = false;
            this.apiKeyErrorMessage = '';

            if (!this.formData.api_key || !this.formData.api_key.trim()) {
                console.log('Cannot load voices: API key missing');
                return;
            }

            console.log('Loading voices via REST API...');
            try {
                const params = {
                    api_key: this.formData.api_key.trim()
                };
                console.log('Fetching voices using callPluginRestEndpoint with params:', params);

                const data = await this.callPluginRestEndpoint('elevenlabstts', 'get_voices', params);
                console.log('Voice list response:', data);

                // Handle response structure
                if (data.voices && Array.isArray(data.voices)) {
                    this.voiceList = data.voices;
                    console.log(`Loaded ${this.voiceList.length} voices via REST API`);
                } else if (Array.isArray(data)) {
                    this.voiceList = data;
                    console.log(`Loaded ${this.voiceList.length} voices via REST API`);
                } else {
                    console.error('Unexpected voice list format:', data);
                    this.voiceList = [];
                }
            } catch (err) {
                console.error('Error loading voices via REST:', err);
                this.voiceList = [];
                this.apiKeyError = true;

                // Extract error message from response
                if (err.response && err.response.data) {
                    const errorData = err.response.data;
                    if (errorData.detail) {
                        if (typeof errorData.detail === 'string') {
                            // Try to parse JSON string from detail
                            try {
                                const parsed = JSON.parse(errorData.detail);
                                if (parsed.detail && parsed.detail.message) {
                                    this.apiKeyErrorMessage = parsed.detail.message;
                                } else if (parsed.message) {
                                    this.apiKeyErrorMessage = parsed.message;
                                } else {
                                    this.apiKeyErrorMessage = 'Invalid API key';
                                }
                            } catch (parseErr) {
                                // If parsing fails, use the detail string directly
                                this.apiKeyErrorMessage = errorData.detail;
                            }
                        } else if (errorData.detail.message) {
                            this.apiKeyErrorMessage = errorData.detail.message;
                        }
                    } else if (errorData.message) {
                        this.apiKeyErrorMessage = errorData.message;
                    }
                }

                // Fallback message if we couldn't extract a specific one
                if (!this.apiKeyErrorMessage) {
                    this.apiKeyErrorMessage = this.t('Failed to validate API key. Please check your key and try again.');
                }
            }
        },

        async testVoice() {
            let msg = this.t('Hello, how are you doing? I feel better today!')
            let testData = { ...this.formData };
            testData['action'] = 'test_speak';
            testData['message'] = msg;
            testData['target'] = 'elevenlabstts'; // Specify target to prevent message interference
            
            // Remove GenerationOptions if it exists (leftover from Speechify)
            delete testData['GenerationOptions'];
            
            console.log('Sending test_speak message:', testData);
            
            // Use HTTP POST for test_speak endpoint (not WebSocket)
            try {
                await this.callPluginRestEndpoint('elevenlabstts', 'test_speak', {method: 'POST', data: testData});
            } catch (error) {
                console.error('Error sending test message:', error);
            }
        },
        onVoiceIdChange() {
            this.voiceIdError = !this.formData.voice_id || !this.formData.voice_id.trim();
        },
        async checkBeforeUpdating() {
            this.apiKeyError = !this.formData.api_key || !this.formData.api_key.trim();
            this.apiKeyErrorMessage = '';
            this.voiceIdError = !this.formData.voice_id || !this.formData.voice_id.trim();
            if (this.apiKeyError || this.voiceIdError) return;

            // Ensure values are properly formatted
            this.onStabilityChange();
            this.onSimilarityBoostChange();
            this.onStyleChange();
            this.onSpeedChange();
            this.onLatencyOptimizationChange();

            try {
                this.isSaving = true;
                this.saveStatus = null;
                await this.updateSettings();
                this.saveStatus = { type: 'success', message: this.t('Settings saved') };
                // refresh original snapshot so hasChanges becomes false
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));

                // Load voice list when API key is available and voice list is empty
                if (this.formData.api_key && this.formData.api_key.trim() && this.voiceList.length === 0) {
                    await this.loadVoiceListFromRest();
                }

            } catch (err) {
                console.error('Error saving settings', err);
                this.saveStatus = { type: 'error', message: this.t('Failed to save settings') };
            } finally {
                this.isSaving = false;
                setTimeout(() => { this.saveStatus = null; }, 3000);
            }
        },
        handleIncomingMessage(event) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) {
                return true;
            }

            let payload;
            try {
                payload = JSON.parse(event.data);
            } catch (err) {
                return false;
            }

            if (payload && payload.type === 'voice_list') {
                const voices = Array.isArray(payload.voice_list) ? payload.voice_list : [];
                this.voiceList = voices.slice();
                if (!this.voiceList.some(v => v.id === this.formData.voice_id)) {
                    this.formData.voice_id = '';
                }
                return true;
            }

            return false;
        }
    },

    async created() {
        await this.loadTranslations();
        
        // Load voice list if API key is already available from initial settings
        if (this.initialSettings?.api_key && this.initialSettings.api_key.trim()) {
            console.log('Loading voices during component creation...');
            await this.loadVoiceListFromRest();
        }
    },

};
</script>

<style scoped>
.elevenlabs-plugin-settings.form-grid {
    gap: 12px 18px;
    align-items: start;
    background: none;
    padding: 10px;
}

.form-input {
    display: flex;
    align-items: center;
    gap: 8px;
}

.voice-selector{
    width: 37vw;
}

.form-note {
    font-size: 0.97em;
    color: #aaa;
    line-height: 1.4;
    padding-top: 2px;
    text-align: left;
}

select,
input[type="text"],
input[type="number"],
input[type="password"] {
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

.disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.input-error {
    border-color: #ff6666;
    background: #2a1818;
}

/* SSML card */
.ssml-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.04);
    padding: 12px;
    border-radius: 8px;
    width: 100%;
}

.ssml-row {
    display: grid;
    grid-template-columns: 150px 1fr 120px;
    align-items: center;
    gap: 12px;
    padding: 0.2vh 0;
}

.ssml-left {
    color: #e8e8e8;
    font-weight: 600;
}

.ssml-center {
    padding: 0 12px;
}

.ssml-center input[type="range"] {
    width: 100%;
}

.ssml-right {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
}

.numeric-input {
    width: 80px;
}

.text-input {
    width: 100%;
    background: #222;
    color: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 0.9em;
}

.reset-button {
    background: #666;
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 0.9em;
    cursor: pointer;
    transition: background 0.2s;
}

.reset-button:hover {
    background: #555;
}

/* Checkbox columns layout */
.checkbox-columns {
    display: flex;
    gap: 20px;
    justify-content: flex-start;
}

.checkbox-column {
    display: flex;
    align-items: center;
    gap: 8px;
}

.checkbox-column label {
    color: #e8e8e8;
    font-size: 0.9em;
}

.checkbox-column input[type="checkbox"] {
    margin: 0;
}
</style>
