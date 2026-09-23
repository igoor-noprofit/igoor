<template>
    <div class="ttsdefault-plugin-settings form-grid">
        <!-- Fallback Only Checkbox -->
        <div class="form-label">{{ t('If checked, this voice will only be used for fallback from your main TTS plugin voice') }}</div>
        <div class="form-input">
            <input type="checkbox" v-model="formData.fallback_only" />
        </div>
        <div class="form-note"></div>

        <!-- Voice Selection -->
        <div class="form-label">{{ t('Select the voice to be used for speech synthesis') }}</div>
        <div class="form-input">
            <select v-model="formData.voice_id">
                <option v-for="voice in voiceList" :key="voice.voice_id" :value="voice.voice_id">
                    {{ voice.voice_label }}
                </option>
            </select>
        </div>
        <div class="form-note"></div>

        <!-- Test + Save buttons -->
        <div class="form-label"></div>
        <div class="form-input">
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                <button type="button" @click="testVoice" :disabled="voiceList.length === 0 || isTesting">
                    <span v-if="isTesting">{{ t('Testing...') }}</span>
                    <span v-else>{{ t('Test voice') }}</span>
                </button>
                <SaveSettingsButton
                    :hasChanges="hasChanges"
                    :loading="isSaving"
                    :t="t"
                    :lang="lang"
                    @save="handleSave"
                    @cancel="resetSettings"
                />
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';

export default {
    name: 'ttsdefaultSettings',
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
                fallback_only: false,
                voice_id: 0,
                voice_list: []
            },
            originalSettings: null,
            isSaving: false,
            isTesting: false,
            saveStatus: null
        };
    },
    computed: {
        hasChanges() {
            if (!this.originalSettings) return false;
            return JSON.stringify(this.formData) !== JSON.stringify(this.originalSettings);
        },
        voiceList() {
            return this.formData.voice_list || [];
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (!newVal) return;
                this.formData = { ...this.formData, ...newVal };
                this.originalSettings = JSON.parse(JSON.stringify(this.formData));
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
        resetSettings() {
            if (this.originalSettings) {
                this.formData = JSON.parse(JSON.stringify(this.originalSettings));
            }
        },
        async testVoice() {
            if (this.isTesting) return;
            this.isTesting = true;
            try {
                // Send the raw dropdown selection so the test speaks with the
                // voice being tried out, not the last saved one
                await this.callPluginRestEndpoint('ttsdefault', 'test_speak', {
                    method: 'POST',
                    data: {
                        message: this.t('Hello, how are you doing? I feel better today!'),
                        voice_id: this.formData.voice_id
                    }
                });
            } catch (error) {
                console.error('Error sending test message:', error);
            } finally {
                this.isTesting = false;
            }
        },
        async handleSave() {
            try {
                this.isSaving = true;
                this.saveStatus = null;

                 // Call set_voice endpoint to immediately update voice settings
                await this.callPluginRestEndpoint('ttsdefault', 'set_voice', {
                    method: 'POST',
                    data: {
                        voice_id: this.formData.voice_id,
                        fallback_only: this.formData.fallback_only
                    }
                });
                // Call BasePluginComponent's updateSettings method
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
        }
    }
};
</script>

<style scoped>
.ttsdefault-plugin-settings.form-grid {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 12px 18px;
    align-items: start;
    padding: 10px;
}

.form-label {
    font-weight: bold;
    text-align: right;
}

.form-input {
    display: flex;
    align-items: center;
}

.form-note {
    grid-column: 2 / span 1;
    font-size: 0.9em;
    color: #aaa;
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
</style>
