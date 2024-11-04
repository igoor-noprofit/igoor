// js/BasePluginComponent.js
console.log('BasePluginComponent is being imported');
const WebSocketUtil = require('./WebSocketUtil.js');

module.exports = {
    data() {
        return {
            websocketUtil: null
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
        this.websocketUtil = new WebSocketUtil('ws://localhost:9715', {
            onMessage: this.handleIncomingMessage,
            onOpen: () => console.log('WebSocket connection opened in BasePluginComponent'),
            onClose: () => console.log('WebSocket connection closed in BasePluginComponent'),
            onError: (error) => console.error('WebSocket error in BasePluginComponent:', error)
        });
    },
    beforeDestroy() {
        if (this.websocketUtil) {
            this.websocketUtil.close();
        }
    }
};