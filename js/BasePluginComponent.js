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
        sendMsgToBackend(data) {
            console.log("Sending msg to backend");
            console.log(data);
            if (this.websocketUtil) {
                this.websocketUtil.send(data);
            }
        },
        handleIncomingMessage(event) {
            console.log("Default message receiver. Msg from backend:", event.data);
        }
    },
    created() {
        console.log('BasePluginComponent created hook');
        const path = this.websocketPath || ''; // Use the provided path or default to an empty string
        ws_url = `ws://localhost:9715/${path}`
        self = this;
        this.websocketUtil = new WebSocketUtil(ws_url, {
            onMessage: this.handleIncomingMessage,
            onOpen: () => self.sendMsgToBackend({"socket":"ready"}),
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