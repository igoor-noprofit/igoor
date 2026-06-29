<template>
    <div class="shortcuts-plugin-settings form-grid bio-container">
        <!-- LEFT COLUMN: button visibility toggles -->
        <div class="bio left">
            <div class="form-label">
                {{ t('Visible buttons') }}
                <HelpPopover
                    :text="t('Uncheck to hide a button from the footer')"
                    :t="t"
                    :lang="lang"
                />
            </div>
            <div class="form-input button-toggles">
                <label
                    v-for="button in buttonList"
                    :key="button.key"
                    class="button-toggle-row"
                >
                    <span class="switch">
                        <input
                            type="checkbox"
                            v-model="formData.button_visibility[button.key]"
                        />
                        <span class="slider round"></span>
                    </span>
                    <span class="button-toggle-label">{{ t(button.label) }}</span>
                </label>
            </div>
        </div>

        <!-- RIGHT COLUMN: Save/Cancel always at top; help-button settings below (only when Help is visible) -->
        <div class="bio right">
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

            <div class="help-settings" v-if="formData.button_visibility.help">
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
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';
import HelpPopover from '/js/HelpPopover.vue';

export default {
    name: "shortcutsSettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    components: {
        SaveSettingsButton,
        HelpPopover
    },
    data() {
        return {
            formData: {
                help_mode: 'speak',
                alert_repetitions: 3,
                alert_interval: 15,
                button_visibility: {
                    drink: true,
                    toilet: true,
                    parole: true,
                    yes: true,
                    no: true,
                    thanks: true,
                    inform: true,
                    repeat: true,
                    help: true
                }
            },
            // Mirrors the footer button list (keys/labels). No custom buttons.
            buttonList: [
                { key: 'drink', label: 'Drink' },
                { key: 'toilet', label: 'Toilet' },
                { key: 'parole', label: 'Just a sec' },
                { key: 'yes', label: 'Yes' },
                { key: 'no', label: 'No' },
                { key: 'thanks', label: 'Thanks' },
                { key: 'inform', label: 'I speak via a tool' },
                { key: 'repeat', label: 'Repeat' },
                { key: 'help', label: 'Help!' }
            ],
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
                        // Merge saved settings over the defaults so partial
                        // objects (e.g. button_visibility missing keys) keep
                        // their default values instead of being wiped.
                        const merged = {
                            ...this.formData,
                            ...newVal,
                            button_visibility: {
                                ...this.formData.button_visibility,
                                ...(newVal.button_visibility || {})
                            }
                        };
                        this.formData = merged;
                        // Snapshot the SAME merged shape so hasUnsavedChanges
                        // compares like-for-like.
                        this.setOriginalSettings(merged);
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
/* Two-panel layout: LEFT = button toggles, RIGHT = help-button settings */
.shortcuts-plugin-settings.bio-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px 18px;
    align-items: start;
    background: none;
    padding: 10px;
}

.bio {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* Within each panel, a label/input/note row sits on its own line */
.bio .form-label,
.bio .form-input,
.bio .form-note {
    width: 100%;
}

.form-label {
    font-weight: 500;
    padding-top: 6px;
    color: #e0e0e0;
    text-align: left;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
}

/* The help trigger carries its own margin-left for inline contexts; inside a
   flex form-label the container gap already handles spacing, so neutralize it. */
.form-label .help-trigger {
    margin-left: 0;
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

.button-toggles {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
}

.button-toggle-row {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    font-size: 1em;
    color: #e0e0e0;
}

.button-toggle-label {
    user-select: none;
}
</style>
