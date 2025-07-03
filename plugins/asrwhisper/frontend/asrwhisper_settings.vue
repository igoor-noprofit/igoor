<template>
    <div class="asrwhisper-plugin-settings">
        <field>
            <label>{{t('Model name')}}</label>
            <select name="model_name" v-model="formData.model_name">
                <option value="whisper-large-v3">Whisper Large v3</option>
                <option value="whisper-large-v3-turbo">Whisper Large v3 Turbo</option>
            </select>
        </field>
        <field>
            <label>{{t('VAD level')}}</label>
            <select name="vad_level" v-model="formData.vad_level">
                <option value="0">0 ({{t('Less aggressive')}})</option>
                <option value="1">1</option>
                <option value="2">2 ({{t('Recommended')}})</option>
                <option value="3">3 ({{t('Most aggressive')}})</option>
            </select>
            <p>
                {{t('The VAD level determines how aggressive the algorithm is at detecting speech.')}}
                <br>{{t('Higher levels works better in noisy environments. ')}}
            </p>
        </field>
        <field>
            <label>{{t('Silence Frames')}}</label>
            <select name="silence_frames" v-model="formData.silence_frames">
                <option value="500">500: {{t('Faster ASR')}}</option>
                <option value="1250">1250: {{t('Recommended for most cases')}}</option>
                <option value="1500">1500: {{t('Recommended for most cases')}}</option>
                <option value="2000">2000: {{t('Slower ASR: For people making big pauses')}}</option>
            </select>
            <p>{{t('The lower, the faster the speech detection, but also less quality.')}}<br>
                {{t('The higher, the slower the speech detection, but better quality')}}
            </p>
        </field>
        <field>
            <label>{{t('Microphone Activation Shortcut')}}</label>
            <div style="display: flex; align-items: center; gap: 8px;">
                <input
                    type="text"
                    readonly
                    :value="formData.shortcut"
                    @focus="startRecordingShortcut"
                    @keydown.prevent="recordShortcut"
                    @blur="stopRecordingShortcut"
                    v-bind:placeholder="t('Click and press a key or key combination')"
                    style="width: 180px;"
                    tabindex="0"
                />
                <button type="button" @click="clearShortcut" style="margin-left: 4px;">{{t('Clear')}}</button>
            </div>
            <p style="font-size: 0.95em; color: #aaa;">{{t('Click the box and press a key or combination (e.g., Ctrl+R) to set the shortcut.')}}</p>
        </field>
        <!--field>
            <label>Continuous Mode</label>
            <input type="checkbox" name="continuous">
        </field>
        <field>
            <label>Wakeword</label><input type="text" value="" name="wakeword" placeholder="ex. Alexa"
                v-model="formData.wakeword">
        </field-->
        <button @click="updateSettings">{{t('SAVE PLUGIN SETTINGS')}}</button>
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
.plugin-settings-component{
    padding: 15px !important;
}
</style>