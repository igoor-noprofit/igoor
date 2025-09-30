<template>
    <div class="asrwhisper-plugin-settings form-grid">
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
        

        <!-- VAD Level -->
        <div class="form-label">{{t('VAD level')}}</div>
        <div class="form-input">
            <select name="vad_level" v-model.number="formData.vad_level" >
                <option value="-1">{{t('Disabled')}}</option>
                <option value="0">0 ({{t('Less aggressive')}})</option>
                <option value="1">1</option>
                <option value="2">2 ({{t('Recommended')}})</option>
                <option value="3">3 ({{t('Most aggressive')}})</option>
            </select>
        </div>
        <div class="form-note">
            {{t('The VAD level determines how aggressive the algorithm is at detecting speech.')}}<br>
            {{t('Higher levels work better in noisy environments. Disabled will bypass VAD entirely.')}}
        </div>

        <!-- Silence Frames -->
        <div class="form-label">{{t('Silence Frames')}}</div>
        <div class="form-input">
            <select name="silence_frames" v-model.number="formData.silence_frames">
                <option value="500">500: {{t('Faster ASR')}}</option>
                <option value="1250">1250: {{t('Recommended for most cases')}}</option>
                <option value="1500">1500: {{t('Recommended for most cases')}}</option>
                <option value="2000">2000: {{t('Slower ASR: For people making big pauses')}}</option>
            </select>
        </div>
        <div class="form-note">
            {{t('The lower,the faster the transcription starts,but risks of cutting people speaking after a pause')}}<br>
            {{t('The higher,the slower the transcription starts, but less risky for people making big pauses speaking')}}
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

        <!-- Save Button (spans all columns) -->
        <div class="form-label"></div>
        <div class="form-input">
            <button @click="checkBeforeUpdating">{{t('SAVE PLUGIN SETTINGS')}}</button>
        </div>
        <div class="form-note"></div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

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
    name: "asrwhisperSettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    data() {
        return {
            originalSettings: null,
            formData: {
                model_name: '',
                vad_level:'',
                silence_frames:1500,
                shortcut: '',
                voxtral_api_key: ''
            },
            isRecordingShortcut: false,
            voxtralKeyError: false
        };
    },
    computed: {
        hasChanges() {
            if (!this.originalSettings) return false;
            return Object.keys(this.formData).some(key => 
                JSON.stringify(this.formData[key]) !== JSON.stringify(this.originalSettings[key])
            );
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal) {
                    this.formData = { ...this.formData, ...newVal };
                    // Store original settings for comparison
                    this.originalSettings = JSON.parse(JSON.stringify(newVal));
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
            this.updateSettings(this.formData);
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
        }
    }
};
</script>

<style scoped>
.asrwhisper-plugin-settings.form-grid {
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
select, input[type="text"] {
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
</style>