// console.log('BasePluginComponent is being imported');
const WebSocketUtil = require("./WebSocketUtil.js");
const BASE_WS_URL = "ws://localhost:9715/"; // Base WebSocket URL

module.exports = {
  props: {
    appview: {
      type: String,
      required: false,
    },
  },
  data() {
    return {
      websocket: null,
      error: false,
      connectionAttempts: 0,
      maxRetries: 5,
      retryDelay: 1000, // Start with 1 second delay
      canonicalPluginName: null, // Added to store the canonical plugin name
    };
  },
  methods: {
    requestSettings() {
      this.sendMsgToBackend({
        action: "get_settings",
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
            onMessage: (event) =>
              console.log("Response from plugin WebSocket:", event.data),
            onOpen: () => {
              tempWebSocketUtil.send(data);
              tempWebSocketUtil.close(); // Close the connection after sending
            },
            onClose: () =>
              console.log(
                `Temporary WebSocket connection to ${targetUrl} closed`
              ),
            onError: (error) =>
              console.error(`WebSocket error in temporary connection:`, error),
          });
        } else {
          // Use the existing WebSocket connection
          this.websocketUtil.send(data);
        }
      }
    },
    handleIncomingMessage(event) {
      console.log(
        "DEFAULT message receiver for plugin " +
          this.$options.name +
          ". Msg from backend:",
        event.data
      );
      try {
        const data = JSON.parse(event.data);
        // Reset error states when receiving non-error messages
        if (data.type !== "error") {
          this.resetErrorStates();
        }
        // Handle common cases
        if (data.status === "ready") {
          this.requestSettings();
          return true; // Indicate the message was handled
        }
        if (data.type === "error") {
          this.error = {
            code: data.error_code,
            message: data.message,
            details: data.details,
          };
          console.error(`${this.$options.name} error:`, data.message);
          return true;
        }
        return false; // Indicate the message wasn't handled by base component
      } catch (e) {
        console.warn("Error parsing message:", e);
        return false;
      }
    },
    resetErrorStates() {
      this.error = false;
      console.log(`Resetting error states for ${this.$options.name}`);
    },
    async initializeWebSocket() {
      if (this.connectionAttempts >= this.maxRetries) {
        console.error(
          `Failed to connect to WebSocket after ${this.maxRetries} attempts`
        );
        return;
      }

      try {
        this.connectionAttempts++;
        const currentDelay =
          this.retryDelay * Math.pow(2, this.connectionAttempts - 1); // Exponential backoff

        if (this.connectionAttempts > 1) {
          console.log(
            `Attempting to reconnect in ${currentDelay}ms (attempt ${this.connectionAttempts})`
          );
          await new Promise((resolve) => setTimeout(resolve, currentDelay));
        }

        self = this;
        this.websocketUtil = new WebSocketUtil(this.ws_url, {
          onMessage: this.handleIncomingMessage,
          onOpen: () => {
            self.connectionAttempts = 0; // Reset attempts on successful connection
            // Send the canonical plugin name to the backend
            self.sendMsgToBackend({ socket: "ready", plugin: self.canonicalPluginName });
            console.log(
              `Socket ready Message sent to backend for ${self.canonicalPluginName} plugin`
            );
          },
          onClose: () => {
            console.log(`WebSocket connection closed at ${this.ws_url}`);
            this.initializeWebSocket(); // Try to reconnect
          },
          onError: (error) => {
            console.error("WebSocket error in BasePluginComponent:", error);
            if (this.connectionAttempts < this.maxRetries) {
              this.initializeWebSocket(); // Try to reconnect on error
            }
          },
        });
      } catch (error) {
        console.error("Error initializing WebSocket:", error);
        if (this.connectionAttempts < this.maxRetries) {
          this.initializeWebSocket(); // Try to reconnect on error
        }
      }
    },
  },
  created() {
    const determinedPluginName = this.pluginName || this.websocketPath || this.$options.name || "";
    this.canonicalPluginName = determinedPluginName;
    console.log(
      "BasePluginComponent created hook for " + this.canonicalPluginName + " plugin"
    );
    this.ws_url = `${BASE_WS_URL}${this.canonicalPluginName}`;
    console.log("WebSocket URL for " + this.canonicalPluginName + " = " + this.ws_url);
    this.initializeWebSocket();
  },
  beforeDestroy() {
    if (this.websocketUtil) {
      this.websocketUtil.close();
    }
  },
};
