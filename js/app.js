var data = {
  pywebviewready: false,
};
let app;

window.addEventListener("pywebviewready", () => {
  console.log("âœ… pywebviewready fired");
});

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
  app = Vue.createApp({
    data() {
      return {
        appview: "loading",
        lastview: "daily",
        websocketUtil: null,
        minimized: false,
        headerExpanded: false,
        pywebviewready: false,
        lang: "en_EN",
      };
    },
    components: {
      'Rag': Vue.defineAsyncComponent(() => loadModule('/plugins/rag/frontend/rag_component.vue',options)), 'Clock': Vue.defineAsyncComponent(() => loadModule('/plugins/clock/frontend/clock_component.vue',options)), 'Bugreport': Vue.defineAsyncComponent(() => loadModule('/plugins/bugreport/frontend/bugreport_component.vue',options)), 'Onboarding': Vue.defineAsyncComponent(() => loadModule('/plugins/onboarding/frontend/onboarding_component.vue',options)), 'Asrwhisper': Vue.defineAsyncComponent(() => loadModule('/plugins/asrwhisper/frontend/asrwhisper_component.vue',options)), 'Autocomplete': Vue.defineAsyncComponent(() => loadModule('/plugins/autocomplete/frontend/autocomplete_component.vue',options)), 'Conversation': Vue.defineAsyncComponent(() => loadModule('/plugins/conversation/frontend/conversation_component.vue',options)), 'Autocompletelauncher': Vue.defineAsyncComponent(() => loadModule('/plugins/autocompletelauncher/frontend/autocompletelauncher_component.vue',options)), 'Daily': Vue.defineAsyncComponent(() => loadModule('/plugins/daily/frontend/daily_component.vue',options)), 'Flow': Vue.defineAsyncComponent(() => loadModule('/plugins/flow/frontend/flow_component.vue',options)), 'Memory': Vue.defineAsyncComponent(() => loadModule('/plugins/memory/frontend/memory_component.vue',options)), 'Shortcuts': Vue.defineAsyncComponent(() => loadModule('/plugins/shortcuts/frontend/shortcuts_component.vue',options))
    },
    template: appTemplate,
    mounted: async function () {
      console.warn("APP MOUNTED");
    },
    methods: {
      readypy() {
        this.pywebviewready = true;
        console.warn("Pywebview is ready!");
        this.connectAppWebSocket();
      },
      connectAppWebSocket() {
        const socketUrl = "ws://127.0.0.1:9714/ws/app";
        this.websocketUtil = new WebSocket(socketUrl);

        this.websocketUtil.onopen = () => {
          console.log("APP WebSocket connection opened");
        };

        this.websocketUtil.onmessage = (event) => {
          console.log("APP received message on websocket:", event.data);
          try {
            const message = JSON.parse(event.data);
            if (message.backend === "addmsg") {
              this.changeView("flow");
            }
            if (message.switchview && message.switchview !== "") {
              this.changeView(message.switchview);
            }
            if (message.minimize) {
              this.minimize();
            }
          } catch (error) {
            console.error("Error parsing WebSocket message:", error);
          }
        };

        this.websocketUtil.onclose = () => {
          console.log("WebSocket connection closed");
          setTimeout(() => this.connectAppWebSocket(), 1000);
        };

        this.websocketUtil.onerror = (error) => {
          console.error("WebSocket error:", error);
        };
      },
      toggleHeaderExpansion(expanded) {
        console.log("Toggling header expansion:", expanded);
        this.headerExpanded = expanded;
        // Optionally trigger any other UI updates needed
      },
      handleIncomingMessage(event) {
        console.log("APP received message from backend:", event.data);
      },
      showAutocomplete(event) {
        this.changeView("autocomplete");
      },
      async changeView(view) {
        console.log("Switching view to " + view);
        if (!this.pywebviewready) {
          console.log("Waiting for pywebview to be ready...");
          return;
        }
        this.lastview = this.appview;
        this.appview = view;

        const localApi = window.pywebview?.api;
        if (!localApi) {
          try {
            await fetch("/api/app/change-view", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ lastview: this.lastview, view }),
            });
          } catch (error) {
            console.error("Failed to notify backend of view change:", error);
          }
          return;
        }

        if (view === "onboarding") {
          console.warn("Forcing onboarding");
          await localApi.force_onboarding();
        } else {
          await localApi.change_view(this.lastview, view);
        }
      },
      maximize() {
        console.log("MAXIMIZE WINDOW");
        window.pywebview.api.maximize();
        this.minimized = false;
        console.log("MINIMIZED=" + this.minimized);
      },
      minimize() {
        console.log("MINIMIZE WINDOW");
        window.pywebview.api.minimize();
        this.minimized = true;
        console.log("MINIMIZED=" + this.minimized);
      },
      goBack() {
        this.appview = this.lastview;
      },
    },
  });
  console.log("created");
  app = app.mount("#app");   // now app is the mounted instance
  window.app = app;   
  console.log(app);
}
document.addEventListener("DOMContentLoaded", function () {
  console.log("ready");
  initializeApp();
});
