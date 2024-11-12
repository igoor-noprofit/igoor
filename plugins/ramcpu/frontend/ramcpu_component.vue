<template>
    <div class="ramcpu-plugin">
        RAM: {{ memoryUsage.toFixed(2) }} MB, CPU: {{ cpuUsage.toFixed(1) }}%
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "ramcpu",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            websocket: null,  // Store WebSocket instance
            websocketPath: 'ramcpu', // Specify the path for WebSocket connection
            cpuUsage: 0.0, // Initialize CPU usage
            memoryUsage: 0.0 // Initialize memory usage
        };
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in ramcpu component:", event.data);
            const data = JSON.parse(event.data);
            this.cpuUsage = data.cpu_usage;
            this.memoryUsage = data.memory_usage;
        }
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>