document.addEventListener("DOMContentLoaded", function () {
    var data = {
        pywebviewready: false,
    };
     
    const options = {

        moduleCache: {
          vue: Vue,
        },
        
        getFile(url) {
          return fetch(url).then(response => response.ok ? response.text() : Promise.reject(response));
        },
        
        addStyle(styleStr) {
          const style = document.createElement('style');
          style.textContent = styleStr;
          const ref = document.head.getElementsByTagName('style')[0] || null;
          document.head.insertBefore(style, ref);
        },
        
        log(type, ...args) {
          console.log(type, ...args);
        }
      }
      const { loadModule, version } = window["vue3-sfc-loader"];
    
    const app = Vue.createApp({
        el: "#app",
        components: {
        //** JS_COMPONENTS */
        },
        data: data,
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
            }
            /* useless wrapper?
            js_api(func, ...args){
                if (this[func] && typeof this[func] === 'function') {
                    pywebview.api[func](...args);
                } else {
                    console.error(`Method '${func}' does not exist or is not a function`);
                }
            }
            */
        }
    });
});
