<template>
    <div class="asrwhisper-plugin-settings">
        <field>
            <label>Wakeword</label><input type="text" value="" name="wakeword" placeholder="ex. Alexa">
        </field>
        <field>
            <label>Groq API Key</label><input type="password" value="" name="api_key" placeholder="Enter your Groq API key">
        </field>
        <field>
            <label>Model Name</label>
            <select name="model_name">
                <option value="whisper-large-v3">Whisper Large v3</option>
                <option value="whisper-large-v3-turbo">Whisper Large v3 Turbo</option>
            </select>
        </field>
        <field>
            <label>Language</label>
            <select name="lang">
                <option value="fr">French</option>
                <option value="en">English</option>
                <option value="de">German</option>
                <option value="es">Spanish</option>
                <!-- Add other languages as needed -->
            </select>
        </field>
        <field>
            <label>Continuous Mode</label>
            <input type="checkbox" name="continuous">
        </field>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
// console.log('BasePluginComponent imported:', BasePluginComponent); // Optional: for debugging

export default {
    name: "asrwhisperSettings",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            // No specific data needed here for this simple settings component
        };
    },
    methods: {
        // No specific methods needed here for this simple settings component
    },
    created() {
        // Lifecycle hook, can be used for initialization if needed
    },
    beforeDestroy() {
        // Lifecycle hook, can be used for cleanup if needed
    }
};
</script>

<style scoped>
/* Add any specific styles for your settings component here */
.asrwhisper-plugin-settings field {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.asrwhisper-plugin-settings label {
    min-width: 120px; /* Adjust as needed */
    margin-right: 10px;
}

.asrwhisper-plugin-settings input[type="text"],
.asrwhisper-plugin-settings input[type="password"],
.asrwhisper-plugin-settings select {
    flex-grow: 1;
    padding: 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
}

.asrwhisper-plugin-settings input[type="checkbox"] {
    margin-left: 5px;
}
</style>