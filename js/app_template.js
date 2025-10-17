var data = {
  pywebviewready: false,
};
let app;

function registerReadypy(fn) {
  if (typeof window === "undefined") {
    return;
  }

  const registerFn = window.__app_register_readypy;
  const pending = window.__app_pending_readypy;

  if (typeof registerFn === "function") {
    registerFn(fn);
    return;
  }

  window.app = window.app || {};
  window.app.readypy = fn;

  if (Array.isArray(pending)) {
    while (pending.length) {
      const args = pending.shift();
      try {
        fn(...(Array.isArray(args) ? args : []));
      } catch (error) {
        console.error("Deferred readypy call failed", error);
      }
    }
  }
}

import("/js/backend_api.js");

window.addEventListener("pywebviewready", () => {
  console.log("✅ pywebviewready fired");
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
import { ensureBackendApi } from "/js/ensureBackendApi.js";
const backendApi = await ensureBackendApi();
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
        lang: "{{LANG}}",
      };
    },
    components: {
      //** JS_COMPONENTS */
    },
    template: appTemplate,
    mounted: async function () {
      console.warn("APP MOUNTED");
    },
    methods: {
      async readypy() {
        this.pywebviewready = true;
        console.warn("Pywebview is ready!");
        await backendApi.waitUntilReady();
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

        if (view === "onboarding") {
          console.warn("Forcing onboarding");
          await backendApi.forceOnboarding();
        } else {
          await backendApi.changeView(this.lastview, view);
        }
      },
      maximize() {
        console.log("MAXIMIZE WINDOW");
        backendApi.maximize();
        this.minimized = false;
        console.log("MINIMIZED=" + this.minimized);
      },
      minimize() {
        console.log("MINIMIZE WINDOW");
        backendApi.minimize();
        this.minimized = true;
        console.log("MINIMIZED=" + this.minimized);
      },
      goBack() {
        this.appview = this.lastview;
      },
    },
  });
  console.log("created");
  app = app.mount("#app");
  if (typeof window !== "undefined") {
    window.app = { ...window.app, ...app };
    registerReadypy(app.readypy.bind(app));
  }
  console.log(app);
}
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeApp, { once: true });
} else {
  initializeApp();
}
