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

        <!-- Save Button -->
        <div class="form-label"></div>
        <div class="form-input">
            <button @click="updateSettings" :disabled="!hasChanges">{{ t('SAVE PLUGIN SETTINGS') }}</button>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: 'ttsdefaultSettings',
    mixins: [BasePluginComponent],
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
        async checkBeforeUpdating() {
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
</style>
