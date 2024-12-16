var data = {
  pywebviewready: false,
};
/*
if ('AmbientLightSensor' in window) {
  alert("Ambient Light Sensor detected");
} else {
  console.log("No Ambient Light Sensor available");
}
*/

const options = {
  moduleCache: {
    vue: Vue,
  },

  getFile(url) {
    return fetch(url).then((response) =>
      response.ok ? response.text() : Promise.reject(response)
    );
  },

  addStyle(styleStr) {
    const style = document.createElement("style");
    style.textContent = styleStr;
    const ref = document.head.getElementsByTagName("style")[0] || null;
    document.head.insertBefore(style, ref);
  },

  log(type, ...args) {
    console.log(type, ...args);
  },
};
const { loadModule, version } = window["vue3-sfc-loader"];
async function initializeApp() {
  console.log("initializing app");
  const appTemplate = await options.getFile("/js/app.vue");
  console.log(appTemplate);
  const app = Vue.createApp({
    data() {
      return {
        appview: "loading", // Add this line
        lastview: "daily",
        websocketUtil: null,
        // ... other data properties if needed ...
      };
    },
    components: {
      'Rag': Vue.defineAsyncComponent(() => loadModule('/plugins/rag/frontend/rag_component.vue',options)), 'Elevenlabs': Vue.defineAsyncComponent(() => loadModule('/plugins/elevenlabs/frontend/elevenlabs_component.vue',options)), 'Asrvosk': Vue.defineAsyncComponent(() => loadModule('/plugins/asrvosk/frontend/asrvosk_component.vue',options)), 'Autocomplete': Vue.defineAsyncComponent(() => loadModule('/plugins/autocomplete/frontend/autocomplete_component.vue',options)), 'Conversation': Vue.defineAsyncComponent(() => loadModule('/plugins/conversation/frontend/conversation_component.vue',options)), 'Autocompletelauncher': Vue.defineAsyncComponent(() => loadModule('/plugins/autocompletelauncher/frontend/autocompletelauncher_component.vue',options)), 'Onboarding': Vue.defineAsyncComponent(() => loadModule('/plugins/onboarding/frontend/onboarding_component.vue',options)), 'Flow': Vue.defineAsyncComponent(() => loadModule('/plugins/flow/frontend/flow_component.vue',options))
    },
    template: appTemplate,
    mounted: function () {
      window.addEventListener("pywebviewready", async function () {
        app.pywebviewready = true;
        console.log("Python is ready!");
      });
      // Create a WebSocket connection
      this.websocketUtil = new WebSocket("ws://localhost:9715/app");

      // Set up WebSocket event listeners
      this.websocketUtil.onopen = function () {
        console.log("WebSocket connection opened");
      };

      this.websocketUtil.onmessage = (event) => {
        console.log("APP received message on websocket:", event.data);
        // Handle incoming WebSocket messages here
        try {
          const message = JSON.parse(event.data);
          console.log("Parsed message:", message); // Log the parsed message
          if (message.backend === "addmsg") {
            this.changeView('flow')
          }
          if (message.switchview && message.switchview != ''){
            this.changeView(message.switchview)
          }
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      this.websocketUtil.onclose = function () {
        console.log("WebSocket connection closed");
      };

      this.websocketUtil.onerror = function (error) {
        console.error("WebSocket error:", error);
      };
    },
    methods: {
      handleIncomingMessage(event) {
        console.log("APP received message from backend:", event.data);
      },
      showAutocomplete(event) {
        this.changeView("autocomplete");
      },
      changeView(view) {
        console.log("Switching view to " + view)
        this.lastview = this.appview;
        this.appview = view;
        window.pywebview.api.change_view(this.lastview,view);
      },
      goBack() {
        this.appview = this.lastview;
      },
    },
    /*data: data,
    methods: {
      showDaily() {
        this.daily = true;
      },
      minimize() {
        if (!this.minimized) {
          pywebview.api.minimize_window();
          this.minimized = true;
        }
      },
      maximize() {
        if (this.minimized) {
          pywebview.api.maximize_window();
          this.minimized = false;
        }
      },
    },
    */
  });
  console.log("created");
  app.mount("#app");
}
document.addEventListener("DOMContentLoaded", function () {
  console.log("ready");
  initializeApp();
});
