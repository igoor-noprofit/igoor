<template>
    <div class="asrwhisper-plugin-settings">
        <field>
            <label>Model Name</label>
            <select name="model_name" v-model="formData.model_name">
                <option value="whisper-large-v3">Whisper Large v3</option>
                <option value="whisper-large-v3-turbo">Whisper Large v3 Turbo</option>
            </select>
        </field>
        <field>
            <label>VAD level</label>
            <select name="vad_level" v-model="formData.vad_level">
                <option value="0">0 (Less aggressive)</option>
                <option value="1">1</option>
                <option value="2">2 (Recommended)</option>
                <option value="3">3 (Most aggressive)</option>
            </select>
            <p>
                The VAD level determines how aggressive the algorithm is at detecting speech.
                Higher levels works better in noisy environments. 
            </p>
        </field>
        <field>
            <label>Silence Frames</label>
            <select name="silence_frames" v-model="formData.silence_frames">
                <option value="500">500: Faster ASR / More</option>
                <option value="1250">1250: Recommended for most cases</option>
                <option value="1500">1500: Recommended for most cases</option>
                <option value="2000">2000: Slower ASR: For people making big pauses</option>
            </select>
            <p>The time (in ms) of silence before speech detection automatically ends.
                The lower, the faster speech detection but also the more likely you'll miss speech.
                The higher, the slower speech detection.
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
        <button @click="updateSettings">SAVE PLUGIN SETTINGS</button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
// console.log('BasePluginComponent imported:', BasePluginComponent); // Optional: for debugging

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