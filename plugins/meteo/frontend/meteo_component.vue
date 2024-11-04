<template>
    <div class="meteo-plugin">
        <button @click="invokeBackend">Invoke Backend</button>
    </div>
</template>

<script>
module.exports = {
    name: "meteo",
    data() {
        return {
            websocket: null  // Store WebSocket instance
        };
    },
    methods: {
        invokeBackend() {
            // Example method to send data to backend
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({ type: 'invoke_backend', data: 'some_data' }));
            } else {
                console.log('WebSocket is not open');
            }
        },
        handleIncomingMessage(event) {
            // Handle incoming messages
            const message = event.data;
            console.log("Received message from backend:", message);
            // Further processing of the message can be added here
        }
    },
    created() {
        this.websocket = new WebSocket("ws://localhost:9715/meteo"); // Connect to the server and specific channel
        this.websocket.onmessage = this.handleIncomingMessage;

        this.websocket.onopen = () => {
            console.log('WebSocket connection established');
        };

        this.websocket.onclose = () => {
            console.log('WebSocket connection closed');
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    },
    beforeDestroy() {
        if (this.websocket) {
            this.websocket.close();  // Ensure WebSocket connection is closed when component is destroyed
        }
    }
};
</script>