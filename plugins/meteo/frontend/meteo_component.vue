<template>
    <div class="meteo-plugin">
        {{ temperature !== null ? temperature + "°C" : "" }}
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "meteo",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            temperature: null
        };
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in METEO component:", event.data);
            try {
                const data = JSON.parse(event.data);
                console.log("Received data in METEO component:", data);
                if (data && data.temperature && typeof data.temperature.temp !== 'undefined') {
                    this.temperature = data.temperature.temp;
                } else {
                    console.warn("Temperature data is missing or malformed", data);
                }
            }
            catch (e) {
                console.warn("Error parsing JSON in METEO component", e);
            }
        }
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>
<style>
.meteo-plugin {
    margin-left: 0.5rem;
    font-size: 0.8rem;
}
</style>