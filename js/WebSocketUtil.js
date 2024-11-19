// js/WebSocketUtil.js
function WebSocketUtil(url, options = {}) {
    this.url = url;
    console.log('URL stored = ' + url)
    this.websocket = null;
    this.onMessage = options.onMessage || function() {};
    this.onOpen = options.onOpen || function() {};
    this.onClose = options.onClose || function() {};
    this.onError = options.onError || function() {};
    this.connect();
}

WebSocketUtil.prototype.connect = function() {
    this.websocket = new WebSocket(this.url);
    this.websocket.onmessage = (event) => {
        console.log("Received message from backend:", event.data);
        this.onMessage(event);
    };

    this.websocket.onopen = () => {
        console.log('WebSocket connection established');
        this.onOpen();
    };

    this.websocket.onclose = () => {
        console.log('WebSocket connection closed');
        this.onClose();
    };

    this.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.onError(error);
    };
};

WebSocketUtil.prototype.send = function(data) {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        this.websocket.send(JSON.stringify(data));
    } else {
        console.log('WebSocket ' + this.url + ' is not open');
    }
};

WebSocketUtil.prototype.close = function() {
    if (this.websocket) {
        this.websocket.close();
    }
};

module.exports = WebSocketUtil;