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
    components: {
      //** JS_COMPONENTS */
    },
    template: appTemplate,
    mounted: function () {
      window.addEventListener("pywebviewready", async function () {
        app.pywebviewready = true;
        console.log("Python is ready!");
      });
      /*
      const path = ''; 
      ws_url = `ws://localhost:9715/${path}`
      this.websocketUtil = new WebSocketUtil(ws_url, {
          onMessage: this.handleIncomingMessage,
          onOpen: () => console.log('WebSocket connection opened at ' + ws_url),
          onClose: () => console.log('WebSocket connection closed at ' + ws_url),
          onError: (error) => console.error('WebSocket error in BasePluginComponent:', error)
      });
      */
    },
    methods: {
      handleIncomingMessage(event) {
        console.log("APP received message from backend:", event.data);
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
