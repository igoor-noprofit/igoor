<template>
    <div class="pockettts-plugin-settings form-grid bio-container">
        <div class="bio left">
            <!-- Model Status Banner -->
            <div v-if="modelLoading" class="model-status-banner loading">
                <span class="spinner"></span>
                {{ t('Loading Pocket TTS model...') }}
            </div>
            <div v-else-if="!modelLoaded" class="model-status-banner error">
                {{ t('Model not loaded. Please check logs.') }}
            </div>

            <!-- Voice Selection -->
            <div class="form-label">{{ t('Choose a voice for synthesis') }}</div>
            <div class="form-input">
                <select v-model="formData.voice" class="voice-selector" @change="onVoiceChange">
                    <option value="auto">{{ t('Auto (recommended)') }}</option>
                    <optgroup :label="t('Built-in voices')">
                        <option v-for="v in builtinVoices" :key="v.name" :value="v.name">
                            {{ v.label }}
                        </option>
                    </optgroup>
                    <optgroup v-if="customVoices.length" :label="t('Cloned voices')">
                        <option v-for="v in customVoices" :key="v.name" :value="'custom:' + v.name">
                            {{ v.label }}
                        </option>
                    </optgroup>
                </select>
            </div>
            <div class="form-note">
                {{ t('Select a built-in voice or clone your own below') }}
            </div>

            <!-- Voice cloning buttons -->
            <div class="voice-clone-section">
                <button class="clone-btn" type="button" @click="useRecordedVoice"
                    :disabled="!voiceSampleExists || isCloning || !modelLoaded"
                    :title="!voiceSampleExists ? t('No recorded voice available') : t('Use your biorecorder voice samples to clone your voice')">
                    <span v-if="isCloning && cloningSource === 'recorded'">{{ t('Cloning...') }}</span>
                    <span v-else>{{ t('Use recorded voice') }}</span>
                </button>
                <button class="clone-btn" type="button" @click="triggerUploadClone"
                    :disabled="isCloning || !modelLoaded">
                    {{ t('Upload audio to clone voice') }}
                </button>
                <input type="file" ref="cloneFileInput" style="display:none"
                    accept=".wav,.mp3,.ogg,.webm" @change="onCloneFileSelected" />
            </div>

            <!-- Language display -->
            <div class="form-label">{{ t('Language') }}</div>
            <div class="form-input">
                <span class="lang-display">{{ modelLanguage || t('Detecting...') }}</span>
            </div>
            <div class="form-note">
                {{ t('Automatically detected from your IGOOR settings') }}
            </div>

            <!-- High Quality Mode (24L) -->
            <div class="form-label">{{ t('High Quality Mode (24L)') }}</div>
            <div class="form-input">
                <input type="checkbox" id="use_24l" v-model="formData.use_24l" />
                <label for="use_24l" class="checkbox-label">
                    {{ t('Use 24-layer model (higher quality, slower)') }}
                </label>
            </div>
            <div class="form-note">
                {{ t('Only available for non-English languages. Requires model reload.') }}
            </div>
        </div>

        <div class="bio right">
            <!-- Test + Save buttons -->
            <div class="form-label"></div>
            <div class="form-input">
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                    <button type="button" @click="testVoice" :disabled="!modelLoaded">{{ t('Test voice') }}</button>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <SaveSettingsButton
                            :hasChanges="hasChanges"
                            :loading="isSaving"
                            :t="t"
                            :lang="lang"
                            @save="handleSave"
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
                    <div class="ssml-card-header"
                        style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div>{{ t('Advanced Voice Controls') }}</div>
                        <div style="text-align:right">
                            <button class="reset-button" type="button" @click="resetControllers">{{ t('Reset') }}</button>
                        </div>
                    </div>

                    <!-- Temperature Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Temperature') }}</div>
                        <div class="ssml-center">
                            <input type="range" :min="0" :max="1" step="0.05"
                                v-model.number="tempValue" @input="onTempChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="tempValue"
                                @change="onTempChange" step="0.05" min="0" max="1" />
                        </div>
                    </div>

                    <!-- EOS Threshold Row -->
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('EOS Threshold') }}</div>
                        <div class="ssml-center">
                            <input type="range" :min="-10" :max="0" step="0.5"
                                v-model.number="eosValue" @input="onEosChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="eosValue"
                                @change="onEosChange" step="0.5" min="-10" max="0" />
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
    name: 'pocketttsSettings',
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
                voice: 'auto',
                custom_voice_path: '',
                use_24l: false,
                temp: 0.7,
                eos_threshold: -4.0
            },
            originalSettings: null,
            isSaving: false,
            saveStatus: null,
            builtinVoices: [],
            customVoices: [],
            modelLanguage: '',
            modelLoaded: false,
            modelLoading: true,
            voiceSampleExists: false,
            isCloning: false,
            cloningSource: '',
            // Local v-model backing values
            tempValue: 0.7,
            eosValue: -4.0,
            // Polling timer
            statusPollTimer: null
        };
    },
    computed: {
        hasChanges() {
            if (!this.originalSettings) return false;
            var keys = ['voice', 'custom_voice_path', 'use_24l', 'temp', 'eos_threshold'];
            var self = this;
            return keys.some(function(k) {
                return JSON.stringify(self.formData[k]) !== JSON.stringify(self.originalSettings[k]);
            });
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (!newVal) return;
                this.formData = Object.assign({}, this.formData, newVal);
                this.tempValue = Number(newVal.temp != null ? newVal.temp : 0.7);
                this.eosValue = Number(newVal.eos_threshold != null ? newVal.eos_threshold : -4.0);
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
        onTempChange() {
            if (this.tempValue < 0) this.tempValue = 0;
            if (this.tempValue > 1) this.tempValue = 1;
            this.formData.temp = parseFloat(this.tempValue.toFixed(2));
        },
        onEosChange() {
            if (this.eosValue < -10) this.eosValue = -10;
            if (this.eosValue > 0) this.eosValue = 0;
            this.formData.eos_threshold = parseFloat(this.eosValue.toFixed(1));
        },
        onVoiceChange() {
            // If selecting a custom voice from the dropdown, update custom_voice_path
            if (this.formData.voice && this.formData.voice.startsWith('custom:')) {
                var fileName = this.formData.voice.replace('custom:', '');
                var match = this.customVoices.find(function(v) { return v.name === fileName; });
                if (match) {
                    this.formData.custom_voice_path = match.path;
                    this.formData.voice = 'custom';
                }
            }
        },
        resetControllers() {
            this.tempValue = 0.7;
            this.eosValue = -4.0;
            this.formData.temp = 0.7;
            this.formData.eos_threshold = -4.0;
        },
        resetSettings() {
            if (this.originalSettings) {
                this.formData = JSON.parse(JSON.stringify(this.originalSettings));
                this.tempValue = this.formData.temp;
                this.eosValue = this.formData.eos_threshold;
            }
        },
        async loadVoices() {
            try {
                var data = await this.callPluginRestEndpoint('pockettts', 'voices');
                if (data.builtin) this.builtinVoices = data.builtin;
                if (data.custom) this.customVoices = data.custom;
                if (data.language) this.modelLanguage = data.language;
            } catch (err) {
                console.error('Error loading voices:', err);
            }
        },
        async checkModelStatus() {
            try {
                var data = await this.callPluginRestEndpoint('pockettts', 'model_status');
                this.modelLoaded = data.model_loaded;
                this.modelLoading = data.model_loading;
                this.modelLanguage = data.language || '';

                if (this.modelLoaded && this.statusPollTimer) {
                    clearInterval(this.statusPollTimer);
                    this.statusPollTimer = null;
                    // Load voices once model is ready
                    await this.loadVoices();
                }
            } catch (err) {
                console.error('Error checking model status:', err);
            }
        },
        async checkVoiceSample() {
            try {
                var response = await fetch('/api/plugins/biorecorder/voice_sample');
                if (response.ok) {
                    var data = await response.json();
                    this.voiceSampleExists = data.exists;
                }
            } catch (e) {
                this.voiceSampleExists = false;
            }
        },
        async useRecordedVoice() {
            this.isCloning = true;
            this.cloningSource = 'recorded';
            try {
                var data = await this.callPluginRestEndpoint('pockettts', 'use_recorded_voice', {
                    method: 'POST'
                });
                if (data.status === 'cloned') {
                    this.formData.voice = 'custom';
                    this.formData.custom_voice_path = data.path;
                    await this.loadVoices();
                    this.saveStatus = { type: 'success', message: this.t('Voice cloned successfully') };
                    var self = this;
                    setTimeout(function() { self.saveStatus = null; }, 3000);
                }
            } catch (e) {
                console.error('Clone error:', e);
                this.saveStatus = { type: 'error', message: e.message || this.t('Failed to clone voice') };
                var self = this;
                setTimeout(function() { self.saveStatus = null; }, 5000);
            } finally {
                this.isCloning = false;
                this.cloningSource = '';
            }
        },
        triggerUploadClone() {
            this.$refs.cloneFileInput.click();
        },
        async onCloneFileSelected(event) {
            var file = event.target.files[0];
            if (!file) return;
            this.isCloning = true;
            this.cloningSource = 'upload';
            try {
                var fd = new FormData();
                fd.append('audio_file', file);
                fd.append('name', 'Voice_Clone_' + new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
                var response = await fetch('/api/plugins/pockettts/clone_voice', {
                    method: 'POST',
                    body: fd
                });
                if (!response.ok) {
                    var err = await response.json();
                    throw new Error(err.detail || 'Clone failed');
                }
                var data = await response.json();
                this.formData.voice = 'custom';
                this.formData.custom_voice_path = data.path;
                await this.loadVoices();
                this.saveStatus = { type: 'success', message: this.t('Voice cloned successfully') };
                var self = this;
                setTimeout(function() { self.saveStatus = null; }, 3000);
            } catch (e) {
                console.error('Clone error:', e);
                this.saveStatus = { type: 'error', message: e.message || this.t('Failed to clone voice') };
                var self = this;
                setTimeout(function() { self.saveStatus = null; }, 5000);
            } finally {
                this.isCloning = false;
                this.cloningSource = '';
                event.target.value = '';
            }
        },
        async testVoice() {
            try {
                await this.callPluginRestEndpoint('pockettts', 'test_speak', {
                    method: 'POST',
                    data: { message: this.t('Hello, how are you doing? I feel better today!') }
                });
            } catch (error) {
                console.error('Error sending test message:', error);
            }
        },
        async handleSave() {
            try {
                this.isSaving = true;
                this.saveStatus = null;

                this.onTempChange();
                this.onEosChange();

                await this.updateSettings();
                this.saveStatus = { type: 'success', message: this.t('Settings saved') };
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
            } catch (err) {
                console.error('Error saving settings', err);
                this.saveStatus = { type: 'error', message: this.t('Failed to save settings') };
            } finally {
                this.isSaving = false;
                var self = this;
                setTimeout(function() { self.saveStatus = null; }, 3000);
            }
        },
        handleIncomingMessage(event) {
            var handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;

            var payload;
            try {
                payload = JSON.parse(event.data);
            } catch (err) {
                return false;
            }

            if (payload && payload.type === 'voice_list') {
                if (payload.builtin) this.builtinVoices = payload.builtin;
                if (payload.custom) this.customVoices = payload.custom;
                if (payload.language) this.modelLanguage = payload.language;
                return true;
            }

            return false;
        }
    },
    async created() {
        await this.loadTranslations();
        this.checkVoiceSample();
        await this.checkModelStatus();

        // Poll model status until loaded
        if (!this.modelLoaded) {
            var self = this;
            this.statusPollTimer = setInterval(function() {
                self.checkModelStatus();
            }, 2000);
        } else {
            await this.loadVoices();
        }
    },
    beforeDestroy() {
        if (this.statusPollTimer) {
            clearInterval(this.statusPollTimer);
        }
    }
};
</script>

<style scoped>
.pockettts-plugin-settings.form-grid {
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

.voice-selector {
    width: 37vw;
}

.form-note {
    font-size: 0.97em;
    color: #aaa;
    line-height: 1.4;
    padding-top: 2px;
    text-align: left;
}

.lang-display {
    color: #ccc;
    font-size: 1em;
    text-transform: capitalize;
}

.checkbox-label {
    color: #e8e8e8;
    font-size: 0.95em;
    margin-left: 6px;
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

button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Model status banner */
.model-status-banner {
    grid-column: 1 / -1;
    padding: 10px 16px;
    border-radius: 6px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}

.model-status-banner.loading {
    background: rgba(60, 162, 60, 0.15);
    border: 1px solid rgba(60, 162, 60, 0.3);
    color: #6fd46f;
}

.model-status-banner.error {
    background: rgba(255, 102, 102, 0.15);
    border: 1px solid rgba(255, 102, 102, 0.3);
    color: #ff6666;
}

.spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(111, 212, 111, 0.3);
    border-top-color: #6fd46f;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
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

.voice-clone-section {
    display: flex;
    gap: 8px;
    margin-top: 4px;
    grid-column: 1 / -1;
}

.clone-btn {
    background: #4a7ab5;
    padding: 8px 16px;
    font-size: 0.95em;
}

.clone-btn:hover:not(:disabled) {
    background: #3d6699;
}
</style>
