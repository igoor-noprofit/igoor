// console.log('BasePluginComponent is being imported');
const WebSocketUtil = require('./WebSocketUtil.js');
const BASE_WS_URL = 'ws://localhost:9715/'; // Base WebSocket URL

module.exports = {
    data() {
        return {
            websocket: null,  // Store WebSocket instance
        };
    },
    methods: {
        sendMsgToBackend(data) {
            console.log("Sending msg to backend on " + this.ws_url);
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
        const path = this.websocketPath || this.$options.name || ''; 
        this.ws_url = `ws://localhost:9715/${path}`
        console.log('Plugin path = ' + this.ws_url)
        self = this;
        this.websocketUtil = new WebSocketUtil(this.ws_url, {
            onMessage: this.handleIncomingMessage,
            onOpen: () => self.sendMsgToBackend({"socket":"ready"}),
            onClose: () => console.log('WebSocket connection closed at ' + this.ws_url),
            onError: (error) => console.error('WebSocket error in BasePluginComponent:', error)
        });
    },
    beforeDestroy() {
        if (this.websocketUtil) {
            this.websocketUtil.close();
        }
    }
};