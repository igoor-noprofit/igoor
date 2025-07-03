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

export default {
    name: "asrwhisperSettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent], // Use the mixin
    data() {

        return {
            formData: {
                model_name: '',
                vad_level:'',
                silence_frames:1500
            }
        };
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal) {
                    // Merge carefully to preserve structure if settings are partial
                    this.formData = { ...this.formData, ...newVal };
                }
            },
            immediate: true, // Apply initial values when component loads
            deep: true
        }
    }

};
</script>
<style>
.plugin-settings-component{
    padding: 15px !important;
}
</style>