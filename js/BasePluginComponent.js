// console.log('BasePluginComponent is being imported');
const WebSocketUtil = require('./WebSocketUtil.js');
const BASE_WS_URL = 'ws://localhost:9715/'; // Base WebSocket URL

module.exports = {
    props: {
        appview: {
            type: String,
            required: false
        }
    },
    data() {
        return {
            websocket: null,  // Store WebSocket instance
        };
    },
    methods: {
        requestSettings() {
            this.sendMsgToBackend({
                action: 'get_settings'
            });
        },
        sendMsgToBackend(data, plugin_name = null) {
            const targetUrl = plugin_name 
                ? `${BASE_WS_URL}${plugin_name}` 
                : this.ws_url;
            console.log(`Sending msg to backend on ${targetUrl}`);
            console.log(data);

            if (this.websocketUtil) {
                if (plugin_name) {
                    // Create a temporary WebSocket connection
                    const tempWebSocketUtil = new WebSocketUtil(targetUrl, {
                        onMessage: (event) => console.log("Response from plugin WebSocket:", event.data),
                        onOpen: () => {
                            tempWebSocketUtil.send(data);
                            tempWebSocketUtil.close(); // Close the connection after sending
                        },
                        onClose: () => console.log(`Temporary WebSocket connection to ${targetUrl} closed`),
                        onError: (error) => console.error(`WebSocket error in temporary connection:`, error)
                    });
                } else {
                    // Use the existing WebSocket connection
                    this.websocketUtil.send(data);
                }
            }
        },
        handleIncomingMessage(event) {
            console.log("Base message receiver for plugin " + this.$options.name + ". Msg from backend:", event.data);
            try {
                const data = JSON.parse(event.data);
                // Handle common cases
                if (data.status === 'ready') {
                    this.requestSettings();
                    return true; // Indicate the message was handled
                }
                return false; // Indicate the message wasn't handled by base component
            }
            catch(e) {
                console.warn('Error parsing message:', e);
                return false;
            }
        }
    },
    created() {
        console.log('BasePluginComponent created hook for ' + this.$options.name + ' plugin');
        const path = this.websocketPath || this.$options.name || ''; 
        this.ws_url = `${BASE_WS_URL}${path}`; // Use the base WebSocket URL
        console.log('Plugin path = ' + this.ws_url);
        self = this;
        this.websocketUtil = new WebSocketUtil(this.ws_url, {
            onMessage: this.handleIncomingMessage,
            onOpen: () => { 
                self.sendMsgToBackend({ socket: "ready" });
                console.log(`Socket ready Message sent to backend for ${this.$options.name} plugin`);
            },
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