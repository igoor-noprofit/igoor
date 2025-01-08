<template>
    <div class="weather-plugin">
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "meteo",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            
        };
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in weather component:", event.data);
            try {
                const data = JSON.parse(event.data);
                console.log(data)
            }
            catch (e) {
                console.warn("Error parsing JSON")
            }
        }
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>