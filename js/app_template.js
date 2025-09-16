var data = {
  pywebviewready: false,
};
let app;

window.addEventListener("pywebviewready", () => {
  console.log("✅ pywebviewready fired");
  window.pywebview.api.ping().then(console.log);
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
      readypy() {
        this.pywebviewready = true;
        console.warn("Pywebview is ready!");
        // Create a WebSocket connection
        this.websocketUtil = new WebSocket("ws://localhost:9715/app");

        // Set up WebSocket event listeners
        this.websocketUtil.onopen = function () {
          console.log("APP WebSocket connection opened");
        };

        this.websocketUtil.onmessage = (event) => {
          console.log("APP received message on websocket:", event.data);
          // Handle incoming WebSocket messages here
          try {
            const message = JSON.parse(event.data);
            console.log("Parsed message:", message); // Log the parsed message
            if (message.backend === "addmsg") {
              this.changeView("flow");
            }
            if (message.switchview && message.switchview != "") {
              this.changeView(message.switchview);
            }
            if (message.minimize) {
              this.minimize();
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
        await window.pywebview.api.change_view(this.lastview, view);
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
