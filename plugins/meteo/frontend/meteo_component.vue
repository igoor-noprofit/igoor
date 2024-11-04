<template>
    <div class="meteo-plugin">
        <button @click="invokeBackend">Invoke Backend</button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
console.log('BasePluginComponent imported:', BasePluginComponent);

export default {
    name: "meteo",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            websocket: null,  // Store WebSocket instance
            websocketPath: 'meteo' // Specify the path for WebSocket connection
        };
    },
    methods: {
        
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>