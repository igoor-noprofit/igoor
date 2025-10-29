<template>
    <div class="asrjs-plugin-settings form-grid">
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

        <!-- API Endpoints Configuration -->
        <div class="form-label">{{t('Transcription API URL')}}</div>
        <div class="form-input">
            <input
                type="url"
                v-model="formData.transcription_api_url"
                placeholder="http://localhost:8001/transcribe"
            />
        </div>
        <div class="form-note">
            {{t('Local API endpoint for speech transcription')}}
        </div>

        <div class="form-label">{{t('Speaker ID API URL')}}</div>
        <div class="form-input">
            <input
                type="url"
                v-model="formData.speaker_api_url"
                placeholder="http://localhost:8002/identify"
            />
        </div>
        <div class="form-note">
            {{t('Local API endpoint for speaker identification')}}
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
    name: "asrjsSettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    data() {
        return {
            originalSettings: null,
            formData: {
                vad_level: 2,
                silence_frames: 1500,
                shortcut: '',
                transcription_api_url: 'http://localhost:8001/transcribe',
                speaker_api_url: 'http://localhost:8002/identify'
            },
            isRecordingShortcut: false
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
            this.updateSettings(this.formData);
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
select, input[type="text"], input[type="url"] {
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
