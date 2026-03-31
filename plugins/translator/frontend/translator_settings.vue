<template>
    <div class="translator-plugin-settings form-grid">
        <!-- Description -->
        <div class="form-label"></div>
        <div class="form-input description-text">
            {{ t('Enable translation between you and your interlocutor. Incoming speech will be translated to your language, outgoing speech to the interlocutor\'s language.') }}
        </div>
        <div class="form-note"></div>

        <!-- Interlocutor Language -->
        <div class="form-label">{{ t('Interlocutor\'s Language') }}</div>
        <div class="form-input">
            <select v-model="formData.interlocutor_language">
                <option value="">{{ t('Select a language') }}</option>
                <option value="French">{{ t('French') }}</option>
                <option value="English">{{ t('English') }}</option>
                <option value="Italian">{{ t('Italian') }}</option>
                <option value="Spanish">{{ t('Spanish') }}</option>
                <option value="German">{{ t('German') }}</option>
                <option value="Portuguese">{{ t('Portuguese') }}</option>
                <option value="Dutch">{{ t('Dutch') }}</option>
                <option value="Polish">{{ t('Polish') }}</option>
                <option value="Russian">{{ t('Russian') }}</option>
                <option value="Chinese">{{ t('Chinese') }}</option>
                <option value="Japanese">{{ t('Japanese') }}</option>
                <option value="Korean">{{ t('Korean') }}</option>
                <option value="Arabic">{{ t('Arabic') }}</option>
            </select>
        </div>
        <div class="form-note">{{ t('The language spoken by the person you are conversing with') }}</div>

        <!-- Translate Incoming -->
        <div class="form-label">{{ t('Translate Incoming Speech') }}</div>
        <div class="form-input">
            <label class="switch">
                <input type="checkbox" v-model="formData.translate_incoming">
                <span class="slider round"></span>
            </label>
        </div>
        <div class="form-note">{{ t('Translate what your interlocutor says to your language') }}</div>

        <!-- Translate Outgoing -->
        <div class="form-label">{{ t('Translate Outgoing Speech') }}</div>
        <div class="form-input">
            <label class="switch">
                <input type="checkbox" v-model="formData.translate_outgoing">
                <span class="slider round"></span>
            </label>
        </div>
        <div class="form-note">{{ t('Translate what you say to your interlocutor\'s language') }}</div>

        <!-- Translation Model (Optional) -->
        <div class="form-label">{{ t('Translation Model (optional)') }}</div>
        <div class="form-input">
            <input
                type="text"
                v-model="formData.translation_model_name"
                :placeholder="t('Leave empty to use default AI model')"
            />
        </div>
        <div class="form-note">{{ t('Specify a faster/lighter model for translations. Uses the main AI model if empty.') }}</div>

        <!-- Save Button -->
        <div class="form-label"></div>
        <div class="form-input">
            <SaveSettingsButton
                :hasChanges="hasUnsavedChanges"
                :loading="isSaving"
                :t="t"
                :lang="lang"
                @save="saveSettingsHandler"
                @cancel="resetSettings"
            />
        </div>
        <div class="form-note"></div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';

export default {
    name: "translatorSettings",
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
                interlocutor_language: '',
                translate_incoming: false,
                translate_outgoing: false,
                translation_model_name: ''
            },
            isSaving: false
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
                console.log('translatorSettings: initialSettings watcher triggered', newVal);
                if (newVal) {
                    this.$nextTick(() => {
                        this.setOriginalSettings(newVal);
                        this.formData = { ...newVal };
                        console.log('translatorSettings: formData updated', this.formData);
                    });
                }
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
        async saveSettingsHandler() {
            console.log('translatorSettings: Saving settings', this.formData);
            this.isSaving = true;
            try {
                await this.saveSettings();
                console.log('translatorSettings: Settings saved successfully');
            } finally {
                this.isSaving = false;
            }
        }
    }
};
</script>

<style scoped>
.translator-plugin-settings.form-grid {
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

.description-text {
    color: #ccc;
    font-size: 0.95em;
    line-height: 1.5;
    max-width: 500px;
}

select, input[type="text"] {
    background: #222;
    color: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 1em;
    width: 100%;
    max-width: 300px;
}

select:focus, input[type="text"]:focus{
    border-color: var(--color-inputfocus-border, #0095c0);
    outline: none;
}

/* Toggle Switch */
.switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 28px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #444;
    transition: 0.3s;
    border-radius: 28px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
}

input:checked + .slider {
    background-color: #407d1c;
}

input:checked + .slider:before {
    transform: translateX(22px);
}
</style>
