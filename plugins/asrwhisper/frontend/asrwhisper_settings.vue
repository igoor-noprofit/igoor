<template>
    <div class="asrwhisper-plugin-settings form-grid">
        <!-- Model Name -->
        <div class="form-label">{{t('Model name')}}</div>
        <div class="form-input">
            <select name="model_name" v-model="formData.model_name">
                <option value="whisper-large-v3">Whisper Large v3</option>
                <option value="whisper-large-v3-turbo">Whisper Large v3 Turbo</option>
            </select>
        </div>
        <div class="form-note"></div>

        <!-- VAD Level -->
        <div class="form-label">{{t('VAD level')}}</div>
        <div class="form-input">
            <select name="vad_level" v-model="formData.vad_level">
                <option value="0">0 ({{t('Less aggressive')}})</option>
                <option value="1">1</option>
                <option value="2">2 ({{t('Recommended')}})</option>
                <option value="3">3 ({{t('Most aggressive')}})</option>
            </select>
        </div>
        <div class="form-note">
            {{t('The VAD level determines how aggressive the algorithm is at detecting speech.')}}<br>
            {{t('Higher levels works better in noisy environments. ')}}
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
            {{t('The lower, the faster the speech detection, but also less quality.')}}<br>
            {{t('The higher, the slower the speech detection, but better quality')}}
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
        </div>

        <!-- Save Button (spans all columns) -->
        <div class="form-label"></div>
        <div class="form-input">
            <button @click="updateSettings">{{t('SAVE PLUGIN SETTINGS')}}</button>
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
            formData: {
                model_name: '',
                vad_level:'',
                silence_frames:1500,
                shortcut: ''
            },
            isRecordingShortcut: false
        };
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal) {
                    this.formData = { ...this.formData, ...newVal };
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
        }
    }
};
</script>

<style>
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
</style>