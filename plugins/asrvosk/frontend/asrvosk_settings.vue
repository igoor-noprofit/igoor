<template>
    <div class="asrvosk-plugin-settings">
        <field>
            <label>Wakeword</label><input type="text" name="wakeword" v-model="formData.wakeword"
                placeholder="ex. Alexa">
        </field>
        <field>
            <label>Model size</label><input type="text" name="model_size" v-model="formData.model_size"
                placeholder="big|medium|small">
        </field>
        <button @click="savePluginSpecificSettings">Save ASR Vosk Settings</button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
// console.log('BasePluginComponent imported:', BasePluginComponent); // Optional: for debugging

export default {
    name: "asrvoskSettings", // This is Vue's internal name, which is fine.
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    data() {
        return {
            formData: {
                wakeword: '',
                model_size: ''
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
    },
    methods: {
        savePluginSpecificSettings() {
            this.saveSettings(this.formData);
        }
    }
};
</script>