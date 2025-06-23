// console.log('BasePluginComponent is being imported');
const WebSocketUtil = require("./WebSocketUtil.js");
const BASE_WS_URL = "ws://localhost:9715/"; // Base WebSocket URL

module.exports = {
  props: {
    appview: {
      type: String,
      required: false,
    },
    lang: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      websocket: null,
      error: false,
      connectionAttempts: 0,
      maxRetries: 5,
      retryDelay: 1000,
      translations: {}
    };
  },
  methods: {
    async loadTranslations() {
      try {
        const pluginName = this.$options.name
          .replace(/Settings$/, "")
          .toLowerCase();
        const lang = this.lang || "en";
        const url = `/plugins/${pluginName}/locales/${lang}/${pluginName}_${lang}.json`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Could not load ${url}`);
        this.translations = await response.json();
        console.log(
          `Loaded translations for ${pluginName}:`,
          this.translations
        );
      } catch (e) {
        // console.warn("Translation loading failed:", e);
        this.translations = {};
      }
    },
    requestSettings() {
      this.sendMsgToBackend({
        action: "get_settings",
      });
    },
    updateSettings() {
      console.log("Saving plugin settings:", this.formData);
      let plugin_name = this.$options.name;
      if (plugin_name.endsWith("Settings")) {
        plugin_name = plugin_name.substring(
          0,
          plugin_name.length - "Settings".length
        );
      }
      window.pywebview.api.update_plugin_settings(plugin_name, this.formData);
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
            self.sendMsgToBackend({ socket: "ready" });
            console.log(
              `Socket ready Message sent to backend for ${this.$options.name} plugin`
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
    console.log(
      "BasePluginComponent created hook for " + this.$options.name + " plugin"
    );
    const path = this.websocketPath || this.$options.name || "";
    this.ws_url = `${BASE_WS_URL}${path}`;
    console.log("Plugin path = " + this.ws_url);
    this.initializeWebSocket();
    this.loadTranslations();
  },
  beforeDestroy() {
    if (this.websocketUtil) {
      this.websocketUtil.close();
    }
  },
};
