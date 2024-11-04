<template>
    <div class="meteo-plugin">
        <button @click="invokeBackend">Invoke Backend</button>
    </div>
</template>

<script>
const BasePluginComponent = require('/js/BasePluginComponent.js');
console.log('BasePluginComponent imported:', BasePluginComponent);

module.exports = {
    name: "meteo",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            websocket: null  // Store WebSocket instance
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