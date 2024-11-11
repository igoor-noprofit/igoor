var data = {
  pywebviewready: false,
};

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
      'Clock': Vue.defineAsyncComponent(() => loadModule('/plugins/clock/frontend/clock_component.vue',options)), 'Meteo': Vue.defineAsyncComponent(() => loadModule('/plugins/meteo/frontend/meteo_component.vue',options)), 'Settings': Vue.defineAsyncComponent(() => loadModule('/plugins/settings/frontend/settings_component.vue',options))
    },
    template: appTemplate,
    /*data: data,
    
    mounted: function () {
      window.addEventListener("pywebviewready", async function () {
        app.pywebviewready = true;
        console.log("Python is ready!");
      });
    },
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
  console.log('created');
  app.mount("#app");
}
document.addEventListener("DOMContentLoaded", function () {
  console.log("ready");
  initializeApp();
});
