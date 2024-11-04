// js/BasePluginComponent.js
console.log('BasePluginComponent is being imported');
const WebSocketUtil = require('./WebSocketUtil.js');

module.exports = {
    data() {
        return {
            websocket: null,  // Store WebSocket instance
        };
    },
    methods: {
        commonMethod() {
            console.log("This is a common method");
        },
        invokeBackend() {
            if (this.websocketUtil) {
                this.websocketUtil.send({ type: 'invoke_backend', data: 'some_data' });
            }
        },
        handleIncomingMessage(event) {
            console.log("Received message from backend:", event.data);
        }
    },
    created() {
        console.log('BasePluginComponent created hook');
        const path = this.websocketPath || ''; // Use the provided path or default to an empty string
        ws_url = `ws://localhost:9715/${path}`
        this.websocketUtil = new WebSocketUtil(ws_url, {
            onMessage: this.handleIncomingMessage,
            onOpen: () => console.log('WebSocket connection opened at ' + ws_url),
            onClose: () => console.log('WebSocket connection closed at ' + ws_url),
            onError: (error) => console.error('WebSocket error in BasePluginComponent:', error)
        });
    },
    beforeDestroy() {
        if (this.websocketUtil) {
            this.websocketUtil.close();
        }
    }
};