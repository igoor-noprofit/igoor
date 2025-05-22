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
        initialSettings: Object,
        pluginName: String // Accept the pluginName prop from the parent
    },
    mixins: [BasePluginComponent],
    data() {
        return {
            formData: {
                wakeword: '',
                model_size: 'medium' // Default to a string, or ensure it's handled if empty
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
            // Emit both the pluginName (received as a prop) and the formData
            if (!this.pluginName) {
                console.error("Plugin name is missing in asrvosk_settings.vue. Cannot save.");
                // Optionally, alert the user or handle this more gracefully
                return;
            }
            this.$emit('save-settings', this.pluginName, this.formData);
        }
    }
};
</script>