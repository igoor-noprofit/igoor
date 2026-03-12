<template>
    <div class="asrjs-plugin-settings form-grid">
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

        <!-- Continuous Mode -->
        <div class="form-label">{{t('Continuous Mode')}}</div>
        <div class="form-input">
            <label class="toggle-switch">
                <input type="checkbox" v-model="formData.continuous" />
                <span class="toggle-slider"></span>
            </label>
            <span style="margin-left: 8px;">{{ formData.continuous ? t('Enabled') : t('Disabled') }}</span>
        </div>
        <div class="form-note">
            {{t('When enabled, the microphone listens continuously and automatically detects speech.')}}<br>
            {{t('When disabled, use the shortcut to manually start/stop recording.')}}
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
                {{t('Lower = more sensitive (may pick up noise), Higher = less sensitive (may miss soft speech)')}}<br>
                {{t('Default: 0.50')}}
            </div>

            <!-- Pause Tolerance (redemptionFrames) -->
            <div class="form-label">{{t('Pause Tolerance')}}</div>
            <div class="form-input">
                <select name="redemptionFrames" v-model.number="formData.redemptionFrames">
                    <option value="4">4 {{t('frames')}} (~80ms) - {{t('Fast')}}</option>
                    <option value="8">8 {{t('frames')}} (~160ms) - {{t('Default')}}</option>
                    <option value="12">12 {{t('frames')}} (~240ms) - {{t('Medium')}}</option>
                    <option value="16">16 {{t('frames')}} (~320ms) - {{t('Slow')}}</option>
                    <option value="24">24 {{t('frames')}} (~480ms) - {{t('Very slow')}}</option>
                </select>
            </div>
            <div class="form-note">
                {{t('How long to wait after speech stops before transcribing.')}}<br>
                {{t('Higher values help with speakers who pause frequently.')}}
            </div>

            <!-- Always Generate (bypass semantic VAD) -->
            <div class="form-label">{{t('Always Generate')}}</div>
            <div class="form-input">
                <label class="toggle-switch">
                    <input type="checkbox" v-model="formData.always_generate" />
                    <span class="toggle-slider"></span>
                </label>
                <span style="margin-left: 8px;">{{ formData.always_generate ? t('Enabled') : t('Disabled') }}</span>
            </div>
            <div class="form-note">
                {{t('When enabled, bypasses the semantic VAD check and generates immediately after speech ends.')}}<br>
                {{t('Useful for faster responses or when the semantic VAD is too conservative.')}}
            </div>
        </template>

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



        <!-- Save Button (spans all columns) -->
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
        <div class="form-note"></div>
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
    // Ignore modifier-only
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
            // Default values for new settings (for migration from old settings)
            defaultSettings: {
                positiveSpeechThreshold: 0.5,
                redemptionFrames: 8,
                continuous: false,
                always_generate: false
            },
            isRecordingShortcut: false,
            voxtralKeyError: false,
            loading: false
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
                    // Only set originalSettings after we've received initialSettings
                    this.$nextTick(() => {
                        this.setOriginalSettings(newVal);
                        // Merge with defaults to handle missing fields from old settings
                        this.formData = {
                            ...this.defaultSettings,
                            ...newVal
                        };
                    });
                }
            },
            immediate: true,
            deep: true
        }
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
            // Only set shortcut if a non-modifier key is pressed
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
            // Reset model_name if not compatible with provider
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
            // Require Voxtral API key if voxtral model is selected
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
        }
    }
};
</script>

<style scoped>
.asrjs-plugin-settings.form-grid {
    display: grid;
    grid-template-columns: 200px 1fr 2fr;
    gap: 12px 18px;
    align-items: start;
    background: none;
    padding: 18px 0;
}
.form-label {
    font-weight: 500;
    padding-top: 6px;
    color: #e0e0e0;
    text-align: right;
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
select, input[type="text"], input[type="url"], input[type="password"], input[type="number"] {
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
.input-error {
    border-color: #ff6666;
    background: #2a1818;
}
/* Toggle switch styles */
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
</style>
