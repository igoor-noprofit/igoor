<template>
    <div class="localtts-plugin-settings form-grid bio-container">
        <div class="bio left">
            <!-- Model status -->
            <div class="form-label">{{ t('Model status') }}</div>
            <div class="form-input">
                <div class="model-status" :class="'status-' + modelStatus.state">
                    <i :class="statusIcon" class="ph-light"></i>
                    <span>{{ statusText }}</span>
                </div>
            </div>
            <div class="form-input" v-if="modelStatus.state === 'error' || modelStatus.state === 'not_downloaded'">
                <button class="retry-btn" type="button" @click="retryDownload" :disabled="isRetrying">
                    {{ t('Retry download') }}
                </button>
            </div>
            <div class="form-note">{{ t('The model (~820 MB) is downloaded once, when the plugin is activated. Synthesis then runs fully offline.') }}</div>

            <!-- Voice Selection -->
            <div class="form-label">{{ t('Choose a voice for synthesis') }}</div>
            <div class="form-input">
                <select v-model="formData.voice" :disabled="!voices.length" class="voice-selector">
                    <option disabled value="">{{ t('Select a voice') }}</option>
                    <option v-for="voice in voices" :key="voice.id" :value="voice.id">
                        {{ voice.display_name }}
                    </option>
                </select>
            </div>
            <div class="form-note"></div>

            <!-- Voice registration -->
            <div class="form-label">{{ t('Voice registration') }}</div>
            <div class="form-input">
                <div class="voice-register-section">
                    <input type="text" v-model="registerTranscript" class="text-input"
                        :placeholder="t('Exact transcript of the recording')" />
                </div>
                <div class="voice-register-section">
                    <input type="text" v-model="registerName" class="text-input"
                        :placeholder="t('Voice name')" />
                    <button class="register-btn" type="button" @click="triggerUploadRegister"
                        :disabled="isRegistering || !registerTranscript.trim() || !registerName.trim() || !modelReady">
                        <span v-if="isRegistering">{{ t('Registering...') }}</span>
                        <span v-else><i class="ph-light ph-upload-simple"></i> {{ t('Register from audio') }}</span>
                    </button>
                    <input type="file" ref="registerFileInput" style="display:none"
                        accept=".wav,.mp3,.ogg,.webm,.flac" @change="onRegisterFileSelected" />
                </div>
            </div>
            <div class="form-note">{{ t('Register a new voice from a 0.5-30 s recording and its exact transcript.') }}</div>
        </div>

        <div class="bio right">
            <!-- Save + Test -->
            <div class="form-label"></div>
            <div class="form-input">
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                    <button type="button" @click="testVoice" :disabled="!modelReady || !formData.voice">{{ t('Test voice') }}</button>
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

            <!-- Performance card -->
            <div class="form-label"></div>
            <div class="form-input" style="grid-column: 2 / span 2; padding: 10px 0;">
                <div class="ssml-card">
                    <div class="ssml-card-header"
                        style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div>{{ t('Performance') }}</div>
                    </div>
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('CPU threads') }}</div>
                        <div class="ssml-center">
                            <input type="range" :min="1" :max="8" step="1" v-model.number="threadsValue" @input="onThreadsChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="threadsValue"
                                @change="onThreadsChange" min="1" max="8" />
                        </div>
                    </div>
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Temperature') }}</div>
                        <div class="ssml-center">
                            <input type="range" :min="0.1" :max="1.0" step="0.05" v-model.number="temperatureValue" @input="onTemperatureChange" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="temperatureValue"
                                @change="onTemperatureChange" step="0.05" min="0.1" max="1.0" />
                        </div>
                    </div>
                    <div class="ssml-row">
                        <div class="ssml-left">{{ t('Max length (tokens)') }}</div>
                        <div class="ssml-center">
                            <input type="range" :min="100" :max="1500" step="50" v-model.number="formData.max_new_tokens" />
                        </div>
                        <div class="ssml-right">
                            <input type="number" class="numeric-input" v-model.number="formData.max_new_tokens" min="100" max="1500" />
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
    name: 'localttsSettings',
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
                voice: 'default',
                threads: 5,
                temperature: 0.7,
                max_new_tokens: 800
            },
            originalSettings: null,
            voices: [],
            modelStatus: { state: 'unknown', detail: '', voices: [] },
            isSaving: false,
            isRegistering: false,
            isRetrying: false,
            saveStatus: null,
            registerTranscript: '',
            registerName: '',
            threadsValue: 5,
            temperatureValue: 0.7
        };
    },
    computed: {
        hasChanges() {
            if (!this.originalSettings) return false;
            const keys = ['voice', 'threads', 'temperature', 'max_new_tokens'];
            return keys.some(k => JSON.stringify(this.formData[k]) !== JSON.stringify(this.originalSettings[k]));
        },
        modelReady() {
            return this.modelStatus.state === 'ready';
        },
        statusIcon() {
            switch (this.modelStatus.state) {
                case 'ready': return 'ph-check-circle';
                case 'downloading': return 'ph-download-simple';
                case 'loading': return 'ph-hourglass';
                case 'error': return 'ph-warning-circle';
                default: return 'ph-circle-dashed';
            }
        },
        statusText() {
            switch (this.modelStatus.state) {
                case 'ready': return this.t('Model ready');
                case 'downloading': return this.t('Downloading model (~820 MB, one time)...');
                case 'loading': return this.t('Loading model...');
                case 'error': return this.t('Download error') + (this.modelStatus.detail ? ' - ' + this.modelStatus.detail : '');
                default: return this.t('Checking model status...');
            }
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (!newVal) return;
                this.formData = { ...this.formData, ...newVal };
                this.threadsValue = Number(newVal.threads ?? 5);
                this.temperatureValue = Number(newVal.temperature ?? 0.7);
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
        onThreadsChange() {
            this.threadsValue = Math.max(1, Math.min(8, parseInt(this.threadsValue) || 5));
            this.formData.threads = this.threadsValue;
        },
        onTemperatureChange() {
            this.temperatureValue = Math.max(0.1, Math.min(1.0, parseFloat(this.temperatureValue) || 0.7));
            this.formData.temperature = parseFloat(this.temperatureValue.toFixed(2));
        },
        async refreshStatus() {
            try {
                const data = await this.callPluginRestEndpoint('localtts', 'status');
                this.modelStatus = data;
                if (Array.isArray(data.voices)) {
                    this.voices = data.voices;
                }
            } catch (e) {
                console.error('Error fetching localtts status:', e);
            }
        },
        async retryDownload() {
            this.isRetrying = true;
            try {
                await this.callPluginRestEndpoint('localtts', 'download_model', { method: 'POST', data: {} });
                this.modelStatus.state = 'downloading';
            } catch (e) {
                console.error('Error triggering download:', e);
            } finally {
                this.isRetrying = false;
            }
        },
        triggerUploadRegister() {
            this.$refs.registerFileInput.click();
        },
        async onRegisterFileSelected(event) {
            const file = event.target.files[0];
            if (!file) return;
            this.isRegistering = true;
            try {
                const form = new FormData();
                form.append('audio_file', file);
                form.append('text', this.registerTranscript.trim());
                form.append('name', this.registerName.trim());
                const response = await fetch('/api/plugins/localtts/register_voice', {
                    method: 'POST',
                    body: form
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Registration failed');
                }
                const data = await response.json();
                this.formData.voice = data.voice;
                await this.refreshStatus();
                this.saveStatus = { type: 'success', message: this.t('Voice registered successfully') };
                setTimeout(() => { this.saveStatus = null; }, 3000);
            } catch (e) {
                console.error('Register error:', e);
                this.saveStatus = { type: 'error', message: e.message || this.t('Failed to register voice') };
                setTimeout(() => { this.saveStatus = null; }, 5000);
            } finally {
                this.isRegistering = false;
                event.target.value = '';
            }
        },
        async testVoice() {
            const testData = { ...this.formData };
            testData['message'] = this.t('Hello, how are you doing? I feel better today!');
            try {
                await this.callPluginRestEndpoint('localtts', 'test_speak', { method: 'POST', data: testData });
            } catch (error) {
                console.error('Error sending test message:', error);
            }
        },
        resetSettings() {
            if (this.originalSettings) {
                this.formData = JSON.parse(JSON.stringify(this.originalSettings));
                this.threadsValue = this.formData.threads;
                this.temperatureValue = this.formData.temperature;
            }
        },
        async checkBeforeUpdating() {
            try {
                this.isSaving = true;
                this.saveStatus = null;
                await this.updateSettings();
                this.saveStatus = { type: 'success', message: this.t('Settings saved') };
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
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
            if (payload && payload.type === 'model_status') {
                this.modelStatus = payload;
                if (Array.isArray(payload.voices)) {
                    this.voices = payload.voices;
                }
                return true;
            }
            if (payload && payload.type === 'voice_list') {
                this.voices = Array.isArray(payload.voice_list) ? payload.voice_list.slice() : [];
                return true;
            }
            return false;
        }
    },
    async created() {
        await this.loadTranslations();
        await this.refreshStatus();
    }
};
</script>

<style scoped>
.localtts-plugin-settings.form-grid {
    gap: 12px 18px;
    align-items: start;
    background: none;
    padding: 10px;
}

.form-input {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
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

select,
input[type="text"],
input[type="number"] {
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

.model-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 1.05em;
    padding: 8px 12px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.04);
    width: 100%;
}

.model-status i {
    font-size: 1.4em;
}

.status-ready {
    color: #3ca23c;
}

.status-downloading,
.status-loading {
    color: #d4a017;
}

.status-error {
    color: #ff6666;
}

.retry-btn {
    background: #216776;
}

.retry-btn:hover:not(:disabled) {
    background: #2a8fa8;
}

.voice-register-section {
    display: flex;
    gap: 8px;
    width: 100%;
    margin-top: 4px;
}

.register-btn {
    background: #216776;
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 0.9em;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
    white-space: nowrap;
}

.register-btn:hover:not(:disabled) {
    background: #2a8fa8;
}

.register-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.text-input {
    flex: 1;
    min-width: 60%;
    background: #222;
    color: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 0.9em;
}

/* Card shared with elevenlabstts layout */
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
</style>
