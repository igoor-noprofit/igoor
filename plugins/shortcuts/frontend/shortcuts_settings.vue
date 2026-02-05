<template>
    <div class="shortcuts-plugin-settings form-grid">
        <!-- Help button mode -->
        <div class="form-label">{{ t('Help button mode') }}</div>
        <div class="form-input">
            <button
                class="mode-toggle-btn btn-secondary"
                :class="{ 'active': formData.help_mode === 'speak' }"
                @click="formData.help_mode = 'speak'"
            >
                <svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-talk"></use>
                </svg>
                <h3>{{ t('Speak') }}</h3>
            </button>
            <button
                class="mode-toggle-btn btn-secondary"
                :class="{ 'active': formData.help_mode === 'sound' }"
                @click="formData.help_mode = 'sound'"
            >
                <svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-sos"></use>
                </svg>
                <h3>{{ t('Play sound') }}</h3>
            </button>
        </div>
        <div class="form-note"></div>

        <!-- Number of repetitions -->
        <div class="form-label">{{ t('Number of repetitions (0 = forever)') }}</div>
        <div class="form-input">
            <input
                type="number"
                v-model.number="formData.alert_repetitions"
                :min="0"
                placeholder="3"
            />
        </div>
        <div class="form-note">{{ t('0 means repeat forever') }}</div>

        <!-- Frequency interval -->
        <div class="form-label">{{ t('Frequency interval (seconds)') }}</div>
        <div class="form-input">
            <input
                type="number"
                v-model.number="formData.alert_interval"
                :min="1"
                placeholder="15"
            />
        </div>
        <div class="form-note"></div>

        <!-- Test sound button -->
        <div class="form-label"></div>
        <div class="form-input">
            <button
                class="test-sound-btn"
                @click="testSound"
                :disabled="formData.help_mode !== 'sound'"
            >
                <svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-sos"></use>
                </svg>
                <h3>{{ t('Test sound') }}</h3>
            </button>
        </div>
        <div class="form-note"></div>

        <!-- Save Button -->
        <div class="form-label"></div>
        <div class="form-input">
            <SaveSettingsButton
                :hasChanges="hasUnsavedChanges"
                :loading="isSaving"
                :t="t"
                :lang="lang"
                @save="saveSettings"
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
    name: "shortcutsSettings",
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
                help_mode: 'speak',
                alert_repetitions: 3,
                alert_interval: 15
            },
            isSaving: false
        };
    },
    methods: {
        async testSound() {
          console.log('testing alert sound');
            try {
                const audio = new Audio('/plugins/shortcuts/alerte.wav');
                await audio.play();
            } catch (error) {
                console.error('Error playing test sound:', error);
            }
        },
        async saveSettings() {
            console.log('Saving shortcuts settings:', this.formData);
            this.isSaving = true;
            try {
                await BasePluginComponent.methods.saveSettings.call(this);
                // Dispatch event to notify other components
                window.dispatchEvent(new CustomEvent('settings-updated', { detail: { plugin: 'shortcuts' } }));
            } finally {
                this.isSaving = false;
            }
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                console.log('initialSettings watcher triggered, newVal:', newVal);
                if (newVal) {
                    this.$nextTick(() => {
                        this.setOriginalSettings(newVal);
                        this.formData = { ...newVal };
                        console.log('formData after initialization:', this.formData);
                    });
                }
            },
            immediate: true,
            deep: true
        }
    }
};
</script>

<style scoped>
.shortcuts-plugin-settings.form-grid {
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
    flex-wrap: wrap;
}

.form-note {
    font-size: 0.97em;
    color: #aaa;
    line-height: 1.4;
    padding-top: 2px;
    text-align: left;
}

input[type="text"],
input[type="password"],
input[type="number"] {
    background: #222;
    color: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 1em;
    width: 100%;
    max-width: 200px;
}

input[type="number"] {
    width: 100px;
}

input:focus {
    outline: none;
    border-color: var(--color-inputfocus-border, #0095c0);
    background: var(--color-inputfocus-bg, #1f474f);
}

.mode-toggle-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 12px 20px;
    background: #444;
    color: #aaa;
    cursor: pointer;
    transition: background 0.2s, box-shadow 0.2s, color 0.2s;
    min-width: 140px;
    height: 80px;
}

.mode-toggle-btnbtn-secondary:hover {
    background: #555;
    color: #fff;
}

.mode-toggle-btn.btn-secondary.active {
    background: var(--color-btn-other, #407d1c) !important;
    color: #fff;
}

.mode-toggle-btn .icon {
    width: 48px;
    height: 48px;
}

.mode-toggle-btn h3 {
    margin: 0;
    font-size: 1em;
}

.test-sound-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 12px 20px;
    background: var(--color-btn-other, #407d1c);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, box-shadow 0.2s;
    min-width: 140px;
    height: 80px;
}

.test-sound-btn:hover {
    background: var(--color-btn-rollover-other, #3ca23c);
}

.test-sound-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.test-sound-btn .icon {
    width: 48px;
    height: 48px;
}

.test-sound-btn h3 {
    margin: 0;
    font-size: 1em;
}

button {
    background: var(--color-btn-base, #216776);
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
}

button:hover {
    background: var(--color-btn-rollover-base, #0095c0);
}

button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-secondary {
    background: var(--color-btn-other, #407d1c);
}

.btn-secondary:hover {
    background: var(--color-btn-rollover-other, #3ca23c);
}
</style>
