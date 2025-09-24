<template>
    <div class="speechifytts-plugin-settings form-grid">
        <!-- API Key -->
        <div class="form-label">{{ t('API Key') }}</div>
        <div class="form-input">
            <input type="text" v-model="formData.api_key" :class="{'input-error': apiKeyError}" placeholder="{{ t('Required') }}" />
        </div>
        <div class="form-note" :style="{color: apiKeyError ? '#ff6666' : undefined}">
            {{ apiKeyError ? t('API Key is required') : t('API Key used to authenticate with the TTS provider') }}
        </div>

        <!-- Voice ID -->
        <div class="form-label">{{ t('Voice ID') }}</div>
        <div class="form-input">
            <input type="text" v-model="formData.voice_id" :class="{'input-error': voiceIdError}" placeholder="{{ t('Required') }}" />
        </div>
        <div class="form-note" :style="{color: voiceIdError ? '#ff6666' : undefined}">
            {{ voiceIdError ? t('Voice ID is required') : t('The voice identifier to use for synthesis') }}
        </div>

        <!-- model_id hidden -->
        <div class="form-label" style="display:none">{{ t('Model ID') }}</div>
        <div class="form-input" style="display:none">
            <input type="text" v-model="formData.model_id" />
        </div>
        <div class="form-note" style="display:none"></div>

        <!-- Use SSML Toggle -->
        <div class="form-label">{{ t('Use SSML') }}</div>
        <div class="form-input">
            <input type="checkbox" id="use_ssml" v-model="formData.use_ssml" />
        </div>
        <div class="form-note">{{ t('When enabled, you can fine-tune pitch, rate and volume using the sliders.') }}</div>

        <!-- Advanced controls card -->
        <div class="form-label"></div>
        <div class="form-input" style="grid-column: 2 / span 2; padding: 10px 0;">
            <div v-if="formData.use_ssml" class="ssml-card">
                <!-- Pitch Row -->
                <div class="ssml-card-header">
                    <div></div>
                    <div style="text-align:right">
                        <button class="reset-button" type="button" @click="resetControllers">{{ t('Reset') }}</button>
                    </div>
                </div>

                <div class="ssml-row">
                    <div class="ssml-left">🎚️ {{ t('Pitch') }}</div>
                    <div class="ssml-center">
                        <input type="range" :min="pitchRange.min" :max="pitchRange.max" step="1" v-model.number="pitchValue" @input="onPitchChange" />
                    </div>
                    <div class="ssml-right">
                        <input type="number" class="numeric-input" v-model.number="pitchValue" @change="onPitchChange" />
                        <span style="margin-left:8px">%</span>
                    </div>
                </div>

                <!-- Rate Row -->
                <div class="ssml-row">
                    <div class="ssml-left">⏩ {{ t('Rate') }}</div>
                    <div class="ssml-center">
                        <input type="range" :min="rateRange.min" :max="rateRange.max" step="1" v-model.number="rateValue" @input="onRateChange" />
                    </div>
                    <div class="ssml-right">
                        <input type="number" class="numeric-input" v-model.number="rateValue" @change="onRateChange" />
                        <span style="margin-left:8px">%</span>
                    </div>
                </div>

                <!-- Volume Row -->
                <div class="ssml-row">
                    <div class="ssml-left">🔊 {{ t('Volume') }}</div>
                    <div class="ssml-center">
                        <input type="range" :min="volumeRange.min" :max="volumeRange.max" step="1" v-model.number="volumeValue" @input="onVolumeChange" />
                    </div>
                    <div class="ssml-right">
                        <input type="number" class="numeric-input" v-model.number="volumeValue" @change="onVolumeChange" />
                        <span style="margin-left:8px">%</span>
                    </div>
                </div>

            </div>
        </div>
        <div class="form-note"></div>

        <!-- Save Button -->
        <div class="form-label"></div>
        <div class="form-input">
            <button @click="checkBeforeUpdating" :disabled="!hasChanges || apiKeyError || voiceIdError || isSaving" :class="{disabled: !hasChanges || apiKeyError || voiceIdError || isSaving}">{{ t('SAVE PLUGIN SETTINGS') }}</button>
            <div v-if="saveStatus" style="margin-left:12px;">
                <span v-if="saveStatus.type==='success'" style="color:#3ca23c">{{ saveStatus.message }}</span>
                <span v-else style="color:#ff6666">{{ saveStatus.message }}</span>
            </div>
             <div style="text-align:left">
                <button class="" type="button" @click="testVoice">{{ t('Test voice') }}</button>
            </div>
        </div>
        <div class="form-note"></div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: 'speechifyttsSettings',
    mixins: [BasePluginComponent],
    props: {
        initialSettings: Object
    },
    data() {
        return {
            formData: {
                api_key: '',
                voice_id: '',
                model_id: '',
                use_ssml: false,
                pitch: 0, // percent centered at 0, stored as integer percent
                rate: 0,  // percent centered at 0
                volume: 0 // percent or dB depending on mode; default percent
            },
            originalSettings: null,
            apiKeyError: false,
            voiceIdError: false,
            // Pitch config
            pitchRange: { min: -83, max: 100 },
            // removed presets
            // Rate config
            rateRange: { min: -50, max: 200 },
            // Volume config (percent only)
            volumeRange: { min: -100, max: 100 },
            // local v-model backing values
            pitchValue: 0,
            rateValue: 0,
            volumeValue: 0,
            isSaving: false,
            saveStatus: null
        };
    },
    computed: {
        hasChanges() {
            if (!this.originalSettings) return false;
            const keys = ['api_key','voice_id','model_id','use_ssml','pitch','rate','volume'];
            return keys.some(k => JSON.stringify(this.formData[k]) !== JSON.stringify(this.originalSettings[k]));
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (!newVal) return;
                this.formData = { ...this.formData, ...newVal };
                // initialize local slider values
                this.pitchValue = Number(newVal.pitch ?? this.formData.pitch ?? 0);
                this.rateValue = Number(newVal.rate ?? this.formData.rate ?? 0);
                // volume might be stored as a string like "100%" or a dB string; convert to integer percent
                let vol = newVal.volume ?? this.formData.volume ?? 0;
                if (typeof vol === 'string') {
                    if (vol.endsWith('%')) {
                        this.volumeValue = Number(vol.replace('%',''));
                    } else if (vol.toLowerCase().endsWith('db')) {
                        // convert dB -> percent using the same naive mapping used previously
                        let db = Number(vol.toLowerCase().replace('db',''));
                        let pct = ((db + 60) / (12 + 60)) * 200 - 100;
                        this.volumeValue = Math.round(pct);
                    } else {
                        // fallback: strip non-numeric chars
                        let n = Number((vol+'').replace(/[^0-9+\-\.]/g, '')) || 0;
                        this.volumeValue = n;
                    }
                } else {
                    this.volumeValue = Number(vol);
                }
                // store original settings snapshot for change detection
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
        onPitchChange() {
            // clamp and store integer percent
            if (this.pitchValue < this.pitchRange.min) this.pitchValue = this.pitchRange.min;
            if (this.pitchValue > this.pitchRange.max) this.pitchValue = this.pitchRange.max;
            this.formData.pitch = Math.round(this.pitchValue);
        },
        onRateChange() {
            if (this.rateValue < this.rateRange.min) this.rateValue = this.rateRange.min;
            if (this.rateValue > this.rateRange.max) this.rateValue = this.rateRange.max;
            this.formData.rate = Math.round(this.rateValue);
        },
        onVolumeChange() {
            // percent-only handling; clamp and store integer percent
            if (this.volumeValue < -100) this.volumeValue = -100;
            if (this.volumeValue > 100) this.volumeValue = 100;
            this.formData.volume = Math.round(this.volumeValue);
        },
        resetControllers() {
            this.pitchValue = 0;
            this.rateValue = 0;
            this.volumeValue = 0;
            this.formData.pitch = 0;
            this.formData.rate = 0;
            this.formData.volume = 0;
        },
        async testVoice(){
            this.formData.pitch = Math.round(this.pitchValue);
            this.formData.rate = Math.round(this.rateValue);
            this.formData.volume = Math.round(this.volumeValue);
            let msg=this.t('Hello, how are you doing? I feel better today!')
            let testData = this.formData;
            testData['action'] = 'test_speak';
            testData['message'] = msg;
            console.warn("TEST SPEAK DATA", testData);
            const result = this.sendMsgToBackend(JSON.stringify(testData),'speechifytts');
            console.warn(result);
        },
        async checkBeforeUpdating() {
            this.apiKeyError = !this.formData.api_key || !this.formData.api_key.trim();
            this.voiceIdError = !this.formData.voice_id || !this.formData.voice_id.trim();
            if (this.apiKeyError || this.voiceIdError) return;

            // ensure pitch/rate/volume are integers
            this.formData.pitch = Math.round(this.pitchValue);
            this.formData.rate = Math.round(this.rateValue);
            this.formData.volume = Math.round(this.volumeValue);

            try {
                this.isSaving = true;
                this.saveStatus = null;
                await this.updateSettings();
                this.saveStatus = { type: 'success', message: this.t('Settings saved') };
                // refresh original snapshot so hasChanges becomes false
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
            } catch (err) {
                console.error('Error saving settings', err);
                this.saveStatus = { type: 'error', message: this.t('Failed to save settings') };
            } finally {
                this.isSaving = false;
                setTimeout(() => { this.saveStatus = null; }, 3000);
            }
        }
    }
};
</script>

<style>
.speechifytts-plugin-settings.form-grid {
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
select, input[type="text"], input[type="number"] {
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
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.04);
    padding: 12px;
    border-radius: 8px;
    width: 100%;
}
.ssml-row {
    display: grid;
    grid-template-columns: 120px 1fr 220px;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
}
.ssml-left { color: #e8e8e8; font-weight: 600; }
.ssml-center { padding: 0 12px; }
.ssml-center input[type="range"] { width: 100%; }
.ssml-right { display:flex; align-items:center; justify-content:flex-end; gap:8px; }
.numeric-input { width: 80px; }
</style>
