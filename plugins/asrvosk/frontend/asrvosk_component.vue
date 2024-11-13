<template>
    <div class="asrvosk">
        <div class="mic" :class="status">
            <img v-if="status !== 'listening'" src="/img/mic.png">
        </div>
        <img v-if="status == 'listening'" src="/img/listening.gif">
    </div>
</template>
<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "asrvosk",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            websocket: null,  // Store WebSocket instance
            websocketPath: 'asrvosk', // Specify the path for WebSocket connection
            status: 'loading'
        };
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in asrvosk component:", event.data);
            const data = JSON.parse(event.data);
            this.status = data.status;
            
        }
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>
<style>
.mic img{
    max-height: 50px;
    max-width: 50px;
}
.mic.loading{
    opacity: 0.5;
    animation: pulse 2s infinite;
}
.mic.ready{
    opacity: 1;
}
</style>